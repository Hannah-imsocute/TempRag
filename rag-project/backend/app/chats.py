import asyncio
from contextlib import aclosing
import json
import logging
from uuid import UUID, uuid4

from anyio import CancelScope
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.auth import User
from app.database import operation
from app.schemas import ChatRequest
from app.sse import encode_sse

router = APIRouter(prefix="/api/chat")
logger = logging.getLogger(__name__)


# 로그인 사용자가 소유한 대화만 조회합니다.
async def owned_conversation(db, conversation_id, user_id):
    chat = await db.fetchrow(
        "SELECT id, title, updated_at FROM conversations WHERE id=$1 AND user_id=$2", conversation_id, user_id
    )
    if not chat:
        raise HTTPException(404, "대화를 찾을 수 없습니다.")
    return chat


# 사용자의 대화 목록을 최신순으로 반환합니다.
@router.get("/conversations")
async def conversations(request: Request, user: User):
    return await request.app.state.db.fetch(
        "SELECT id, title, updated_at FROM conversations WHERE user_id=$1 ORDER BY updated_at DESC, id", user["id"]
    )


# 사용자에게 속한 새 대화를 생성합니다.
@router.post("/conversations", status_code=201)
async def create_conversation(request: Request, user: User):
    return await request.app.state.db.fetchrow(
        "INSERT INTO conversations (id, user_id) VALUES ($1,$2) RETURNING id, title, updated_at", uuid4(), user["id"]
    )


# 대화의 메시지와 출처를 시간순으로 반환합니다.
@router.get("/conversations/{conversation_id}")
async def conversation(conversation_id: UUID, request: Request, user: User):
    db = request.app.state.db
    chat = await owned_conversation(db, conversation_id, user["id"])
    messages = await db.fetch(
        "SELECT id, role, content, sources, interrupted FROM messages WHERE conversation_id=$1 ORDER BY id",
        conversation_id,
    )
    return {**chat, "messages": [{**message, "sources": json.loads(message["sources"])} for message in messages]}


# 질문을 접수하고 규정 기반 답변을 SSE로 반환합니다.
@router.post("/stream")
async def stream_chat(body: ChatRequest, request: Request, user: User):
    question = body.question.strip()
    if not question:
        raise HTTPException(422, "질문을 입력해 주세요.")
    state = request.app.state
    chat_id = body.conversation_id
    await owned_conversation(state.db, chat_id, user["id"])

    # 질문과 답변을 저장하며 생성 이벤트를 전달합니다.
    async def events():
        try:
            async with operation(state.db, f"chat:{chat_id}") as connection:
                if connection is None:
                    yield encode_sse("error", {"message": "이 대화에서 답변을 생성 중입니다."})
                    return
                previous = await connection.fetch(
                    """SELECT role, left(content, 1000) AS content FROM messages
                       WHERE conversation_id=$1 AND NOT interrupted ORDER BY id DESC LIMIT 8""", chat_id,
                )
                history = [dict(message) for message in reversed(previous)]
                while history and history[0]["role"] != "user":
                    history.pop(0)
                async with connection.transaction():
                    first = await connection.fetchval("SELECT NOT EXISTS (SELECT 1 FROM messages WHERE conversation_id=$1)", chat_id)
                    await connection.execute(
                        "INSERT INTO messages (conversation_id, role, content) VALUES ($1, 'user', $2)", chat_id, question
                    )
                    await connection.execute(
                        "UPDATE conversations SET updated_at=now(), title=CASE WHEN $2 THEN $3 ELSE title END WHERE id=$1",
                        chat_id, first, question[:60],
                    )

                # 자료 상태를 확인해 검색 근거로 사용할 청크를 선별합니다.
                async def visible_chunks(chunks):
                    ids = [chunk.document_id for chunk in chunks if chunk.document_id]
                    names = [chunk.pdf_filename for chunk in chunks if chunk.pdf_filename and not chunk.document_id]
                    rows = await connection.fetch(
                        """SELECT id, filename, status, legacy FROM pdf_documents
                           WHERE collection=$1 AND (id=ANY($2::uuid[]) OR (legacy AND filename=ANY($3::text[])))""",
                        state.settings.weaviate_collection, ids, names,
                    )
                    ready = {row["id"] for row in rows if row["status"] == "ready"}
                    hidden = {row["filename"] for row in rows if row["legacy"] and row["status"] != "ready"}
                    return [
                        chunk for chunk in chunks
                        if (chunk.document_id in ready if chunk.document_id else chunk.pdf_filename not in hidden)
                    ]

                fragments = []
                sources = []
                saved = False
                try:
                    async with aclosing(state.rag.stream(question, history, visible_chunks)) as responses:
                        async for event, data in responses:
                            if event == "sources":
                                sources = data["items"]
                            elif event == "delta":
                                fragments.append(data["text"])
                            elif event == "done":
                                await connection.execute(
                                    """INSERT INTO messages (conversation_id, role, content, sources)
                                       VALUES ($1, 'assistant', $2, $3)""", chat_id, "".join(fragments), json.dumps(sources),
                                )
                                saved = True
                            yield encode_sse(event, data)
                finally:
                    if fragments and not saved:
                        with CancelScope(shield=True):
                            await connection.execute(
                                """INSERT INTO messages (conversation_id, role, content, sources, interrupted)
                                   VALUES ($1, 'assistant', $2, $3, true)""", chat_id, "".join(fragments), json.dumps(sources),
                            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("RAG 스트리밍 처리 실패")
            yield encode_sse("error", {"message": "답변 생성에 실패했습니다. 서버 상태를 확인해 주세요."})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no"})
