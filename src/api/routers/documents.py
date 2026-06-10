"""Document upload and listing endpoints."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from common.upload_filename import sanitize_upload_filename
from src.api.deps import get_documents_service, get_ingest_service
from src.api.schemas import DocumentDTO, DocumentDetailDTO
from src.services.documents import DocumentDetail, DocumentsService
from src.services.ingest import IngestService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])


def _to_dto(doc: object) -> DocumentDTO:
    return DocumentDTO(
        id=doc.document_id,  # type: ignore[attr-defined]
        source_path=doc.source_path,  # type: ignore[attr-defined]
        category=doc.category,  # type: ignore[attr-defined]
        document_date=doc.document_date,  # type: ignore[attr-defined]
        indexed_at=doc.indexed_at,  # type: ignore[attr-defined]
    )


def _to_detail_dto(doc: DocumentDetail) -> DocumentDetailDTO:
    return DocumentDetailDTO(**_to_dto(doc.metadata).model_dump(), content=doc.content)


@router.post("", response_model=DocumentDTO, status_code=201)
async def upload_document(
    file: UploadFile = File(...),
    service: IngestService = Depends(get_ingest_service),
) -> DocumentDTO:
    raw = await file.read()
    filename = sanitize_upload_filename(file.filename)
    logger.info("Document upload: filename=%s size=%d", filename, len(raw))
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=422, detail="File must be UTF-8 encoded Markdown text"
        )
    doc = await service.ingest_document(content, original_filename=filename)
    return _to_dto(doc)


@router.get("", response_model=list[DocumentDTO])
async def list_documents(
    service: DocumentsService = Depends(get_documents_service),
) -> list[DocumentDTO]:
    docs = await service.list_documents()
    return [_to_dto(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentDetailDTO)
async def get_document(
    document_id: str,
    service: DocumentsService = Depends(get_documents_service),
) -> DocumentDetailDTO:
    doc = await service.get_document(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id!r} not found")
    return _to_detail_dto(doc)


@router.delete("/{document_id}", status_code=204)
async def delete_document(
    document_id: str,
    service: DocumentsService = Depends(get_documents_service),
) -> None:
    await service.delete_document(document_id)
