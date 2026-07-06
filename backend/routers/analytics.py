"""Endpoint exposing per-user usage/performance analytics."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

import database
from models.schemas import AnalyticsResponse
from services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get(
    "",
    response_model=AnalyticsResponse,
    summary="Get usage and performance analytics",
    description=(
        "Returns aggregate usage/performance stats for the current user: "
        "document and query counts, success rate, average response time, "
        "a 30-day daily query trend, the most-cited documents, and the "
        "10 most recent conversation turns. Scoped entirely to the "
        "authenticated user — never includes another user's data."
    ),
)
def get_analytics(
    db: Session = Depends(database.get_db),
    user_id: str = Depends(auth_service.get_current_user),
) -> AnalyticsResponse:
    """Assemble this user's analytics from the documents/conversations/query_logs tables."""
    logger.info("Analytics requested")
    stats = database.get_query_stats(db, user_id)
    return AnalyticsResponse(
        total_documents=database.get_document_count(db, user_id),
        total_queries=stats["total_queries"],
        success_rate=stats["success_rate"],
        avg_response_time=stats["avg_response_time"],
        queries_over_time=database.get_queries_over_time(db, user_id),
        most_queried_documents=database.get_most_queried_documents(db, user_id),
        recent_conversations=database.get_recent_conversations(db, user_id),
    )
