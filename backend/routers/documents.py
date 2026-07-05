"""Endpoints for uploading, listing, and deleting documents."""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from langchain_community.vectorstores import Chroma
from sqlalchemy.orm import Session

import database
from models.schemas import (
    DeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    UploadResponse,
    UploadResult,
)
from services import auth_service, chroma_service, rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post(
    "/upload",
    response_model=UploadResponse,
    summary="Upload and ingest PDF documents",
    description=(
        "Accepts one or more PDF files, chunks and embeds each one, and "
        "stores the chunks in the vector store. Each file is processed "
        "independently: one corrupt or scanned/unreadable PDF in a batch "
        "does not stop the others from being ingested — check `results` "
        "for the per-file outcome."
    ),
)
async def upload_documents(
    files: list[UploadFile] = File(..., description="One or more PDF files to ingest."),
    vectordb: Chroma = Depends(chroma_service.get_vectordb),
    db: Session = Depends(database.get_db),
    user_id: str = Depends(auth_service.get_current_user),
) -> UploadResponse:
    """Chunk, embed, and store each uploaded PDF in the vector store."""
    logger.info("Upload request received for %d file(s)", len(files))
    results: list[UploadResult] = []
    total_chunks = 0

    for upload in files:
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            results.append(
                UploadResult(
                    filename=upload.filename or "unknown",
                    status="failed",
                    detail="Only PDF files are supported.",
                )
            )
            continue

        try:
            file_bytes = await upload.read()
            chunk_count = rag_service.process_pdf(file_bytes, upload.filename, vectordb, user_id)
            results.append(
                UploadResult(filename=upload.filename, status="success", chunk_count=chunk_count)
            )
            total_chunks += chunk_count

            # Persisting the ingestion record is bookkeeping, not core
            # ingestion — a database hiccup (bad DATABASE_URL, Supabase
            # unreachable) must never turn a successfully embedded
            # document into a reported failure, so log and swallow rather
            # than letting it bubble into the except Exception below.
            try:
                database.log_document(db, upload.filename, chunk_count, user_id)
            except Exception:
                logger.error("Could not log document '%s' to the database", upload.filename, exc_info=True)
                # A failed commit leaves the session mid-transaction —
                # roll back so the next file in this same batch (which
                # reuses this request-scoped session) can still attempt
                # its own log_document call instead of inheriting a
                # broken transaction.
                db.rollback()
        except rag_service.PDFProcessingError as exc:
            logger.warning("Failed to process '%s': %s", upload.filename, exc)
            results.append(
                UploadResult(filename=upload.filename, status="failed", detail=str(exc))
            )
        except Exception:
            logger.exception("Unexpected error processing '%s'", upload.filename)
            results.append(
                UploadResult(
                    filename=upload.filename,
                    status="failed",
                    detail="Unexpected server error while processing this file.",
                )
            )

    return UploadResponse(results=results, total_chunks=total_chunks)


@router.get(
    "/",
    response_model=DocumentListResponse,
    summary="List ingested documents",
    description="Returns every distinct document currently stored in the vector store, with its chunk count.",
)
def list_documents(
    vectordb: Chroma = Depends(chroma_service.get_vectordb),
    user_id: str = Depends(auth_service.get_current_user),
) -> DocumentListResponse:
    """Return every distinct document currently stored in the vector store for the current user."""
    logger.info("Document list requested")
    try:
        documents = rag_service.list_documents(vectordb, user_id)
    except Exception:
        logger.exception("Failed to list documents")
        raise HTTPException(status_code=500, detail="Could not retrieve the document list.")
    return DocumentListResponse(documents=[DocumentInfo(**doc) for doc in documents])


@router.delete(
    "/{filename}",
    response_model=DeleteResponse,
    summary="Delete a document",
    description="Removes every chunk belonging to the given filename from the vector store.",
)
def delete_document(
    filename: str,
    vectordb: Chroma = Depends(chroma_service.get_vectordb),
    db: Session = Depends(database.get_db),
    user_id: str = Depends(auth_service.get_current_user),
) -> DeleteResponse:
    """Remove every chunk belonging to `filename` from the vector store, scoped to the current user."""
    logger.info("Delete requested for '%s'", filename)
    try:
        existing = rag_service.list_documents(vectordb, user_id)
        if not any(doc["filename"] == filename for doc in existing):
            raise HTTPException(status_code=404, detail=f"No document named '{filename}' found.")
        # $and is required here (rather than a plain two-key dict) because
        # Chroma's `where` only accepts a single top-level operator — see
        # rag_service for the single-key filter case that doesn't need it.
        # Filtering by user_id (not just source) prevents one user's
        # delete from ever touching another user's same-named upload.
        vectordb.delete(where={"$and": [{"source": filename}, {"user_id": user_id}]})
    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to delete '%s'", filename)
        raise HTTPException(status_code=500, detail=f"Could not delete '{filename}'.")

    # Mirror the deletion in the documents table. Bookkeeping, like
    # log_document on the upload path — a database hiccup here must not
    # turn an already-successful Chroma deletion into a reported failure.
    try:
        database.delete_document_record(db, filename, user_id)
    except Exception:
        logger.error("Could not remove '%s' from the documents table", filename, exc_info=True)
        db.rollback()

    logger.info("Deleted document '%s'", filename)
    return DeleteResponse(filename=filename, message=f"'{filename}' was removed.")
