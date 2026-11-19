"""질문 -> 임베딩 -> 유사도 검색 -> 문맥 구성 -> LLM 스트리밍 순서를 조립합니다."""
from __future__ import annotations
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

from app.config import Settings
from app.services.ollama_service import OllamaService
from app.schemas import RetrievedChunk
from typing import BinaryIO, TYPE_CHECKING

from pypdf import PdfReader

if TYPE_CHECKING:
    from app.services.weaviate_service import WeaviateService

EMBEDDING_BATCH_SIZE = 4


def read_pdf_chunks(file: BinaryIO) -> list[tuple[int, str]]:
    reader = PdfReader(file)
    if reader.is_encrypted:
        raise ValueError("Encrypted PDF")
    chunks = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = " ".join((page.extract_text() or "").split())
        for start in range(0, len(text), 850):
            chunks.append((page_number, text[start:start + 1000]))
            if start + 1000 >= len(text):
                break
    return chunks


def build_context(chunks: list[RetrievedChunk], max_chars: int) -> str:
    """과도하게 긴 PDF 청크 때문에 LLM 문맥 창을 초과하지 않도록 자릅니다."""
    sections = []
    remaining = max_chars
    for i, chunk in enumerate(chunks, start=1):
        prefix = f"[{i}] 출처: {chunk.title}" + (f", 페이지: {chunk.page}" if chunk.page else "") + "\n"
        capacity = remaining - len(prefix) - 1
        if capacity <= 0:
            break
        text = chunk.text[:capacity]
        section = prefix + text + "\n"
        sections.append(section)
        remaining -= len(section)
    return "".join(sections)


class RagService:
    def __init__(self, ollama: OllamaService, weaviate: WeaviateService, settings: Settings):
        self.ollama = ollama
        self.weaviate = weaviate
        self.settings = settings

    async def index_pdf(self, document_id: UUID, name: str, chunks: list[tuple[int, str]]) -> None:
        embedded = []
        for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
            batch = chunks[start:start + EMBEDDING_BATCH_SIZE]
            vectors = await self.ollama.embed_many([text for _, text in batch])
            embedded.extend(
                (page, text, vector) for (page, text), vector in zip(batch, vectors, strict=True)
            )
        await self.weaviate.store_pdf(document_id, name, embedded)

    async def stream(
        self, question: str, history: list[dict[str, str]],
        visible_chunks: Callable[[list[RetrievedChunk]], Awaitable[list[RetrievedChunk]]],
    ) -> AsyncIterator[tuple[str, dict]]:
        # status: 검색 전 대기 상태에서도 사용자가 작업 진행을 알 수 있습니다.
        yield "status", {"message": "질문을 임베딩하고 있습니다..."}
        vector = await self.ollama.embed(question)

        yield "status", {"message": "학교 규정을 검색하고 있습니다..."}
        limit = self.settings.search_top_k
        candidates = await self.weaviate.search(vector, limit * 3)
        chunks = (await visible_chunks(candidates))[:limit]
        sources = [
            {"index": index, "title": chunk.title, "page": chunk.page, "distance": chunk.distance}
            for index, chunk in enumerate(chunks, start=1)
        ]
        yield "sources", {"items": sources}

        if not chunks:
            yield "delta", {"text": "관련 학교 규정을 찾지 못했습니다. 문서 저장 여부와 질문을 확인해 주세요."}
            yield "done", {}
            return

        yield "status", {"message": "검색된 규정으로 답변을 작성하고 있습니다..."}
        context = build_context(chunks, self.settings.max_context_chars)
        generated = False
        async for text in self.ollama.stream_answer(question, context, history):
            generated = True
            yield "delta", {"text": text}
        if not generated:
            raise RuntimeError("LLM이 답변을 생성하지 않았습니다.")
        yield "done", {}
