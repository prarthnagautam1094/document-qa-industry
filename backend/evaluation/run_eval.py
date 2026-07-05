"""RAG evaluation harness — runs the real pipeline against a hand-written
question set and scores it with RAGAS.

============================================================================
WHY AUTOMATED EVALUATION, NOT JUST SPOT-CHECKING ANSWERS
----------------------------------------------------------------------------
Manually asking a few questions and eyeballing the answers is how you find
out a pipeline is *obviously* broken — it's not how you find out it got
*worse*. Retrieval threshold tweaks, a prompt wording change, an embedding
or chunking change, a re-ranking stage — each of these can silently shift
answer quality in either direction, and a human spot-check of 3-4
questions has no chance of reliably catching a regression that only shows
up on, say, questions with ambiguous phrasing or thin retrieved context.
An automated eval set re-run on every change gives a repeatable, numeric
signal instead of a vibe, and results.json gives a paper trail (e.g. for a
project report) showing the pipeline was actually measured, not just
demoed.

THE FOUR METRICS
----------------------------------------------------------------------------
faithfulness (0-1, higher is better)
    Breaks the generated answer down into individual factual claims and
    checks each one against the retrieved context. Measures hallucination:
    a low score means the answer asserts things the retrieved chunks don't
    actually support, regardless of whether the answer sounds right.

answer_relevancy (0-1, higher is better)
    Generates several questions an embedding model thinks the given answer
    is addressing, then compares those back to the actual question asked.
    Measures whether the answer is *on-topic and responsive* — a
    factually-faithful-but-evasive or overly generic answer scores low
    here even if every claim it makes is technically grounded.

context_precision (0-1, higher is better)
    Of the chunks that were retrieved, how many were actually relevant to
    answering the question (using the ground truth to judge relevance)?
    Low precision means retrieval is pulling in noise alongside (or
    instead of) the right chunks — the RELEVANCE_THRESHOLD / re-ranking
    tuning in rag_service.py is exactly what this metric is checking.

context_recall (0-1, higher is better)
    Of everything the ground truth says was needed to answer the
    question, how much of it shows up somewhere in the retrieved chunks?
    Low recall means retrieval is missing information the answer would
    have needed — a ceiling on answer quality no amount of good prompting
    can fix, since the LLM never saw the missing piece.

Faithfulness and answer_relevancy score the *generation* half of the
pipeline; context_precision and context_recall score the *retrieval*
half — running all four is what lets a bad score be traced to "the wrong
chunks were retrieved" vs. "retrieval was fine but the LLM answered badly"
instead of just "something's wrong somewhere."

For the two deliberately off-topic questions in eval_dataset.py, the
*correct* pipeline behavior is retrieving nothing and returning the fixed
"I couldn't find relevant information..." fallback — treat a low
answer_relevancy on those two as expected (a generic fallback sentence
is never going to look "relevant" to a specific off-topic question by
this metric's definition), not as a pipeline defect. See the printed
summary's off-topic breakout for those two scored separately.
============================================================================
"""

import json
import logging
import sys
import types
from pathlib import Path

# ---------------------------------------------------------------------------
# Compatibility shim, must run before any `import ragas`.
#
# ragas 0.2.15 (the newest release that does NOT require the scikit-network
# package — 0.3.0+ added it as a hard dependency for an unrelated knowledge-
# graph test-generation feature, and scikit-network has no prebuilt wheel
# for this machine's Python 3.14 and fails to build from source without
# Microsoft's C++ Build Tools) unconditionally imports `ChatVertexAI` from
# `langchain_community.chat_models.vertexai`. That submodule no longer
# exists in the newer langchain_community version this project already
# depends on for its actual (working, tested) ingestion/retrieval pipeline
# — downgrading langchain_community to satisfy ragas would risk that
# pipeline instead. ChatVertexAI is only referenced in a static "which LLMs
# support multi-completion" list inside ragas and is never instantiated
# unless you actually use Vertex AI (which this project doesn't), so
# registering an empty stub module at that import path satisfies the
# import without installing or downgrading anything.
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _vertexai_stub = types.ModuleType("langchain_community.chat_models.vertexai")

    class _StubChatVertexAI:  # never instantiated — import-time placeholder only
        pass

    _vertexai_stub.ChatVertexAI = _StubChatVertexAI
    sys.modules["langchain_community.chat_models.vertexai"] = _vertexai_stub

# ---------------------------------------------------------------------------
# Second compatibility fix, also must run before `import ragas`.
#
# ragas.executor unconditionally calls `nest_asyncio.apply()` at import time
# to support being called from an already-running event loop (e.g. inside a
# Jupyter notebook). This script has no such loop — it's a plain top-level
# script — so that patch is never actually needed here, but nest_asyncio's
# global monkeypatch of the event loop is applied anyway, and on this
# Python version it breaks async timeout handling somewhere in the
# httpx/anyio stack underneath ChatGroq's async calls: every single RAGAS
# metric call failed with `RuntimeError: Timeout should be used inside a
# task` until this was neutralized (confirmed by direct A/B testing — the
# identical evaluate() call succeeds immediately once nest_asyncio.apply is
# a no-op). Monkeypatching a real, already-installed dependency's function
# to a no-op is not something to do lightly, but this one is verified safe
# for this exact use case: nothing in this script runs inside a nested
# event loop, so the functionality being disabled was inert here anyway.
import nest_asyncio  # noqa: E402

nest_asyncio.apply = lambda *args, **kwargs: None

# Make the backend package (config, services, models) importable as
# top-level modules, matching the same sys.path convention as
# tests/conftest.py — this script is meant to be run with backend/ as the
# working directory: `python evaluation/run_eval.py`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_groq import ChatGroq  # noqa: E402
from ragas import EvaluationDataset, evaluate  # noqa: E402
from ragas.embeddings import LangchainEmbeddingsWrapper  # noqa: E402
from ragas.llms import LangchainLLMWrapper  # noqa: E402
from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness  # noqa: E402
from ragas.run_config import RunConfig  # noqa: E402

from config import settings  # noqa: E402
from evaluation.eval_dataset import EVAL_DATASET  # noqa: E402
from models.schemas import ChatMessage  # noqa: E402
from services import chroma_service, rag_service  # noqa: E402

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("run_eval")

SAMPLE_PDF_PATH = Path(__file__).resolve().parent / "sample.pdf"
SAMPLE_PDF_FILENAME = "sample.pdf"
RESULTS_PATH = Path(__file__).resolve().parent / "results.json"

OFF_TOPIC_QUESTIONS = {
    "What is the capital of France?",
    "What is BrightWave's current stock price?",
}


def ensure_sample_pdf_uploaded(vectordb) -> None:
    """Make sure sample.pdf is actually ingested before evaluating.

    Every ground_truth in eval_dataset.py was written from this file's
    content — evaluating against a store that doesn't have it loaded
    would just measure "how well does the pipeline fall back when it has
    nothing to work with," not real answer quality.
    """
    existing = {doc["filename"]: doc["chunk_count"] for doc in rag_service.list_documents(vectordb)}
    if SAMPLE_PDF_FILENAME in existing:
        print(f"'{SAMPLE_PDF_FILENAME}' already ingested ({existing[SAMPLE_PDF_FILENAME]} chunks) — skipping upload.")
        return

    print(f"'{SAMPLE_PDF_FILENAME}' not found in the vector store — ingesting it now...")
    file_bytes = SAMPLE_PDF_PATH.read_bytes()
    chunk_count = rag_service.process_pdf(file_bytes, SAMPLE_PDF_FILENAME, vectordb)
    print(f"Ingested '{SAMPLE_PDF_FILENAME}' into {chunk_count} chunks.\n")


def run_pipeline_on_dataset(vectordb) -> list[dict]:
    """Run every eval_dataset.py question through the real pipeline.

    Returns one dict per question with everything needed both for the
    RAGAS dataset and for results.json — question, the real generated
    answer, the real retrieved context text, and the ground truth.
    """
    rows = []
    for i, item in enumerate(EVAL_DATASET, start=1):
        question = item["question"]
        history = [ChatMessage(**h) for h in item.get("history", [])]

        # Retrieval is computed once here (to capture the actual chunk
        # text RAGAS needs for contexts) and generate_answer is called
        # separately for the real answer, reusing rag_service's actual
        # production functions rather than reimplementing the pipeline.
        # generate_answer() re-runs retrieval internally, so for the two
        # follow-up-style questions there's a theoretical chance its
        # internal query rewrite returns slightly different phrasing than
        # the rewrite computed here, since rewrite_query_standalone calls
        # an LLM — acceptable for an eval script; it's a narrow, low-
        # variance rewrite task, not a source of meaningfully different
        # retrieval in practice.
        search_query = rag_service.rewrite_query_standalone(question, history)
        retrieved_docs = rag_service.retrieve_relevant_chunks(search_query, vectordb)
        contexts = [doc.page_content for doc in retrieved_docs]

        answer, sources, num_chunks_retrieved = rag_service.generate_answer(question, history, vectordb)

        rows.append(
            {
                "question": question,
                "answer": answer,
                "ground_truth": item["ground_truth"],
                "contexts": contexts,
                "reference_context": item.get("reference_context"),
                "sources": sources,
                "num_chunks_retrieved": num_chunks_retrieved,
                "is_off_topic": question in OFF_TOPIC_QUESTIONS,
            }
        )
        print(f"  [{i}/{len(EVAL_DATASET)}] {question!r} -> {len(contexts)} chunk(s) retrieved")

    return rows


def score_with_ragas(rows: list[dict]):
    """Build a RAGAS EvaluationDataset from the pipeline output and run
    faithfulness / answer_relevancy / context_precision / context_recall
    against it, using this project's own ChatGroq LLM and HuggingFace
    embeddings as the evaluator backend instead of the RAGAS default
    (OpenAI) — no OpenAI key is configured or needed anywhere here.
    """
    samples = [
        {
            "user_input": row["question"],
            "response": row["answer"],
            "retrieved_contexts": row["contexts"] or [""],
            "reference": row["ground_truth"],
        }
        for row in rows
    ]
    dataset = EvaluationDataset.from_list(samples)

    evaluator_llm = LangchainLLMWrapper(ChatGroq(model=settings.LLM_MODEL))
    evaluator_embeddings = LangchainEmbeddingsWrapper(chroma_service.get_embeddings())

    # RunConfig.max_workers defaults to 16 — firing that many concurrent
    # Groq requests at once (faithfulness alone issues 2+ LLM calls per
    # question) tripped rate-limit-induced timeouts on roughly a quarter
    # of the jobs in an earlier run. 3 concurrent workers comfortably
    # avoids that while still evaluating faster than one-at-a-time.
    run_config = RunConfig(max_workers=3, timeout=120)

    return evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=evaluator_llm,
        run_config=run_config,
        embeddings=evaluator_embeddings,
    )


def main() -> None:
    if not settings.GROQ_API_KEY:
        print("GROQ_API_KEY is not set in .env — the pipeline and the RAGAS evaluator both need it. Aborting.")
        sys.exit(1)

    vectordb = chroma_service.get_vectordb()
    ensure_sample_pdf_uploaded(vectordb)

    print(f"Running {len(EVAL_DATASET)} questions through the RAG pipeline...")
    rows = run_pipeline_on_dataset(vectordb)

    print("\nScoring with RAGAS (this calls the LLM/embeddings several times per question)...")
    result = score_with_ragas(rows)
    scores_df = result.to_pandas()

    metric_columns = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    present_columns = [c for c in metric_columns if c in scores_df.columns]

    # --- Per-question summary table ---------------------------------------
    print("\n" + "=" * 100)
    print("PER-QUESTION SCORES")
    print("=" * 100)
    for i, row in enumerate(rows):
        tag = " [OFF-TOPIC]" if row["is_off_topic"] else ""
        print(f"\n{i + 1}. {row['question']}{tag}")
        print(f"   answer: {row['answer'][:150]}{'...' if len(row['answer']) > 150 else ''}")
        for col in present_columns:
            value = scores_df.iloc[i][col]
            print(f"   {col}: {value:.3f}")

    # --- Averages, on-topic vs off-topic broken out separately ------------
    on_topic_mask = [not r["is_off_topic"] for r in rows]
    print("\n" + "=" * 100)
    print("AVERAGE SCORES")
    print("=" * 100)
    print(f"{'metric':<20}{'all':>10}{'on-topic':>12}{'off-topic':>12}")
    for col in present_columns:
        all_avg = scores_df[col].mean()
        on_topic_avg = scores_df.loc[on_topic_mask, col].mean()
        off_topic_avg = scores_df.loc[[not m for m in on_topic_mask], col].mean()
        print(f"{col:<20}{all_avg:>10.3f}{on_topic_avg:>12.3f}{off_topic_avg:>12.3f}")

    # --- Save full results for later reference (e.g. a project report) ----
    output = {
        "questions": [
            {
                **{k: v for k, v in row.items() if k != "is_off_topic"},
                "is_off_topic": row["is_off_topic"],
                "scores": {col: float(scores_df.iloc[i][col]) for col in present_columns},
            }
            for i, row in enumerate(rows)
        ],
        "averages": {
            "all": {col: float(scores_df[col].mean()) for col in present_columns},
            "on_topic": {col: float(scores_df.loc[on_topic_mask, col].mean()) for col in present_columns},
            "off_topic": {
                col: float(scores_df.loc[[not m for m in on_topic_mask], col].mean()) for col in present_columns
            },
        },
    }
    RESULTS_PATH.write_text(json.dumps(output, indent=2))
    print(f"\nFull results saved to {RESULTS_PATH}")


if __name__ == "__main__":
    main()
