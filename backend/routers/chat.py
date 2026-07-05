"""Endpoint for asking questions against the ingested documents."""

import logging
import time

from fastapi import APIRouter, Depends, HTTPException
from langchain_community.vectorstores import Chroma
from sqlalchemy.orm import Session

import database
from models.schemas import ChatRequest, ChatResponse
from services import auth_service, chroma_service, rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/ask",
    response_model=ChatResponse,
    summary="Ask a question about the ingested documents",
    description=(
        "Answers a question using retrieval-augmented generation over "
        "uploaded PDFs. `conversation_history` is used only to resolve "
        "follow-up questions into a standalone query before retrieval — "
        "the answer is generated from `question` as asked. If no document "
        "has a chunk relevant enough to answer from (including when no "
        "documents have been uploaded yet), a fallback message is "
        "returned with an empty `sources` list rather than an error."
    ),
)
def ask_question(
    request: ChatRequest,
    vectordb: Chroma = Depends(chroma_service.get_vectordb),
    db: Session = Depends(database.get_db),
    user_id: str = Depends(auth_service.get_current_user),
) -> ChatResponse:
    """Answer a question using retrieval-augmented generation over ingested PDFs."""
    logger.info(
        "Chat request: session=%s question=%r history_len=%d",
        request.session_id,
        request.question,
        len(request.conversation_history),
    )
    # Timed end-to-end (rewrite + retrieval + generation), not just the LLM
    # call in isolation, since response_time_seconds in query_logs is
    # meant to reflect what the caller actually waited for.
    start_time = time.time()
    try:
        answer, sources, num_chunks_retrieved = rag_service.generate_answer(
            request.question, request.conversation_history, vectordb, user_id
        )
    except Exception:
        logger.exception("Answer generation failed for session %s", request.session_id)
        raise HTTPException(
            status_code=500, detail="Failed to generate an answer. Please try again."
        )
    response_time = time.time() - start_time

    # Persisting the turn and its performance metrics is bookkeeping, not
    # the user-facing feature — a database hiccup here must never turn a
    # successful answer into a 500 for the caller.
    try:
        database.log_conversation(db, request.question, answer, sources, user_id)
        database.log_query(
            db, request.question, response_time, num_chunks_retrieved, num_chunks_retrieved > 0, user_id
        )
    except Exception:
        logger.error("Could not log conversation/query for session %s", request.session_id, exc_info=True)
        db.rollback()

    return ChatResponse(answer=answer, sources=sources)
