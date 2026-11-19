"""API는 HTTP/SSE 입출력만 담당하고, 실제 RAG 처리는 서비스에 위임합니다."""
import asyncio
from contextlib import asynccontextmanager
import logging
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile

from fastapi import FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import httpx

from app.config import Settings
from app.schemas import ChatRequest
from app.sse import encode_sse
from app.services.ollama_service import OllamaService
from app.services.rag_service import RagService

logger = logging.getLogger(__name__)
settings = Settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 외부 DB 드라이버는 서버가 시작할 때 로딩됩니다. API 테스트에서는 실제 DB 연결이 필요 없습니다.
    import weaviate
    from weaviate.classes.config import Configure, DataType, Property
    from weaviate.classes.init import AdditionalConfig, Timeout
    from weaviate.exceptions import UnexpectedStatusCodeError
    from app.services.weaviate_service import WeaviateService

    # 요청마다 클라이언트를 재연결하지 않고 애플리케이션 수명 동안 재사용합니다.
    async with httpx.AsyncClient(
        base_url=settings.ollama_base_url.rstrip("/"),
        timeout=httpx.Timeout(240.0, connect=10.0),
    ) as ollama_http:
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
            app.state.rag = RagService(
                ollama=OllamaService(ollama_http, settings.embedding_model, settings.llm_model),
                weaviate=WeaviateService(
                    weaviate_client, settings.weaviate_collection, settings.weaviate_text_property
                ),
                settings=settings,
            )
            yield
        finally:
            await weaviate_client.close()


app = FastAPI(title="학교 규정 RAG 챗봇", lifespan=lifespan)

project_dir = Path(__file__).resolve().parents[2]
uploads_dir = project_dir / "uploads"
static_dir = project_dir / "static"
if not static_dir.is_dir():
    static_dir = project_dir / "frontend" / "dist"

assets_dir = static_dir / "assets"
if assets_dir.is_dir():
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/", include_in_schema=False)
def index():
    index_file = static_dir / "index.html"
    if not index_file.is_file():
        raise HTTPException(status_code=404, detail="프런트엔드 빌드가 없습니다.")
    return FileResponse(index_file)


@app.get("/api/health")
async def health():
    # 이 API는 FastAPI 프로세스 응답 여부만 확인합니다(외부 AI 서비스의 상태 검사는 아님).
    return {"status": "ok"}


@app.get("/api/pdfs")
def list_pdfs() -> list[str]:
    if not uploads_dir.is_dir():
        return []
    return sorted(
        file.name for file in uploads_dir.iterdir()
        if file.is_file() and file.suffix.lower() == ".pdf"
    )


@app.post("/api/pdfs", status_code=201)
def upload_pdf(file: UploadFile) -> str:
    name = file.filename or ""
    if Path(name).suffix.lower() != ".pdf" or any(c in name for c in ("/", "\\", "\x00")):
        raise HTTPException(status_code=400, detail="PDF 파일을 선택해 주세요.")
    if len(name.encode("utf-8")) > 255:
        raise HTTPException(status_code=400, detail="파일 이름이 너무 깁니다.")
    if file.file.read(5) != b"%PDF-":
        raise HTTPException(status_code=400, detail="유효한 PDF 파일이 아닙니다.")
    file.file.seek(0)
    uploads_dir.mkdir(exist_ok=True)
    with NamedTemporaryFile(dir=uploads_dir) as temporary:
        shutil.copyfileobj(file.file, temporary)
        temporary.flush()
        try:
            (uploads_dir / name).hardlink_to(temporary.name)
        except FileExistsError:
            raise HTTPException(status_code=409, detail="같은 이름의 PDF가 이미 있습니다.") from None
    return name


@app.post("/api/chat/stream")
async def stream_chat(body: ChatRequest, request: Request):
    question = body.question.strip()

    async def events():
        try:
            if not question:
                yield encode_sse("error", {"message": "질문을 입력해 주세요."})
                return
            async for event_name, data in request.app.state.rag.stream(question):
                if await request.is_disconnected():
                    return
                yield encode_sse(event_name, data)
        except asyncio.CancelledError:
            raise  # 프런트에서 생성 중단 시 불필요한 작업을 계속하지 않음
        except Exception:
            logger.exception("RAG 스트리밍 처리 실패")
            # 서버 주소나 내부 환경 변수 등 민감한 오류 메시지를 브라우저에 노출하지 않습니다.
            yield encode_sse("error", {"message": "답변 생성에 실패했습니다. 서버 로그를 확인해 주세요."})

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",  # Nginx가 청크를 모아서 보내지 않게 함
            "Connection": "keep-alive",
        },
    )
