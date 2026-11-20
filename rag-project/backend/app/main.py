from contextlib import asynccontextmanager
from pathlib import Path

import asyncpg
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx

from app.config import Settings
from app import auth, chats, documents
from app.database import initialize
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

settings = Settings()


# 앱 시작과 종료 시 공용 연결과 서비스를 관리합니다.
@asynccontextmanager
async def lifespan(app: FastAPI):
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property
    from weaviate.classes.init import AdditionalConfig, Timeout
    from weaviate.exceptions import UnexpectedStatusCodeError
    from app.services.weaviate_service import WeaviateService

    async with asyncpg.create_pool(
        host=settings.postgres_host, port=settings.postgres_port, user=settings.postgres_user,
        password=settings.postgres_password, database=settings.postgres_db, min_size=1, max_size=20, command_timeout=15,
    ) as pool, httpx.AsyncClient(
        base_url=settings.ollama_base_url.rstrip("/"),
        timeout=httpx.Timeout(240.0, connect=10.0),
    ) as ollama_http:
        await initialize(pool)
        await auth.bootstrap_admin(pool, settings)
        app.state.db = pool
        app.state.settings = settings
        app.state.uploads_dir = uploads_dir
        weaviate_client = weaviate.use_async_with_custom(
            http_host=settings.weaviate_http_host,
            http_port=settings.weaviate_http_port,
            http_secure=False,
            grpc_host=settings.weaviate_grpc_host,
            grpc_port=settings.weaviate_grpc_port,
            grpc_secure=False,
            additional_config=AdditionalConfig(timeout=Timeout(init=15, query=45, insert=45)),
        )
        try:
            await weaviate_client.connect()
            collections = weaviate_client.collections
            if not await collections.exists(settings.weaviate_collection):
                try:
                    await collections.create(
                        settings.weaviate_collection,
                        vector_config=Configure.Vectors.self_provided(),
                        properties=[Property(name=settings.weaviate_text_property, data_type=DataType.TEXT)],
                    )
                except UnexpectedStatusCodeError as error:
                    if error.status_code != 422 or not await collections.exists(settings.weaviate_collection):
                        raise
            vector_store = WeaviateService(
                weaviate_client, settings.weaviate_collection, settings.weaviate_text_property
            )
            await vector_store.ensure_pdf_properties()
            await documents.import_existing_files(pool, uploads_dir, settings.weaviate_collection)
            app.state.rag = RagService(
                ollama=OllamaService(ollama_http, settings.embedding_model, settings.llm_model),
                weaviate=vector_store,
                settings=settings,
            )
            yield
        finally:
            await weaviate_client.close()


app = FastAPI(title="학교 규정 RAG 챗봇", lifespan=lifespan)
app.include_router(auth.router)
app.include_router(chats.router)
app.include_router(documents.router)


# API 요청의 출처와 응답 캐시 정책을 처리합니다.
@app.middleware("http")
async def protect_api(request: Request, call_next):
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.headers.get("sec-fetch-site") in {"cross-site", "same-site"}:
        return JSONResponse({"detail": "같은 사이트에서 요청해 주세요."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response

project_dir = Path(__file__).resolve().parents[2]
uploads_dir = project_dir / "uploads"
static_dir = project_dir / "static"
if not static_dir.is_dir():
    static_dir = project_dir / "frontend" / "dist"

assets_dir = static_dir / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# 빌드된 프런트엔드 진입 페이지를 반환합니다.
@app.get("/", include_in_schema=False)
def index():
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="프런트엔드 빌드가 없습니다.")
    return FileResponse(index_file)


# FastAPI가 요청에 응답할 수 있는지 확인합니다.
@app.get("/api/health")
async def health():
    return {"status": "ok"}
