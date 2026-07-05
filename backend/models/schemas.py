"""Pydantic request/response models shared across routers.

Field descriptions here double as the auto-generated Swagger UI (/docs)
documentation for every request/response body, so they're written for a
reader who has never seen the code.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """One turn in a conversation, used only to resolve follow-up questions."""

    role: str = Field(..., description="Who sent the message: 'user' or 'assistant'.")
    content: str = Field(..., description="The message text.")


class ChatRequest(BaseModel):
    """Request body for POST /chat/ask."""

    question: str = Field(
        ..., min_length=1, description="The question to answer, as typed by the user."
    )
    session_id: str = Field(
        ..., description="Client-generated identifier grouping turns into one conversation."
    )
    conversation_history: List[ChatMessage] = Field(
        default_factory=list,
        description=(
            "Prior turns in this session, oldest first. Used to rewrite an "
            "elliptical follow-up (e.g. 'what about maternity?') into a "
            "standalone query before retrieval — the answer itself is "
            "still generated from `question` as asked."
        ),
    )


class ChatResponse(BaseModel):
    """Response body for POST /chat/ask."""

    answer: str = Field(
        ...,
        description=(
            "The generated answer, or a fixed fallback message if neither "
            "the uploaded documents nor a web search had anything relevant "
            "to answer from."
        ),
    )
    sources: List[str] = Field(
        default_factory=list,
        description=(
            "De-duplicated citations for what the answer was grounded in — "
            "'filename (p. N)' for document chunks, or a URL for web "
            "search results. Use `source_type` to tell which citations in "
            "this list are which (a URL is always a web source; anything "
            "else is a document source)."
        ),
    )
    source_type: str = Field(
        ...,
        description=(
            "Which source(s) the answer was routed to and grounded in: "
            "'document' (uploaded documents only), 'web' (live web search "
            "only), or 'both'."
        ),
    )


class DocumentInfo(BaseModel):
    """Metadata about one document currently stored in the vector store."""

    filename: str = Field(..., description="Original filename as uploaded.")
    chunk_count: int = Field(..., description="Number of chunks this document was split into.")
    upload_timestamp: Optional[str] = Field(
        None, description="ISO-8601 timestamp of when the document was ingested."
    )


class DocumentListResponse(BaseModel):
    """Response body for GET /documents/."""

    documents: List[DocumentInfo]


class UploadResult(BaseModel):
    """Per-file outcome within a batch upload — one upload request can
    partially succeed, so each file's result is reported individually
    rather than failing the whole request for one bad PDF.
    """

    filename: str
    status: str = Field(..., description="'success' or 'failed'.")
    chunk_count: Optional[int] = Field(None, description="Set when status is 'success'.")
    detail: Optional[str] = Field(None, description="Reason for failure, set when status is 'failed'.")


class UploadResponse(BaseModel):
    """Response body for POST /documents/upload."""

    results: List[UploadResult]
    total_chunks: int = Field(..., description="Sum of chunk_count across all successful files.")


class DeleteResponse(BaseModel):
    """Response body for DELETE /documents/{filename}."""

    filename: str
    message: str


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = Field(..., description="'ok' when the service is up and able to serve requests.")
