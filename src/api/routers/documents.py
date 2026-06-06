"""Document upload and listing endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from src.api.deps import get_documents_service, get_ingest_service
from src.api.schemas import DocumentDTO
from src.services.documents import DocumentsService
from src.services.ingest import IngestService

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _to_dto(doc: object) -> DocumentDTO:
    return DocumentDTO(
        id=doc.document_id,  # type: ignore[attr-defined]
        category=doc.category,  # type: ignore[attr-defined]
        document_date=doc.document_date,  # type: ignore[attr-defined]
        indexed_at=doc.indexed_at,  # type: ignore[attr-defined]
    )


@router.post("", response_model=DocumentDTO, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service: IngestService = Depends(get_ingest_service),
) -> DocumentDTO:
    raw = await file.read()
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        # Not an AppError — this is an input validation error at the HTTP boundary.
        raise HTTPException(
            status_code=422, detail="File must be UTF-8 encoded Markdown text"
        )
    doc = await service.ingest_document(content)
    return _to_dto(doc)


@router.get("", response_model=list[DocumentDTO])
async def list_documents(
    service: DocumentsService = Depends(get_documents_service),
) -> list[DocumentDTO]:
    docs = await service.list_documents()
    return [_to_dto(d) for d in docs]


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    service: DocumentsService = Depends(get_documents_service),
) -> None:
    await service.delete_document(document_id)
