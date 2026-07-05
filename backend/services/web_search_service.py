"""Free, no-API-key web search (DuckDuckGo, via the `ddgs` package) for
questions that need current/live information the uploaded documents
can't provide — see rag_service.classify_route for the routing decision
that decides when this is called.
"""

import logging
from typing import List, TypedDict

from ddgs import DDGS

from config import settings

logger = logging.getLogger(__name__)


class WebSearchResult(TypedDict):
    title: str
    url: str
    snippet: str


def search_web(query: str, max_results: int = None) -> List[WebSearchResult]:
    """Return up to `max_results` web search results for `query`.

    Returns [] (rather than raising) if the search backend is unreachable,
    rate-limited, or returns nothing — DuckDuckGo's free, unauthenticated
    endpoint has no SLA, so a web-search miss should degrade to "no web
    results" for generate_answer to fall back on, not take down the whole
    /chat/ask request the way an unhandled exception would.
    """
    if max_results is None:
        max_results = settings.WEB_SEARCH_MAX_RESULTS

    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=max_results))
    except Exception:
        logger.warning("Web search failed for query %r", query, exc_info=True)
        return []

    results: List[WebSearchResult] = [
        {
            "title": r.get("title") or "Untitled",
            "url": r["href"],
            "snippet": r.get("body") or "",
        }
        for r in raw_results
        if r.get("href")
    ]
    logger.info("Web search for %r returned %d result(s)", query, len(results))
    return results
