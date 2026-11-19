"""Weaviate에 문서 벡터를 저장하고 질문과 유사한 문서 텍스트를 읽습니다."""
import json
from typing import Any
from uuid import UUID, uuid4

from app.schemas import RetrievedChunk
from weaviate import WeaviateAsyncClient
from weaviate.classes.config import DataType, Property
from weaviate.classes.data import DataObject
from weaviate.classes.query import Filter, MetadataQuery
from weaviate.exceptions import UnexpectedStatusCodeError

WRITE_BATCH_SIZE = 64


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

    async def ensure_pdf_properties(self) -> None:
        config = self.client.collections.use(self.collection).config
        existing = {prop.name for prop in (await config.get()).properties}
        for name, data_type in (
            (self.text_property, DataType.TEXT),
            ("pdfFileName", DataType.TEXT),
            ("pdfPageNumber", DataType.INT),
            ("pdfDocumentId", DataType.UUID),
        ):
            if name not in existing:
                try:
                    await config.add_property(Property(name=name, data_type=data_type))
                except UnexpectedStatusCodeError as error:
                    if error.status_code != 422 or not any(
                        prop.name == name for prop in (await config.get()).properties
                    ):
                        raise

    async def store_pdf(self, document_id: UUID, name: str, chunks: list[tuple[int, str, list[float]]]) -> None:
        collection = self.client.collections.use(self.collection)
        for start in range(0, len(chunks), WRITE_BATCH_SIZE):
            objects = [
                DataObject(
                    uuid=uuid4(),
                    properties={
                        self.text_property: text, "pdfFileName": name,
                        "pdfPageNumber": page, "pdfDocumentId": document_id,
                    },
                    vector=vector,
                )
                for page, text, vector in chunks[start:start + WRITE_BATCH_SIZE]
            ]
            result = await collection.data.insert_many(objects)
            if result.has_errors:
                raise RuntimeError(f"Weaviate PDF insert failed for {len(result.errors)} chunks")

    async def delete_pdf(self, document_id: UUID, name: str, collection_name: str, legacy: bool) -> None:
        if not await self.client.collections.exists(collection_name):
            return
        collection = self.client.collections.use(collection_name)
        if not legacy:
            await self.delete_vectors(collection, Filter.by_property("pdfDocumentId").equal(document_id))
            return
        # Older vectors have a filename but no document ID. Compare the entire name,
        # since the existing text property's tokenization may match other filenames.
        properties = {prop.name for prop in (await collection.config.get()).properties}
        if "pdfFileName" not in properties:
            return
        ids = [
            obj.uuid async for obj in collection.iterator(return_properties=list(properties & {"pdfFileName", "pdfDocumentId"}))
            if obj.properties.get("pdfFileName") == name and not obj.properties.get("pdfDocumentId")
        ]
        for start in range(0, len(ids), WRITE_BATCH_SIZE):
            await self.delete_vectors(collection, Filter.by_id().contains_any(ids[start:start + WRITE_BATCH_SIZE]))

    @staticmethod
    async def delete_vectors(collection, where) -> None:
        while True:
            result = await collection.data.delete_many(where)
            if result.failed or (result.matches and not result.successful):
                raise RuntimeError("Weaviate PDF vector deletion failed")
            if result.matches == result.successful:
                return

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
                first_nonempty(props, "pdfFileName", "file_name", "filename", "document_name", "source", "title")
                or first_nonempty(metadata, "file_name", "filename", "document_name", "source", "title")
                or "학교 규정 문서"
            )
            page = first_nonempty(props, "pdfPageNumber", "page_label", "page", "page_number") or first_nonempty(
                metadata, "page_label", "page", "page_number"
            )
            distance = obj.metadata.distance if obj.metadata else None
            found.append(
                RetrievedChunk(
                    text=text,
                    title=str(title),
                    page=str(page) if page is not None else None,
                    distance=round(float(distance), 4) if distance is not None else None,
                    document_id=UUID(str(props["pdfDocumentId"])) if props.get("pdfDocumentId") else None,
                    pdf_filename=props.get("pdfFileName"),
                )
            )
        return found
