"""Covers question-answering: retrieval-grounded answers, the "no
relevant context" fallback, conversational follow-up handling, and input
validation.

This is the core value proposition of the whole backend — ingestion and
vector storage only exist to feed this. These tests call the real Groq
LLM and the real vector store (no mocking), the same way an actual client
would, so a prompt regression, a broken relevance threshold, or a broken
query-rewrite step shows up here instead of only in production.
"""

import pytest

from conftest import REMOTE_DAYS, VACATION_DAYS


@pytest.fixture(scope="module")
def shared_document(client, sample_pdf_bytes):
    """Upload the sample PDF once for every test in this module, and
    delete it once at the end.

    Chat tests only ever *read* against the document — none of them
    mutate or delete it — so sharing one upload across the whole module
    is safe and avoids paying the embedding/upload cost per test. Each
    test's own conversation/query_log rows are still isolated by the
    autouse cleanup fixture in conftest.py, so sharing the document
    doesn't leak any state between tests.
    """
    filename = "shared_chat_test.pdf"
    client.post(
        "/documents/upload",
        files=[("files", (filename, sample_pdf_bytes, "application/pdf"))],
    )
    yield filename
    client.delete(f"/documents/{filename}")


def test_ask_relevant_question_returns_grounded_answer(client, shared_document):
    response = client.post(
        "/chat/ask",
        json={
            "question": "How many vacation days do employees get per year?",
            "session_id": "test-relevant",
            "conversation_history": [],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["answer"].strip() != ""
    assert "couldn't find relevant information" not in body["answer"]
    assert len(body["sources"]) > 0
    # The answer should contain the actual number from the document
    # ("18") — this is what distinguishes "answered from retrieved
    # context" from "the LLM produced a plausible-sounding but ungrounded
    # answer". Checking just the digits (not the exact phrase "18 days")
    # tolerates minor LLM phrasing variation like "18-day" or "18".
    assert VACATION_DAYS.split()[0] in body["answer"]


def test_ask_offtopic_question_returns_fallback(client, shared_document):
    response = client.post(
        "/chat/ask",
        json={
            "question": "What is the capital of Japan?",
            "session_id": "test-offtopic",
            "conversation_history": [],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert "couldn't find relevant information" in body["answer"]
    assert body["sources"] == []


def test_ask_followup_with_history_gets_sensible_answer(client, shared_document):
    response = client.post(
        "/chat/ask",
        json={
            "question": "What about remote work?",
            "session_id": "test-followup",
            "conversation_history": [
                {"role": "user", "content": "What is the vacation policy?"},
                {
                    "role": "assistant",
                    "content": f"Employees get {VACATION_DAYS} of paid vacation per year.",
                },
            ],
        },
    )
    assert response.status_code == 200

    body = response.json()
    assert body["answer"].strip() != ""
    assert "couldn't find relevant information" not in body["answer"]
    assert len(body["sources"]) > 0
    # Confirms the follow-up was actually resolved against the remote-work
    # section (not re-answering the previous vacation-policy turn) — the
    # standalone-query rewrite is the thing under test here.
    assert REMOTE_DAYS.split()[0] in body["answer"]


def test_ask_empty_question_returns_422(client):
    response = client.post(
        "/chat/ask",
        json={"question": "", "session_id": "test-empty", "conversation_history": []},
    )
    assert response.status_code == 422
