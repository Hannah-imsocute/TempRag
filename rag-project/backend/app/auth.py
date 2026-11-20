import hashlib
import hmac
import secrets
from typing import Annotated

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config import Settings

router = APIRouter(prefix="/api/auth")
COOKIE = "rag_session"
SESSION_SECONDS = 7 * 24 * 3600


class Credentials(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.-]{3,40}$")
    password: str = Field(min_length=1, max_length=128)


# 비밀번호를 저장할 scrypt 해시를 생성합니다.
def password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return f"{salt.hex()}:{digest.hex()}"


# 설정된 웹 관리자 계정을 최초 실행 시 생성합니다.
async def bootstrap_admin(pool: asyncpg.Pool, settings: Settings) -> None:
    if not settings.admin_password:
        return
    credentials = Credentials(username=settings.admin_username, password=settings.admin_password)
    if len(credentials.password) < 8:
        raise ValueError("ADMIN_PASSWORD는 8자 이상이어야 합니다.")
    username = credentials.username.lower()
    async with pool.acquire() as connection, connection.transaction():
        await connection.execute("SELECT pg_advisory_xact_lock(81347602)")
        account = await connection.fetchrow("SELECT role FROM users WHERE username=$1", username)
        if account:
            if account["role"] != "admin":
                raise ValueError("ADMIN_USERNAME이 기존 일반 계정과 중복됩니다.")
            return
        digest = await run_in_threadpool(password_hash, credentials.password)
        await connection.execute(
            "INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'admin')", username, digest
        )


# 세션 토큰의 SHA-256 해시를 반환합니다.
def token_hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


# 세션 쿠키를 검증하고 로그인한 사용자를 조회합니다.
async def current_user(request: Request):
    token = request.cookies.get(COOKIE)
    if token:
        user = await request.app.state.db.fetchrow(
            """SELECT u.id, u.username, u.role FROM login_sessions s JOIN users u ON u.id=s.user_id
               WHERE s.token_hash=$1 AND s.expires_at>now()""",
            token_hash(token),
        )
        if user:
            return user
    raise HTTPException(401, "로그인이 필요합니다.")


User = Annotated[asyncpg.Record, Depends(current_user)]


# 로그인한 사용자의 관리자 권한을 확인합니다.
async def admin_only(user: User):
    if user["role"] != "admin":
        raise HTTPException(403, "관리자 계정이 필요합니다.")
    return user


Admin = Annotated[asyncpg.Record, Depends(admin_only)]


# 로그인 세션을 등록하고 브라우저에 쿠키를 발급합니다.
async def open_session(request: Request, response: Response, user: asyncpg.Record):
    token = secrets.token_urlsafe(32)
    async with request.app.state.db.acquire() as connection, connection.transaction():
        await connection.execute("DELETE FROM login_sessions WHERE expires_at <= now()")
        previous = request.cookies.get(COOKIE)
        if previous:
            await connection.execute("DELETE FROM login_sessions WHERE token_hash=$1", token_hash(previous))
        await connection.execute(
            "INSERT INTO login_sessions VALUES ($1, $2, now() + make_interval(secs => $3))",
            token_hash(token), user["id"], SESSION_SECONDS,
        )
    response.set_cookie(
        COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="strict",
        secure=request.app.state.settings.cookie_secure,
    )
    return {"username": user["username"], "role": user["role"]}


# 일반 사용자 계정을 만들고 로그인합니다.
@router.post("/register", status_code=201)
async def register(body: Credentials, request: Request, response: Response):
    username = body.username.lower()
    if username == request.app.state.settings.admin_username.lower():
        raise HTTPException(409, "이미 사용 중인 아이디입니다.")
    if len(body.password) < 8:
        raise HTTPException(422, "비밀번호를 8자 이상 입력해 주세요.")
    digest = await run_in_threadpool(password_hash, body.password)
    user = await request.app.state.db.fetchrow(
        """INSERT INTO users (username, password_hash, role) VALUES ($1, $2, 'user')
           ON CONFLICT (username) DO NOTHING RETURNING id, username, role""",
        username, digest,
    )
    if not user:
        raise HTTPException(409, "이미 사용 중인 아이디입니다.")
    return await open_session(request, response, user)


# 아이디와 비밀번호를 검증하고 로그인합니다.
@router.post("/login")
async def login(body: Credentials, request: Request, response: Response):
    user = await request.app.state.db.fetchrow(
        "SELECT id, username, password_hash, role FROM users WHERE username=$1", body.username.lower()
    )
    salt = bytes.fromhex(user["password_hash"].split(":")[0]) if user else bytes(16)
    digest = await run_in_threadpool(password_hash, body.password, salt)
    if not user or not hmac.compare_digest(digest, user["password_hash"]):
        raise HTTPException(401, "아이디 또는 비밀번호를 확인해 주세요.")
    return await open_session(request, response, user)


# 현재 로그인한 계정의 공개 정보를 반환합니다.
@router.get("/me")
async def me(user: User):
    return {"username": user["username"], "role": user["role"]}


# 현재 로그인 세션과 쿠키를 제거합니다.
@router.post("/logout", status_code=204)
async def logout(request: Request, response: Response):
    token = request.cookies.get(COOKIE)
    if token:
        await request.app.state.db.execute("DELETE FROM login_sessions WHERE token_hash=$1", token_hash(token))
    response.delete_cookie(COOKIE)
