"""React와 FastAPI가 주고받는 요청 형태를 정의합니다."""
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    # 최대 길이 제한으로 매우 큰 입력을 무분별하게 임베딩하지 않도록 합니다.
    question: str = Field(min_length=1, max_length=3000)


from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """Weaviate 데이터 구조와 RAG 로직 사이의 공통 문서 형식입니다."""
    text: str
    title: str
    page: str | None
    distance: float | None
