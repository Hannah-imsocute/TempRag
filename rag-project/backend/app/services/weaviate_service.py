"""기존 Weaviate 컬렉션에서 사용자 질문과 유사한 문서 텍스트를 읽습니다."""
import json
from typing import Any

from app.schemas import RetrievedChunk
from weaviate import WeaviateAsyncClient
from weaviate.classes.query import MetadataQuery


def first_nonempty(properties: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = properties.get(key)
        if value is not None and value != "":
            return value
    return None


def extract_text(properties: dict[str, Any], text_property: str) -> str:
    # 일반 PDF 청킹 스키마(text/content 등)와 LlamaIndex의 _node_content를 지원합니다.
    value = first_nonempty(properties, text_property, "text", "content", "page_content", "chunk", "body")
    if isinstance(value, str) and value.strip():
        return value.strip()
    node = properties.get("_node_content")
    if isinstance(node, str):
        try:
            parsed = json.loads(node)
            if isinstance(parsed, dict):
                return str(parsed.get("text") or "").strip()
        except json.JSONDecodeError:
            pass
    return ""


class WeaviateService:
    def __init__(self, client: WeaviateAsyncClient, collection: str, text_property: str):
        self.client = client
        self.collection = collection
        self.text_property = text_property

    async def search(self, vector: list[float], limit: int) -> list[RetrievedChunk]:
        collection = self.client.collections.use(self.collection)
        response = await collection.query.near_vector(
            near_vector=vector,
            limit=limit,
            return_metadata=MetadataQuery(distance=True),
        )
        found: list[RetrievedChunk] = []
        for obj in response.objects:
            props = obj.properties or {}
            text = extract_text(props, self.text_property)
            if not text:
                continue
            metadata = props.get("metadata") if isinstance(props.get("metadata"), dict) else {}
            title = (
                first_nonempty(props, "file_name", "filename", "document_name", "source", "title")
                or first_nonempty(metadata, "file_name", "filename", "document_name", "source", "title")
                or "학교 규정 문서"
            )
            page = first_nonempty(props, "page_label", "page", "page_number") or first_nonempty(
                metadata, "page_label", "page", "page_number"
            )
            distance = obj.metadata.distance if obj.metadata else None
            found.append(
                RetrievedChunk(
                    text=text,
                    title=str(title),
                    page=str(page) if page is not None else None,
                    distance=round(float(distance), 4) if distance is not None else None,
                )
            )
        return found
