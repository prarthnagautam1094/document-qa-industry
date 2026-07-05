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
from datetime import datetime, timezone

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
