"""SQLAlchemy engine, session factory, and ORM models for persistent
storage of ingested documents, conversation history, and query
performance logs.

Why PostgreSQL (Supabase-hosted) instead of SQLite here: SQLite is a
single file on disk with file-level write locking — fine for a local demo
script or a single-user Streamlit prototype, but this is a FastAPI
backend meant to serve concurrent requests (potentially across multiple
uvicorn workers), and SQLite's "one writer at a time" model turns into
"database is locked" errors well before real traffic would stress a
proper client/server database. Postgres is built for concurrent
connections, and using a managed, cloud-hosted instance (Supabase) means
the data isn't tied to this process's local disk at all — it survives a
redeploy, a container restart, or moving the app to different
infrastructure entirely, which is the baseline expectation for
persistence in a production-grade backend rather than a demo script.
"""

import logging
import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import Boolean, Column, DateTime, Float, Integer, String, Text, create_engine, func
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from config import settings

logger = logging.getLogger(__name__)

# pool_pre_ping guards against Supabase (or any managed Postgres) silently
# closing idle connections — without it, the first query on a connection
# that's gone stale fails outright instead of transparently reconnecting.
# engine is None when DATABASE_URL isn't configured, so the app can still
# start (see init_db()); every call site below that touches the database
# is wrapped by its caller so a None/broken engine degrades gracefully
# instead of crashing the request.
engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True) if settings.DATABASE_URL else None
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Document(Base):
    """One row per successfully ingested PDF."""

    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    filename = Column(String, nullable=False)
    upload_timestamp = Column(DateTime(timezone=True), nullable=False)
    chunk_count = Column(Integer, nullable=False)


class Conversation(Base):
    """One row per Q&A turn.

    Sources are flattened to a comma-separated string (matching the
    original schema) rather than normalized into their own table —
    they're display-only citations that are never queried or filtered on
    individually, so a join table would add complexity with no practical
    benefit here.
    """

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    sources = Column(Text, nullable=True)


class QueryLog(Base):
    """One row per question asked, independent of the answer text — this is
    the table a real deployment builds latency/success-rate dashboards on
    without needing to parse conversation text to figure out which turns
    fell back to "couldn't find information".
    """

    __tablename__ = "query_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, nullable=False, index=True)
    question = Column(Text, nullable=False)
    response_time_seconds = Column(Float, nullable=False)
    num_chunks_retrieved = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    was_answered = Column(Boolean, nullable=False)


def init_db() -> None:
    """Create all tables if they don't exist. Called once at app startup.

    A missing/invalid DATABASE_URL or an unreachable Supabase instance
    must not crash the whole app before a single request is served — PDF
    upload, retrieval, and chat don't depend on this table existing, so
    this logs a clear, actionable error and returns instead of raising.
    """
    if engine is None:
        logger.error(
            "DATABASE_URL is not set — document/conversation/query-log "
            "persistence is disabled. Check your .env file."
        )
        return
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables ready (documents, conversations, query_logs).")
    except Exception:
        logger.error(
            "Could not connect to the database to create tables. Check "
            "that DATABASE_URL in .env is correct and the database is "
            "reachable.",
            exc_info=True,
        )


def get_db():
    """FastAPI dependency: yield a request-scoped SQLAlchemy session.

    Each request gets its own Session via Depends(get_db) rather than
    sharing one module-level session — Session is not safe to use
    concurrently across requests, and per-request scoping is what lets
    each request's transaction commit or roll back independently.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def log_document(db: Session, filename: str, chunk_count: int, user_id: str) -> None:
    """Record a successfully ingested document, scoped to the uploading user."""
    db.add(
        Document(
            user_id=user_id,
            filename=filename,
            upload_timestamp=datetime.now(timezone.utc),
            chunk_count=chunk_count,
        )
    )
    db.commit()


def delete_document_record(db: Session, filename: str, user_id: str) -> None:
    """Remove a document's row(s) from the documents table.

    Mirrors the delete on the Chroma side (which removes the filename's
    chunks) — without this, a deleted document's row would remain in
    Postgres forever, so the table would silently stop reflecting what's
    actually in the vector store. filter (not filter_by) with delete()
    removes every row for this filename, matching the fact that
    log_document is called once per upload, so a file uploaded, deleted,
    and re-uploaded could have accumulated more than one row. Scoped to
    user_id so one user's delete can never remove another user's row,
    even if two users happen to upload a same-named file.
    """
    db.query(Document).filter(Document.filename == filename, Document.user_id == user_id).delete()
    db.commit()


def log_conversation(db: Session, question: str, answer: str, sources: list, user_id: str) -> None:
    """Record one Q&A turn, with sources flattened to comma-separated text."""
    db.add(
        Conversation(
            user_id=user_id,
            question=question,
            answer=answer,
            timestamp=datetime.now(timezone.utc),
            sources=", ".join(sources),
        )
    )
    db.commit()


def log_query(
    db: Session,
    question: str,
    response_time: float,
    num_chunks: int,
    was_answered: bool,
    user_id: str,
) -> None:
    """Record retrieval/generation performance metrics for one question."""
    db.add(
        QueryLog(
            user_id=user_id,
            question=question,
            response_time_seconds=response_time,
            num_chunks_retrieved=num_chunks,
            timestamp=datetime.now(timezone.utc),
            was_answered=was_answered,
        )
    )
    db.commit()


def get_query_stats(db: Session, user_id: str) -> dict:
    """Return aggregate query stats for one user: total queries, avg response time, success rate.

    Returns zeros/defaults rather than None fields when there's no data
    yet, so callers can render a stats view without a special-case for an
    empty table. Scoped to user_id — otherwise one tenant's dashboard
    would include every other tenant's query volume and success rate.
    """
    base = db.query(QueryLog).filter(QueryLog.user_id == user_id)
    total = base.count()
    if total == 0:
        return {"total_queries": 0, "avg_response_time": 0.0, "success_rate": 0.0}

    avg_time = (
        db.query(func.avg(QueryLog.response_time_seconds))
        .filter(QueryLog.user_id == user_id)
        .scalar()
        or 0.0
    )
    answered = base.filter(QueryLog.was_answered.is_(True)).count()
    return {
        "total_queries": total,
        "avg_response_time": round(avg_time, 2),
        "success_rate": round(answered / total * 100, 1),
    }


def get_document_count(db: Session, user_id: str) -> int:
    """Return how many documents this user currently has on record."""
    return db.query(Document).filter(Document.user_id == user_id).count()


def get_queries_over_time(db: Session, user_id: str, days: int = 30) -> List[dict]:
    """Return one {date, count} entry per day for the last `days` days,
    oldest first, including days with zero queries.

    Zero-filling every day (rather than only the days something actually
    happened) is what lets a caller plot this directly as a continuous
    time series — a chart built from a sparse GROUP BY would show gaps
    wherever nothing happened instead of a flat zero, which reads as
    missing data rather than "no activity that day".
    """
    today = datetime.now(timezone.utc).date()
    start_date = today - timedelta(days=days - 1)
    start_datetime = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)

    rows = (
        db.query(func.date(QueryLog.timestamp).label("day"), func.count(QueryLog.id))
        .filter(QueryLog.user_id == user_id, QueryLog.timestamp >= start_datetime)
        .group_by("day")
        .all()
    )
    counts_by_day = {row[0]: row[1] for row in rows}

    return [
        {
            "date": (start_date + timedelta(days=i)).isoformat(),
            "count": counts_by_day.get(start_date + timedelta(days=i), 0),
        }
        for i in range(days)
    ]


# Matches the "filename (p. N)" document-citation format generate_answer
# builds (see rag_service._chunk_label) — used below to recover just the
# filename, stripping the page suffix, so citations of the same document
# on different pages count toward one total instead of splitting it.
_DOC_SOURCE_PATTERN = re.compile(r"^(.*)\s\(p\.\s*.+\)$")


def get_most_queried_documents(db: Session, user_id: str, limit: int = 5) -> List[dict]:
    """Return the top `limit` documents by how often they were cited as a
    source across this user's conversations, most-cited first.

    Parses each conversation's flattened `sources` string (see
    log_conversation) rather than querying a normalized sources table —
    sources were never modeled as their own rows (see Conversation's
    docstring), so this is the one place that flattening costs a bit of
    string parsing instead of a GROUP BY. Web-search citations (bare
    URLs, from rag_service._web_source_label) are excluded — this stat is
    specifically about the user's own uploaded documents.
    """
    rows = (
        db.query(Conversation.sources)
        .filter(Conversation.user_id == user_id, Conversation.sources.isnot(None))
        .all()
    )

    counts: Counter = Counter()
    for (sources_text,) in rows:
        if not sources_text:
            continue
        for raw in sources_text.split(", "):
            raw = raw.strip()
            if not raw or raw.startswith("http://") or raw.startswith("https://"):
                continue
            match = _DOC_SOURCE_PATTERN.match(raw)
            filename = match.group(1) if match else raw
            counts[filename] += 1

    return [{"filename": filename, "count": count} for filename, count in counts.most_common(limit)]


# Recent-conversation questions are shown as a table row, not a full
# transcript — truncated so one long question can't blow out the layout.
_RECENT_QUESTION_MAX_LENGTH = 100


def get_recent_conversations(db: Session, user_id: str, limit: int = 10) -> List[dict]:
    """Return the `limit` most recent conversation turns for this user, newest first.

    `was_answered` is derived from whether any sources were cited rather
    than joined against query_logs — the two tables have no shared key
    linking a specific conversation row to a specific query_log row, but
    generate_answer's contract guarantees they agree: sources is non-empty
    exactly when num_chunks_retrieved > 0 (query_logs.was_answered), so
    checking sources here is equivalent without an unreliable join.
    """
    rows = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "timestamp": row.timestamp.isoformat(),
            "question": (
                row.question
                if len(row.question) <= _RECENT_QUESTION_MAX_LENGTH
                else row.question[: _RECENT_QUESTION_MAX_LENGTH - 1].rstrip() + "…"
            ),
            "was_answered": bool(row.sources),
        }
        for row in rows
    ]
