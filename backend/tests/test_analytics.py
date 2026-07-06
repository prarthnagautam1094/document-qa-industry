"""Covers GET /analytics: response structure and per-user data isolation.

Creates its own conversation activity via /chat/ask rather than relying on
another test file's leftover rows — the autouse cleanup_conversation_logs
fixture in conftest.py wipes conversations/query_logs after every test, so
each test here must produce whatever data it asserts on itself.
"""

import pytest

from conftest import TEST_USER_ID
from main import app
from services import auth_service


@pytest.fixture(scope="module")
def analytics_document(client, sample_pdf_bytes):
    """Upload one document for this module's tests, scoped to TEST_USER_ID."""
    filename = "analytics_test.pdf"
    client.post(
        "/documents/upload",
        files=[("files", (filename, sample_pdf_bytes, "application/pdf"))],
    )
    yield filename
    client.delete(f"/documents/{filename}")


def test_analytics_returns_expected_structure(client, analytics_document):
    client.post(
        "/chat/ask",
        json={
            "question": "How many vacation days do employees get per year?",
            "session_id": "analytics-test",
            "conversation_history": [],
        },
    )

    response = client.get("/analytics")
    assert response.status_code == 200

    body = response.json()
    assert set(body.keys()) == {
        "total_documents",
        "total_queries",
        "success_rate",
        "avg_response_time",
        "queries_over_time",
        "most_queried_documents",
        "recent_conversations",
    }
    assert body["total_documents"] >= 1
    assert body["total_queries"] >= 1
    assert 0 <= body["success_rate"] <= 100
    assert body["avg_response_time"] >= 0

    # 30 days, zero-filled, oldest first.
    assert len(body["queries_over_time"]) == 30
    assert all(set(entry.keys()) == {"date", "count"} for entry in body["queries_over_time"])
    dates = [entry["date"] for entry in body["queries_over_time"]]
    assert dates == sorted(dates)
    # The question asked above was cited from the just-uploaded document,
    # so it should show up in the ranking.
    assert any(doc["filename"] == analytics_document for doc in body["most_queried_documents"])

    assert len(body["recent_conversations"]) >= 1
    assert all(
        set(entry.keys()) == {"timestamp", "question", "was_answered"}
        for entry in body["recent_conversations"]
    )
    assert body["recent_conversations"][0]["was_answered"] is True


def test_analytics_is_scoped_to_the_current_user(client, analytics_document):
    # TEST_USER_ID (see conftest.py) has at least the document + question
    # from the test above. A different user, overridden just for this
    # test, must see none of it — this is the whole point of scoping
    # every analytics query by user_id.
    other_user_id = "00000000-0000-0000-0000-000000000099"
    app.dependency_overrides[auth_service.get_current_user] = lambda: other_user_id
    try:
        response = client.get("/analytics")
        assert response.status_code == 200
        body = response.json()
        assert body["total_documents"] == 0
        assert body["total_queries"] == 0
        assert body["success_rate"] == 0.0
        assert body["most_queried_documents"] == []
        assert body["recent_conversations"] == []
        assert all(entry["count"] == 0 for entry in body["queries_over_time"])
    finally:
        app.dependency_overrides[auth_service.get_current_user] = lambda: TEST_USER_ID


def test_analytics_requires_auth(client):
    original = app.dependency_overrides.pop(auth_service.get_current_user, None)
    try:
        response = client.get("/analytics")
        assert response.status_code == 401
    finally:
        if original is not None:
            app.dependency_overrides[auth_service.get_current_user] = original
