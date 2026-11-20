import asyncio
import logging
from pathlib import Path
import shutil
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Literal
from uuid import UUID, uuid4

from anyio import CancelScope
from fastapi import APIRouter, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from pypdf.errors import PyPdfError

from app.auth import Admin
from app.database import operation
from app.services.ollama_service import EmbeddingError
from app.services.rag_service import read_pdf_chunks

router = APIRouter(prefix="/api/pdfs")
logger = logging.getLogger(__name__)
FIELDS = "id, filename, size_bytes, uploaded_at, status, chunk_count"
ORDER = {"newest": "uploaded_at DESC", "oldest": "uploaded_at ASC", "name": "lower(filename), filename", "size": "size_bytes DESC"}


# 기존 업로드 파일을 PostgreSQL 문서 목록에 등록합니다.
async def import_existing_files(pool, directory: Path, collection: str) -> None:
    if not directory.is_dir():
        return
    for path in directory.iterdir():
        if path.suffix.lower() == ".pdf" and path.is_file() and not path.is_symlink():
            await pool.execute(
                """INSERT INTO pdf_documents (id, filename, collection, size_bytes, status, legacy)
                   VALUES ($1, $2, $3, $4, 'ready', true) ON CONFLICT (filename) DO NOTHING""",
                uuid4(), path.name, collection, path.stat().st_size,
            )


# PDF 원본을 업로드 폴더에 저장합니다.
def save_pdf(source: BinaryIO, path: Path) -> None:
    path.parent.mkdir(exist_ok=True)
    source.seek(0)
    with NamedTemporaryFile(dir=path.parent) as temporary:
        shutil.copyfileobj(source, temporary)
        temporary.flush()
        path.hardlink_to(temporary.name)


# 문서의 벡터, 원본 파일, 메타데이터를 정리합니다.
async def remove_document(connection, rag, path: Path, document) -> None:
    await rag.weaviate.delete_pdf(document["id"], document["filename"], document["collection"], document["legacy"])
    path.unlink(missing_ok=True)
    await connection.execute("DELETE FROM pdf_documents WHERE id=$1", document["id"])


# 파일명 검색과 정렬을 적용한 PDF 목록을 반환합니다.
@router.get("")
async def list_pdfs(
    request: Request, admin: Admin, q: str = Query(default="", max_length=255),
    sort: Literal["newest", "oldest", "name", "size"] = "newest",
):
    return await request.app.state.db.fetch(
        f"""SELECT {FIELDS} FROM pdf_documents WHERE strpos(lower(filename), lower($1)) > 0 OR $1 = ''
            ORDER BY {ORDER[sort]}, id""", q.strip(),
    )


# 관리자 PDF를 검증하고 원본 및 벡터를 저장합니다.
@router.post("", status_code=201)
async def upload_pdf(file: UploadFile, request: Request, admin: Admin):
    name = file.filename or ""
    if Path(name).suffix.lower() != ".pdf" or any(c in name for c in ("/", "\\", "\x00")):
        raise HTTPException(400, "PDF 파일을 선택해 주세요.")
    if len(name.encode("utf-8")) > 255:
        raise HTTPException(400, "파일 이름이 너무 깁니다.")
    if await file.read(5) != b"%PDF-":
        raise HTTPException(400, "유효한 PDF 파일이 아닙니다.")
    await file.seek(0)
    try:
        chunks = await run_in_threadpool(read_pdf_chunks, file.file)
    except (PyPdfError, ValueError) as error:
        raise HTTPException(400, "PDF를 읽을 수 없습니다.") from error
    if not chunks:
        raise HTTPException(422, "PDF에서 추출할 텍스트가 없습니다.")

    state = request.app.state
    path = state.uploads_dir / name
    async with operation(state.db, f"pdf:{name}") as connection:
        if connection is None or path.exists():
            raise HTTPException(409, "같은 이름의 PDF가 이미 있거나 처리 중입니다.")
        document = await connection.fetchrow(
            """INSERT INTO pdf_documents (id, filename, collection, size_bytes, status, uploaded_by)
               VALUES ($1, $2, $3, $4, 'indexing', $5) ON CONFLICT (filename) DO NOTHING RETURNING *""",
            uuid4(), name, state.settings.weaviate_collection, file.size or 0, admin["id"],
        )
        if not document:
            raise HTTPException(409, "같은 이름의 PDF가 이미 있거나 처리 중입니다.")

        saved = False
        indexing_started = False
        try:
            with CancelScope(shield=True):
                await run_in_threadpool(save_pdf, file.file, path)
                saved = True
            indexing_started = True
            await state.rag.index_pdf(document["id"], name, chunks)
            return await connection.fetchrow(
                f"UPDATE pdf_documents SET status='ready', chunk_count=$2 WHERE id=$1 RETURNING {FIELDS}",
                document["id"], len(chunks),
            )
        except (Exception, asyncio.CancelledError) as error:
            with CancelScope(shield=True):
                try:
                    if indexing_started:
                        await remove_document(connection, state.rag, path, document)
                    else:
                        if saved:
                            path.unlink(missing_ok=True)
                        await connection.execute("DELETE FROM pdf_documents WHERE id=$1", document["id"])
                except Exception:
                    logger.exception("PDF 정리 실패: %s", document["id"])
            if isinstance(error, asyncio.CancelledError):
                raise
            if isinstance(error, EmbeddingError):
                raise HTTPException(503, str(error)) from error
            logger.exception("PDF 업로드 실패: %s", document["id"])
            raise HTTPException(502, "PDF 저장에 실패했습니다. 자료 목록을 확인해 주세요.") from error


# 선택한 PDF와 연결된 벡터를 삭제합니다.
@router.delete("/{document_id}", status_code=204)
async def delete_pdf(document_id: UUID, request: Request, admin: Admin):
    state = request.app.state
    document = await state.db.fetchrow("SELECT filename FROM pdf_documents WHERE id=$1", document_id)
    if not document:
        return
    name = document["filename"]
    async with operation(state.db, f"pdf:{name}") as connection:
        if connection is None:
            raise HTTPException(409, "문서가 처리 중입니다. 잠시 후 다시 시도해 주세요.")
        document = await connection.fetchrow(
            "UPDATE pdf_documents SET status='deleting' WHERE id=$1 RETURNING *", document_id
        )
        if document:
            try:
                await remove_document(connection, state.rag, state.uploads_dir / name, document)
            except Exception as error:
                logger.exception("PDF 삭제 실패: %s", document_id)
                raise HTTPException(502, "자료 삭제를 완료하지 못했습니다. 다시 시도해 주세요.") from error
