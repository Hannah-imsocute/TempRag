from dataclasses import dataclass
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    conversation_id: UUID
    question: str = Field(min_length=1, max_length=3000)


@dataclass(frozen=True)
class RetrievedChunk:
    text: str
    title: str
    page: str | None
    distance: float | None
    document_id: UUID | None = None
    pdf_filename: str | None = None
