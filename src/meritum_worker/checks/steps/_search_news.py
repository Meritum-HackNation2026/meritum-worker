"""Ask major media once, when the catalogue search found no page.

Features:
    US-KOR-04, F-13, ADR-07
"""

import logging

from meritum_core.corpus.web_search import WebSearchError

from meritum_worker import corpus
from meritum_worker.checks.models import CheckDeps, CheckState

_log = logging.getLogger(__name__)


async def search_news(state: CheckState, deps: CheckDeps) -> CheckState:
    """Search the major media once for a check the web search found nothing for.

    Runs after the research agents, only when neither the live search nor the
    fact-check search gave a page. The outlets are secondary sources: the
    answer names the publisher and quotes a short passage, like any citation.
    The pages are fetched under robots.txt and Content-Signal, pass quarantine
    and never join the corpus. A failed or timed-out search leaves the check
    as it was.

    Args:
        state: the check after the research agents.
        deps: the ports; the news search, fetcher, detector and masking gate.

    Returns:
        The state with the media pages as evidence and one more search counted.

    Features:
        US-KOR-04, F-13, ADR-07
    """
    facts = [q for claim in state.claims if claim.is_fact for q in claim.web_queries]
    found_before = bool(state.evidence or state.fact_checks)
    if state.result is not None or found_before or not facts:
        return state
    if deps.news_search is None:
        return state
    ports = corpus.LiveSearchPorts(
        web_search=deps.news_search,
        pages=deps.pages,
        injection=deps.injection,
        pii=deps.pii,
        catalog=deps.catalog,
    )
    try:
        # shortcut: one query, so only the first fact is asked; widen when
        # multi-claim checks need it.
        found = await corpus.search_live(facts[:1], ports)
    except (WebSearchError, TimeoutError) as error:
        _log.info("news search skipped: %s", type(error).__name__)
        return state
    return state.model_copy(
        update={
            "web_search_calls": state.web_search_calls + found.calls,
            "evidence": [*state.evidence, *found.documents],
            "injection_events": [*state.injection_events, *found.dropped],
        }
    )
