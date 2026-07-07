"""Regression tests for a real CI failure in rag_service.generate_answer's
tool-calling loop: see the module-level docstrings on the fake LLMs below
and generate_answer's post-loop safety net / mid-loop resilience for the
full story.

Unlike test_chat.py, these tests deliberately do NOT hit the real Groq
API — the bugs they guard against are in *our* loop/message-history
logic, not model quality or retrieval accuracy (the things the project's
no-mocking philosophy protects), and the failure modes (the model never
settling within MAX_TOOL_ITERATIONS; every retry for one turn's
generation failing) aren't things a real LLM can be forced to reproduce
deterministically. Fast, deterministic, code-level tests are the right
tool for this specific class of bug.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx
import groq
from langchain_core.documents import Document

from config import settings
from services import rag_service


def _fake_bad_request_error(message: str) -> groq.BadRequestError:
    """Build a real groq.BadRequestError with a fake httpx.Response —
    groq's exception classes require one, but no actual HTTP round trip
    is needed to construct one for a test.
    """
    response = httpx.Response(
        400, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    )
    return groq.BadRequestError(message, response=response, body=None)


class _NeverSettlesBoundLLM:
    """Simulates a tool-bound ChatGroq that keeps requesting another tool
    call for the first MAX_TOOL_ITERATIONS invocations — forcing
    generate_answer's main loop to exhaust its iteration cap without ever
    settling — then produces a plain-text answer once given one further
    (still tools-bound) chance via the post-loop safety net.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1
        if self.call_count <= settings.MAX_TOOL_ITERATIONS:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "name": "search_documents",
                        "args": {"query": "vacation policy"},
                        "id": f"call_{self.call_count}",
                    }
                ],
            )
        return SimpleNamespace(content="Final answer from the safety net.", tool_calls=[])


class _FakeChatGroq:
    """Stands in for ChatGroq inside generate_answer.

    bind_tools(...) always returns the same _NeverSettlesBoundLLM
    instance (shared across tool_choice="required"/"auto", matching how
    generate_answer reuses one underlying LLM object for both). A bare,
    tools-unbound .invoke() call made against message history that
    already contains tool_calls reproduces exactly what a real Groq
    request gets rejected for: "tool call validation failed: attempted to
    call tool '<name>' which was not in request.tools" — this is what a
    production CI run actually hit before generate_answer's safety net
    was fixed to keep using a tools-bound LLM throughout.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._bound = _NeverSettlesBoundLLM()

    def bind_tools(self, tools, tool_choice=None):
        return self._bound

    def invoke(self, messages):
        if any(getattr(m, "tool_calls", None) for m in messages):
            raise AssertionError(
                "generate_answer invoked a tools-unbound LLM against message "
                "history that already contains tool_calls — this is the exact "
                "bug a real Groq call rejects with 'tool call validation "
                "failed: attempted to call tool ... which was not in "
                "request.tools'."
            )
        return SimpleNamespace(content="unused", tool_calls=[])


def test_generate_answer_keeps_tools_bound_past_the_iteration_cap(monkeypatch):
    """A model that never settles within MAX_TOOL_ITERATIONS must still be
    answered via a tools-bound LLM in the post-loop fallback, not a bare
    one — see _FakeChatGroq's docstring for the production failure this
    guards against.
    """
    monkeypatch.setattr(rag_service, "ChatGroq", _FakeChatGroq)
    # Isolates this test to the tool-calling loop's own logic — retrieval
    # quality/correctness is test_chat.py's job, exercised against the
    # real Chroma store there. Must return something non-empty: an empty
    # result would take generate_answer's "nothing found anywhere"
    # early-return before it ever reaches the safety net this test targets.
    fake_doc = Document(
        page_content="Employees get 24 paid leaves per year.",
        metadata={"source": "handbook.pdf", "page_label": "1"},
    )
    monkeypatch.setattr(rag_service, "retrieve_relevant_chunks", lambda *a, **k: [fake_doc])

    answer, sources, num_results, source_type = rag_service.generate_answer(
        "How does our vacation policy compare to the industry average?",
        [],
        MagicMock(),
        "test-user",
    )

    # The AssertionError above would have propagated (generate_answer has
    # no try/except around the safety-net call) if the bug had regressed —
    # reaching this line at all is most of what this test checks.
    assert answer == "Final answer from the safety net."
    assert sources == ["handbook.pdf (p. 1)"]
    assert source_type == "document"


class _FailsSecondTurnBoundLLM:
    """Simulates the actual CI failure: the first tool-call turn succeeds
    normally (requesting search_documents), but every retry of the
    *second* turn's generation hits Groq's real, documented, non-
    deterministic malformed-tool-call quirk — reproducing "tool call
    validation failed: attempted to call tool ... which was not in
    request.tools" on every attempt, exhausting
    _invoke_with_tool_retry's retry budget.
    """

    def __init__(self) -> None:
        self.call_count = 0

    def invoke(self, messages):
        self.call_count += 1
        if self.call_count == 1:
            return SimpleNamespace(
                content="",
                tool_calls=[
                    {"name": "search_documents", "args": {"query": "vacation policy"}, "id": "call_1"}
                ],
            )
        raise _fake_bad_request_error(
            "tool call validation failed: attempted to call tool "
            "'search_web {\"query\": \"industry average\"}' which was not in request.tools"
        )


class _FakeChatGroqFailsSecondTurn:
    """Stands in for ChatGroq: every bind_tools(...) call shares the same
    _FailsSecondTurnBoundLLM instance, so the "first turn succeeds, every
    retry of the second fails" behavior is consistent whether
    generate_answer is currently using llm_required or llm_auto.
    """

    def __init__(self, *args, **kwargs) -> None:
        self._bound = _FailsSecondTurnBoundLLM()

    def bind_tools(self, tools, tool_choice=None):
        return self._bound


def test_generate_answer_degrades_gracefully_when_retries_are_exhausted_mid_conversation(monkeypatch):
    """Reproduces the actual CI failure end to end: exhausting
    _invoke_with_tool_retry's retries on a *later* turn must not crash
    the whole request (the old behavior — a 500 via chat.py's generic
    exception handler) when earlier turns already gathered real results.
    generate_answer should answer from what it has instead.
    """
    monkeypatch.setattr(rag_service, "ChatGroq", _FakeChatGroqFailsSecondTurn)
    fake_doc = Document(
        page_content="Employees get 24 paid leaves per year.",
        metadata={"source": "handbook.pdf", "page_label": "1"},
    )
    monkeypatch.setattr(rag_service, "retrieve_relevant_chunks", lambda *a, **k: [fake_doc])

    # Must not raise groq.BadRequestError (or anything else) — that's the
    # exact bug this test guards against.
    answer, sources, num_results, source_type = rag_service.generate_answer(
        "How does our vacation policy compare to the industry average?",
        [],
        MagicMock(),
        "test-user",
    )

    assert answer  # some non-empty response, not a crash
    assert sources == ["handbook.pdf (p. 1)"]
    assert num_results == 1
    # Only search_documents ever actually succeeded — the second turn's
    # search_web attempt never got a real result, so this correctly
    # reflects "document" rather than "both".
    assert source_type == "document"
