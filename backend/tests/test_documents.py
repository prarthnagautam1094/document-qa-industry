"""Covers the document ingestion lifecycle: upload, list, and delete.

This is the entry point for all data into the system — if upload
silently corrupts chunk counts, if one bad file in a batch crashes the
whole request instead of failing gracefully per-file, or if delete
doesn't actually remove a document's vectors from the store, every
downstream RAG answer is affected. These tests exercise the real
PDF-processing and Chroma-storage pipeline end to end (a real PDF is
parsed, chunked, and embedded), not a mocked stand-in for it.

Each test uploads its own uniquely-named document and cleans it up
itself, rather than sharing one across tests — document lifecycle
(create/list/delete) is exactly what's under test here, so tests need
independent control over that lifecycle rather than a shared fixture
that would make one test's delete affect another's list.
"""

from database import Document, SessionLocal


def test_upload_valid_pdf_succeeds(client, sample_pdf_bytes, unique_filename):
    response = client.post(
        "/documents/upload",
        files=[("files", (unique_filename, sample_pdf_bytes, "application/pdf"))],
    )
    assert response.status_code == 200

    body = response.json()
    assert len(body["results"]) == 1
    result = body["results"][0]
    assert result["filename"] == unique_filename
    assert result["status"] == "success"
    assert result["chunk_count"] > 0
    assert body["total_chunks"] == result["chunk_count"]

    client.delete(f"/documents/{unique_filename}")


def test_upload_non_pdf_fails_gracefully(client, unique_filename):
    txt_filename = unique_filename.replace(".pdf", ".txt")
    response = client.post(
        "/documents/upload",
        files=[("files", (txt_filename, b"just plain text, not a pdf", "text/plain"))],
    )
    # The endpoint itself must not error out — a bad file in the batch is
    # reported as a per-file failure inside a normal 200 response, not a
    # crash that would also take down any *other* valid files in the
    # same request.
    assert response.status_code == 200
    result = response.json()["results"][0]
    assert result["status"] == "failed"
    assert result["chunk_count"] is None
    assert "PDF" in result["detail"]


def test_list_documents_includes_uploaded_file(client, sample_pdf_bytes, unique_filename):
    client.post(
        "/documents/upload",
        files=[("files", (unique_filename, sample_pdf_bytes, "application/pdf"))],
    )

    response = client.get("/documents/")
    assert response.status_code == 200
    filenames = [doc["filename"] for doc in response.json()["documents"]]
    assert unique_filename in filenames

    client.delete(f"/documents/{unique_filename}")


def test_delete_document_removes_it_from_list(client, sample_pdf_bytes, unique_filename):
    client.post(
        "/documents/upload",
        files=[("files", (unique_filename, sample_pdf_bytes, "application/pdf"))],
    )

    delete_response = client.delete(f"/documents/{unique_filename}")
    assert delete_response.status_code == 200
    assert delete_response.json()["filename"] == unique_filename

    list_response = client.get("/documents/")
    filenames = [doc["filename"] for doc in list_response.json()["documents"]]
    assert unique_filename not in filenames


def test_delete_nonexistent_document_returns_404(client, unique_filename):
    # unique_filename was never uploaded, so this exercises the
    # not-found path rather than a real deletion.
    response = client.delete(f"/documents/{unique_filename}")
    assert response.status_code == 404


def test_delete_document_removes_its_postgres_row(client, sample_pdf_bytes, unique_filename):
    # Regression test: delete_document previously only removed a
    # document's chunks from Chroma and never touched its row in the
    # Postgres `documents` table, so every deletion left a permanent
    # orphaned audit row behind. Covers both stores explicitly so this
    # can't silently regress.
    client.post(
        "/documents/upload",
        files=[("files", (unique_filename, sample_pdf_bytes, "application/pdf"))],
    )

    db = SessionLocal()
    try:
        assert db.query(Document).filter(Document.filename == unique_filename).count() == 1
    finally:
        db.close()

    client.delete(f"/documents/{unique_filename}")

    db = SessionLocal()
    try:
        assert db.query(Document).filter(Document.filename == unique_filename).count() == 0
    finally:
        db.close()
