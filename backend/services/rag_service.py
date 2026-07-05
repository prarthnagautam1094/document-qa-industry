"""Core RAG logic: PDF ingestion, retrieval, query rewriting, and answer
generation.

Ported from a working Streamlit prototype. The retrieval/generation logic
is unchanged; what changed is the shape of the code around it — instead of
reading/writing `st.session_state`, every function takes the resources it
needs (a Chroma instance, a conversation history list) as explicit
parameters, since a stateless API has no per-user session object to reach
into.

Created by Prarthna Gautam (https://github.com/prarthnagautam1094) — 2026.
Part of the Document Q&A project.
"""

import logging
import tempfile
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

import groq
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import CrossEncoder

from config import settings
from models.schemas import ChatMessage
from services import web_search_service

logger = logging.getLogger(__name__)

# Single system prompt for the tool-calling loop below — the LLM decides
# for itself (via real tool calls, not a separate classification prompt)
# whether it needs the uploaded documents, live web search, or both, so
# there's no longer a per-route prompt variant to keep in sync with a
# routing decision made elsewhere.
TOOL_SYSTEM_PROMPT = (
    "You answer questions by calling tools to gather grounded information "
    "before responding — never answer from your own prior knowledge alone. "
    "Call search_documents for anything that could be in the user's own "
    "uploaded documents, and search_web for current events or general "
    "knowledge unlikely to be in those documents. Call both, one at a "
    "time, if the question plausibly needs information from both. Base "
    "your final answer only on what the tools returned. If a tool result "
    "doesn't answer the question, say so honestly rather than guessing. "
    "When your answer draws on both a document and a web result, clearly "
    "distinguish which part comes from which (e.g. 'According to your "
    "document...' vs 'According to a recent web search...')."
)


@lru_cache(maxsize=1)
def get_cross_encoder() -> CrossEncoder:
    """Load and cache the cross-encoder re-ranking model.

    Same pattern as chroma_service.get_embeddings(): loaded once per
    process and reused on every request, since re-loading a transformer
    model per call would dominate request latency.
    """
    logger.info("Loading cross-encoder model: %s", settings.CROSS_ENCODER_MODEL)
    return CrossEncoder(settings.CROSS_ENCODER_MODEL)


class PDFProcessingError(Exception):
    """Raised when a PDF can't be read, or has no extractable text.

    Callers (the documents router) catch this specifically to turn it into
    a per-file failure result rather than a 500 — a corrupt or scanned PDF
    is bad input, not a server fault.
    """


def process_pdf(file_bytes: bytes, filename: str, vectordb: Chroma, user_id: str) -> int:
    """Chunk, embed, and store one PDF's contents in the vector store.

    Returns the number of chunks created. Raises PDFProcessingError if the
    file is unreadable/corrupted/password-protected, or has no extractable
    text (e.g. a scanned/image-only PDF with no text layer) — embedding an
    empty document would add useless zero-content vectors that silently
    degrade retrieval for every other document.

    Every chunk is stamped with user_id in its metadata (same mechanism as
    "source" and "upload_timestamp" below) — Chroma stores every user's
    chunks in one shared collection, so this metadata field is the only
    thing that lets retrieval, listing, and deletion later filter down to
    just the uploading user's own documents.
    """
    # PyPDFLoader needs a filesystem path, so the uploaded bytes are
    # written to a temp file for the duration of loading.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        try:
            loader = PyPDFLoader(tmp_path)
            documents = loader.load()
        except Exception as exc:
            raise PDFProcessingError(
                f"Could not read '{filename}' — it may be corrupted or "
                "password-protected."
            ) from exc

        # Stamp each page with the original filename (PyPDFLoader defaults
        # "source" to the temp path) and an ingestion timestamp, both of
        # which propagate onto every chunk split from it below — this is
        # what makes citations readable and lets list_documents() group
        # chunks back into documents without a separate metadata store.
        upload_timestamp = datetime.now(timezone.utc).isoformat()
        for doc in documents:
            doc.metadata["source"] = filename
            doc.metadata["upload_timestamp"] = upload_timestamp
            doc.metadata["user_id"] = user_id

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE, chunk_overlap=settings.CHUNK_OVERLAP
        )
        chunks = text_splitter.split_documents(documents)

        total_text_length = sum(len(c.page_content) for c in chunks)
        if not chunks or total_text_length < 50:
            raise PDFProcessingError(
                f"'{filename}' appears to have no extractable text — it "
                "may be a scanned/image-based PDF."
            )

        vectordb.add_documents(chunks)
        logger.info("Processed '%s' into %d chunks", filename, len(chunks))
        return len(chunks)
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def list_documents(vectordb: Chroma, user_id: str) -> List[dict]:
    """Return every distinct document currently stored for this user, grouped from chunk metadata.

    Chroma stores chunks, not documents — there's no separate table
    tracking uploads — so this reconstructs the document list by grouping
    every stored chunk's "source" metadata and counting chunks per
    filename. Filtered to this user's own chunks via the "user_id"
    metadata stamped at ingestion — without this, every user would see
    every other user's document list.
    """
    collection_data = vectordb.get(where={"user_id": user_id}, include=["metadatas"])
    documents: dict = {}
    for metadata in collection_data["metadatas"]:
        filename = metadata.get("source", "unknown")
        if filename not in documents:
            documents[filename] = {
                "filename": filename,
                "chunk_count": 0,
                "upload_timestamp": metadata.get("upload_timestamp"),
            }
        documents[filename]["chunk_count"] += 1
    return list(documents.values())


def rewrite_query_standalone(question: str, history: List[ChatMessage]) -> str:
    """Rewrite a follow-up question into a standalone one using recent history.

    In a multi-turn RAG chat, users often ask elliptical follow-ups like
    "and what about maternity?" that only make sense given the preceding
    turns. The vector store has no notion of conversation — it embeds
    exactly the words it's given — so searching with the raw follow-up
    retrieves poorly or matches the wrong topic entirely. Rewriting the
    follow-up into a self-contained question before retrieval lets
    similarity search match against what the user actually means,
    independent of the conversation that led there.
    """
    if not history:
        return question

    # Last 2-3 exchanges is enough context to resolve most pronouns/
    # ellipsis without paying for a huge prompt on every turn.
    recent = history[-6:]
    history_text = "\n".join(
        f"{'User' if m.role == 'user' else 'Assistant'}: {m.content}" for m in recent
    )

    llm = ChatGroq(model=settings.LLM_MODEL)
    rewrite_prompt = (
        "Given the conversation history and a follow-up question, rewrite "
        "the follow-up question as a standalone question that can be "
        "understood without the conversation history, preserving its "
        "original meaning and intent. If it is already standalone, return "
        "it unchanged. Respond with ONLY the rewritten question — no "
        "explanation, no quotes.\n\n"
        f"Conversation history:\n{history_text}\n\n"
        f"Follow-up question: {question}\n\n"
        "Standalone question:"
    )
    # Rewriting is a nice-to-have retrieval optimization, not the answer
    # itself — if Groq is unreachable, rate-limited, or times out here,
    # fall back to searching with the raw question rather than failing the
    # whole request over a step the caller never sees.
    try:
        response = llm.invoke([HumanMessage(content=rewrite_prompt)])
        return response.content.strip()
    except Exception:
        logger.warning("Query rewrite failed; falling back to the raw question", exc_info=True)
        return question


def _chunk_label(doc: Document) -> str:
    """Build the "filename (p. N)" citation label for one chunk.

    Shared by the re-ranking debug log below and generate_answer's
    citation list, so the two never drift out of sync with each other.
    """
    filename = doc.metadata.get("source", "unknown")
    page = doc.metadata.get("page_label", doc.metadata.get("page", "?"))
    return f"{filename} (p. {page})"


def _rerank(query: str, candidates: List[Tuple[Document, float]]) -> List[Document]:
    """Re-score bi-encoder candidates with the cross-encoder and return
    them sorted best-first.

    ============================================================================
    BI-ENCODER (stage 1, Chroma) vs CROSS-ENCODER (stage 2, this function)
    ----------------------------------------------------------------------------
    Stage 1 embeds the query and every chunk *independently* into vectors
    ahead of time, then compares them with cosine similarity — that
    independence is exactly what makes it fast enough to search an entire
    collection (a single HNSW index lookup), but it also means the model
    never actually looks at the query and a chunk together. Two chunks
    that share surface-level vocabulary with the query can end up with
    near-identical bi-encoder scores even when only one of them actually
    answers the question — the embedding captures "roughly the same
    topic," not "specifically relevant to this question."
    Stage 2 feeds the (query, chunk) pair through the transformer
    *together*, so it can attend across both texts and weigh how the
    specific wording of the question relates to the specific wording of
    the chunk — a much more precise relevance judgment. That precision
    costs a full transformer forward pass per candidate instead of one
    vector lookup, so it doesn't scale to an entire collection — running
    it only over the small shortlist stage 1 already narrowed things down
    to is what makes two-stage retrieval practical: bi-encoder speed at
    collection scale, cross-encoder precision on the chunks that actually
    end up in front of the LLM.
    ============================================================================

    Falls back to the original bi-encoder order (rather than raising) if
    the cross-encoder fails to load or run — re-ranking is a quality
    improvement, not a required step, so a broken model shouldn't turn a
    working retrieval into a failed one.
    """
    docs = [doc for doc, _ in candidates]
    try:
        cross_encoder = get_cross_encoder()
        pairs = [(query, doc.page_content) for doc in docs]
        cross_scores = cross_encoder.predict(pairs)
    except Exception:
        logger.warning("Cross-encoder re-ranking failed; using bi-encoder order", exc_info=True)
        return docs

    combined = [
        (doc, bi_score, float(cross_score))
        for (doc, bi_score), cross_score in zip(candidates, cross_scores)
    ]
    bi_order = sorted(combined, key=lambda item: item[1], reverse=True)
    cross_order = sorted(combined, key=lambda item: item[2], reverse=True)

    # Demo/debug evidence: log both orderings side by side (with scores)
    # so it's visible exactly when and how re-ranking changed the result
    # — useful evidence that the cross-encoder stage is actually doing
    # something, not just adding latency.
    bi_labels = [f"{_chunk_label(doc)} [bi={bi:.3f}]" for doc, bi, _ in bi_order]
    cross_labels = [f"{_chunk_label(doc)} [cross={cr:.3f}]" for doc, _, cr in cross_order]
    if [doc for doc, _, _ in bi_order] != [doc for doc, _, _ in cross_order]:
        logger.info(
            "Re-ranking CHANGED the order for query %r:\n  bi-encoder:    %s\n  cross-encoder: %s",
            query,
            bi_labels,
            cross_labels,
        )
    else:
        logger.info(
            "Re-ranking confirmed the bi-encoder order for query %r: %s", query, cross_labels
        )

    return [doc for doc, _, _ in cross_order]


def retrieve_relevant_chunks(query: str, vectordb: Chroma, user_id: str) -> List[Document]:
    """Two-stage retrieval: threshold-filter a bi-encoder shortlist, then
    cross-encoder re-rank it for the final chunks sent to the LLM.

    Pulls MAX_RETRIEVAL_CANDIDATES scored results from Chroma rather than
    a plain top-N — with multiple documents in the same collection, a
    plain similarity_search always returns k chunks regardless of how
    relevant they actually are, so scoring more candidates and
    thresholding lets us drop off-topic chunks before they ever reach the
    (more expensive) re-ranking stage. The survivors are then re-ranked
    by _rerank() and capped at MAX_CONTEXT_CHUNKS — see _rerank's
    docstring for the full bi-encoder vs cross-encoder rationale. Returns
    [] (rather than raising) if the store is empty, the search otherwise
    fails, or nothing clears the threshold, since "no relevant context"
    is a normal outcome for generate_answer to fall back on, not an
    error.

    The `filter={"user_id": user_id}` restricts the similarity search to
    this user's own chunks — without it, one user's question could be
    answered (and cited) from another user's uploaded documents, which
    for a document Q&A product is a data leak, not just a relevance bug.
    """
    try:
        scored_results = vectordb.similarity_search_with_relevance_scores(
            query, k=settings.MAX_RETRIEVAL_CANDIDATES, filter={"user_id": user_id}
        )
    except Exception:
        logger.warning(
            "Similarity search failed (likely an empty vector store)", exc_info=True
        )
        return []

    candidates = [
        (doc, score) for doc, score in scored_results if score >= settings.RELEVANCE_THRESHOLD
    ]
    if not candidates:
        return []

    reranked = _rerank(query, candidates)
    return reranked[: settings.MAX_CONTEXT_CHUNKS]


def _web_source_label(result: web_search_service.WebSearchResult) -> str:
    """Build the citation label for one web search result — the URL
    itself, matching how a document citation is the thing you'd actually
    click through to verify (a "filename (p. N)" analog would be the
    result's title, but the URL is what the frontend needs to link out).
    """
    return result["url"]


class _ToolExecutionState:
    """Collects what each tool call actually retrieved, as it happens.

    The LLM only ever sees the plain-text string a tool call returns (fed
    back as a ToolMessage) — but generate_answer still needs the
    underlying Document/WebSearchResult objects afterward to build the
    `sources` citation list, count `num_chunks_retrieved`, and know which
    tool(s) were actually invoked for `source_type`. Mutated from inside
    the tool closures in _build_tools() rather than parsed back out of
    the LLM's tool-call arguments or its final text, which would be
    fragile and duplicate work retrieve_relevant_chunks/search_web
    already did.
    """

    def __init__(self) -> None:
        self.doc_results: List[Document] = []
        self.web_results: List[web_search_service.WebSearchResult] = []
        self.tools_called: List[str] = []


def _build_tools(vectordb: Chroma, user_id: str, state: _ToolExecutionState) -> List[BaseTool]:
    """Build the two tools the LLM can call, bound via closure to this
    request's vectordb/user_id/state.

    The LLM only ever sees and controls the `query` argument each tool's
    schema exposes — which vector store and which user's chunks to
    search are this request's own resources, never something a tool-
    calling LLM should be trusted to supply itself. A fresh pair of
    closures is built per request (cheap: LangChain's @tool wrapping is
    lightweight) rather than sharing one module-level instance, since
    each request has its own vectordb/user_id/state to close over.
    """

    @tool
    def search_documents(query: str) -> str:
        """Search the user's own uploaded documents (their company handbook, HR policies, personal reports, or other files they've uploaded) for information relevant to the query. Use this whenever the question could be about content the user has personally uploaded."""
        state.tools_called.append("search_documents")
        docs = retrieve_relevant_chunks(query, vectordb, user_id)
        state.doc_results = docs
        if not docs:
            return "No relevant content found in the uploaded documents."
        return "\n\n".join(f"[{_chunk_label(doc)}]\n{doc.page_content}" for doc in docs)

    @tool
    def search_web(query: str) -> str:
        """Search the live web for current events, real-time facts (today's weather, news, sports results, prices), or general world knowledge unlikely to be found in the user's own uploaded documents. Use this whenever the question needs up-to-date or general information."""
        state.tools_called.append("search_web")
        results = web_search_service.search_web(query)
        state.web_results = results
        if not results:
            return "No web search results found."
        return "\n\n".join(f"{r['title']}\nSource: {r['url']}\n{r['snippet']}" for r in results)

    return [search_documents, search_web]


def _invoke_with_tool_retry(llm_with_tools, messages: List[BaseMessage]):
    """Invoke a tool-bound LLM, retrying on Groq's occasional malformed
    tool-call generation.

    llama-3.3-70b-versatile via Groq's API sometimes emits a syntactically
    broken function-call (e.g. a missing closing tag), which Groq rejects
    with a 400 `tool_use_failed` BadRequestError rather than returning it
    as a normal (unusable) response — this isn't a bug in this code, it's
    a documented, non-deterministic quirk of the model/API pairing.
    Retrying is the mitigation Groq's own docs recommend: since the model
    runs at temperature > 0, a retry samples a fresh generation and has a
    real chance of producing a well-formed call where the last attempt
    didn't. Exhausting all retries propagates the error — by this point
    it's indistinguishable from a genuine Groq outage, which the router
    already maps to a 500.
    """
    last_exc: Exception = RuntimeError("unreachable")
    for attempt in range(settings.MAX_TOOL_CALL_RETRIES):
        try:
            return llm_with_tools.invoke(messages)
        except groq.BadRequestError as exc:
            last_exc = exc
            logger.warning(
                "Tool-call generation failed (attempt %d/%d): %s",
                attempt + 1,
                settings.MAX_TOOL_CALL_RETRIES,
                exc,
            )
    raise last_exc


def generate_answer(
    question: str, history: List[ChatMessage], vectordb: Chroma, user_id: str
) -> Tuple[str, List[str], int, str]:
    """Run the full pipeline for one question: rewrite -> tool-calling loop -> generate.

    Returns (answer, sources, num_chunks_retrieved, source_type). `history`
    is used only to rewrite `question` into a standalone query before the
    tool-calling loop — the answer itself is generated from `question` as
    asked (via the tool-calling messages, which use the rewritten query).

    Unlike the earlier classify-then-retrieve design, there's no separate
    routing step: the LLM is given both tools (see _build_tools) and
    decides for itself, via real tool_calls, whether it needs
    search_documents, search_web, or both — it may even rephrase the
    query it sends to a tool rather than using the raw question verbatim.
    The first turn forces at least one tool call (tool_choice="required")
    so every answer stays grounded in a tool result; later turns use
    tool_choice="auto" so the model can call the *other* tool too (for a
    question needing both) or stop and produce its final answer.
    source_type is derived from whichever tool(s) were actually called,
    not from a prediction made before retrieval happened.

    Raises on an LLM failure during the tool-calling loop (the router
    maps that to a 500); finding nothing from either source is not an
    error and instead returns a fixed fallback message with no sources
    and num_chunks_retrieved=0 — the router uses that zero to log the
    turn as unanswered in query_logs without needing to string-match the
    fallback text.
    """
    search_query = rewrite_query_standalone(question, history)

    state = _ToolExecutionState()
    tools = _build_tools(vectordb, user_id, state)
    tools_by_name = {t.name: t for t in tools}

    llm = ChatGroq(model=settings.LLM_MODEL)
    llm_required = llm.bind_tools(tools, tool_choice="required")
    llm_auto = llm.bind_tools(tools, tool_choice="auto")

    messages: List[BaseMessage] = [
        SystemMessage(content=TOOL_SYSTEM_PROMPT),
        HumanMessage(content=search_query),
    ]

    llm_for_next_turn = llm_required
    ai_message = None
    for _ in range(settings.MAX_TOOL_ITERATIONS):
        ai_message = _invoke_with_tool_retry(llm_for_next_turn, messages)
        messages.append(ai_message)
        if not ai_message.tool_calls:
            break
        for call in ai_message.tool_calls:
            # Demo/debug evidence that real function calling is
            # happening: the tool name AND the LLM's own chosen
            # arguments, not a routing label we assigned ourselves.
            logger.info("LLM tool call: %s(%s)", call["name"], call["args"])
            tool_fn = tools_by_name[call["name"]]
            result_text = tool_fn.invoke(call["args"])
            messages.append(ToolMessage(content=result_text, tool_call_id=call["id"]))
        llm_for_next_turn = llm_auto  # only the first turn is forced

    if ai_message.tool_calls:
        # Hit the iteration cap while the model still wanted to call more
        # tools — not expected in practice (MAX_TOOL_ITERATIONS covers
        # "one tool" and "both tools" with a turn to spare), but if it
        # happens, force a plain-text completion from whatever's been
        # gathered so far rather than surfacing an incomplete message.
        ai_message = llm.invoke(messages)

    called = set(state.tools_called)
    if called == {"search_documents", "search_web"}:
        source_type = "both"
    elif called == {"search_web"}:
        source_type = "web"
    else:
        # Covers the expected {"search_documents"} case and, as a
        # conservative fallback, the (unreachable in practice, since
        # tool_choice="required" forces a first call) empty-set case.
        source_type = "document"

    if not state.doc_results and not state.web_results:
        return (
            "I couldn't find relevant information to answer this question.",
            [],
            0,
            source_type,
        )

    sources: List[str] = []
    for doc in state.doc_results:
        label = _chunk_label(doc)
        if label not in sources:
            sources.append(label)
    for result in state.web_results:
        label = _web_source_label(result)
        if label not in sources:
            sources.append(label)

    num_results = len(state.doc_results) + len(state.web_results)
    return ai_message.content, sources, num_results, source_type
