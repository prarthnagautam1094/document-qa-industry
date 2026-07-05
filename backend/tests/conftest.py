"""Shared pytest fixtures for the backend test suite.

These tests exercise the real application stack — the real Chroma vector
store, the real Postgres (Supabase) database, and the real Groq LLM
configured in .env — through FastAPI's TestClient, rather than mocking
any of it. For a RAG backend, the parts most likely to silently break
(retrieval thresholds, prompt wording, chunking behavior) are exactly the
parts a mocked test would hide, so these are deliberately real
integration tests, not unit tests with stubbed collaborators.
"""

import io
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# The app's modules (config, database, services, routers, models) use bare
# imports like `from config import settings`, written to run with backend/
# as the working directory (see main.py's own docstring). Prepending
# backend/ to sys.path here makes those same imports resolve the same way
# for pytest, regardless of which directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database import Conversation, QueryLog, SessionLocal  # noqa: E402
from main import app  # noqa: E402
from services import auth_service  # noqa: E402

# A fixed fake user id for every test in this suite. These tests exercise
# real ingestion/retrieval/generation behavior, not Supabase's token
# verification — that's covered separately in test_auth.py — so the
# get_current_user dependency is overridden here rather than requiring a
# real Supabase project and a real signed JWT just to run the RAG test
# suite.
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"
app.dependency_overrides[auth_service.get_current_user] = lambda: TEST_USER_ID

# Distinctive facts baked into the generated sample PDF, referenced by
# test_chat.py's assertions — defined here so the "source of truth" for
# what the document says lives right next to the code that generates it.
VACATION_DAYS = "18 days"
REMOTE_DAYS = "3 days per week"


def _build_sample_pdf_bytes() -> bytes:
    """Render a small, realistic multi-paragraph PDF with distinctive,
    easily-assertable facts. Generated programmatically (rather than
    checked in as a static file) so the test suite has no external file
    dependency, and the expected content is defined in code alongside the
    tests that check it.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("TechNova Solutions Employee Handbook", styles["Title"]),
        Spacer(1, 12),
        Paragraph(
            "Vacation Policy: All employees at TechNova Solutions are "
            f"entitled to {VACATION_DAYS} of paid vacation per calendar "
            "year. Vacation days must be requested at least 5 business "
            "days in advance through the HR portal.",
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph(
            "Remote Work Policy: Employees may work remotely up to "
            f"{REMOTE_DAYS} with manager approval. Fully remote "
            "arrangements require director-level sign-off.",
            styles["BodyText"],
        ),
        Spacer(1, 12),
        Paragraph(
            "Equipment Policy: Each employee receives a laptop and a "
            "$500 annual budget for home office equipment.",
            styles["BodyText"],
        ),
    ]
    doc.build(story)
    return buffer.getvalue()


@pytest.fixture(scope="session")
def client():
    """A single TestClient for the whole test session.

    TestClient drives the real ASGI app in-process — no real network
    socket needed — but still exercises the full stack: routing,
    dependency injection, Pydantic validation, and whatever
    Chroma/Postgres/Groq backends are configured in .env. Using it as a
    context manager triggers the app's lifespan startup (database.init_db(),
    the GROQ_API_KEY check) exactly as a real server launch would.
    Session-scoped since it's stateless infrastructure shared safely
    across every test.
    """
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def sample_pdf_bytes() -> bytes:
    """Generate the sample PDF once per test session.

    Rendering it is cheap, but there's still no reason to regenerate
    identical, immutable bytes for every single test that needs a file to
    upload — session scope means every test file shares the same one
    in-memory PDF.
    """
    return _build_sample_pdf_bytes()


@pytest.fixture
def unique_filename() -> str:
    """A fresh, collision-free filename for tests that upload their own document.

    /documents/{filename} identifies a document purely by filename, so
    two tests uploading a file with the same name would step on each
    other (or on leftover state from a previous run) without this.
    Function-scoped (the default) so every test gets its own name.
    """
    return f"test_{uuid.uuid4().hex[:8]}.pdf"


@pytest.fixture(autouse=True)
def cleanup_conversation_logs():
    """After every test, wipe the conversations and query_logs tables.

    Every call to /chat/ask writes real rows to Postgres — that's the
    behavior under test, not a mock — so without this, one test's logged
    question would leak into another test's row counts or aggregate
    stats, making the suite order-dependent. Document/Chroma cleanup is
    handled separately by whichever fixture created the document (see
    unique_filename usage in test_documents.py and the module-scoped
    fixture in test_chat.py), since those need finer control over when
    the document itself disappears within a file.
    """
    yield
    db = SessionLocal()
    try:
        db.query(Conversation).delete()
        db.query(QueryLog).delete()
        db.commit()
    finally:
        db.close()
