"""API는 HTTP/SSE 입출력만 담당하고, 실제 RAG 처리는 서비스에 위임합니다."""
import asyncio
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
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
    from weaviate.classes.init import AdditionalConfig, Timeout
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


@app.get("/api/health")
async def health():
    # 이 API는 FastAPI 프로세스 응답 여부만 확인합니다(외부 AI 서비스의 상태 검사는 아님).
    return {"status": "ok"}


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
