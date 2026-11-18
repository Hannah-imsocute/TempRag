"""질문 -> 임베딩 -> 유사도 검색 -> 문맥 구성 -> LLM 스트리밍 순서를 조립합니다."""
from __future__ import annotations
from collections.abc import AsyncIterator

from app.config import Settings
from app.services.ollama_service import OllamaService
from app.schemas import RetrievedChunk
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.weaviate_service import WeaviateService


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

    async def stream(self, question: str) -> AsyncIterator[tuple[str, dict]]:
        # status: 검색 전 대기 상태에서도 사용자가 작업 진행을 알 수 있습니다.
        yield "status", {"message": "질문을 임베딩하고 있습니다..."}
        vector = await self.ollama.embed(question)

        yield "status", {"message": "학교 규정을 검색하고 있습니다..."}
        chunks = await self.weaviate.search(vector, self.settings.search_top_k)
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
        async for text in self.ollama.stream_answer(question, context):
            generated = True
            yield "delta", {"text": text}
        if not generated:
            raise RuntimeError("LLM이 답변을 생성하지 않았습니다.")
        yield "done", {}
