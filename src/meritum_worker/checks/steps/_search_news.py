"""Ask major media once, when no source settled a fact.

Features:
    US-KOR-04, F-13, ADR-07
"""

import logging

from meritum_core.corpus.web_search import WebSearchError

from meritum_worker import corpus
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.checks.steps._assess_evidence import assess_pairs

_log = logging.getLogger(__name__)


async def search_news(state: CheckState, deps: CheckDeps) -> CheckState:
    """Search the major media once for the first fact no source settled.

    Runs after ``assess_evidence``. A fact is settled when a source supports
    or refutes it, or a fact-checker rated the same claim; passages that only
    add context do not count, since the reranker always returns some
    (worker#275). The outlets are secondary sources: the answer names the
    publisher and quotes a short passage, like any citation. The pages are
    fetched under robots.txt and Content-Signal, pass quarantine, never join
    the corpus and get the same stance call as any other source. A failed or
    timed-out search leaves the check as it was.

    Args:
        state: the check after the stance calls.
        deps: the ports; the news search, fetcher, detector, masking gate and
            the model.

    Returns:
        The state with the media pages as evidence, their proposed citations
        and one more search counted.

    Features:
        US-KOR-04, F-13, ADR-07
    """
    if state.result is not None or deps.news_search is None:
        return state
    facts = [claim for claim in state.claims if claim.is_fact]
    settled = {a.fact for a in state.assessed if a.draft.stance != "context"}
    settled |= {state.fact_checks[i].fact for i in state.same_claim_reviews}
    open_facts = [(i, f) for i, f in enumerate(facts) if i not in settled]
    if not open_facts:
        return state
    ports = corpus.LiveSearchPorts(
        web_search=deps.news_search,
        pages=deps.pages,
        injection=deps.injection,
        pii=deps.pii,
        catalog=deps.catalog,
    )
    # shortcut: one query, so only the first open fact is asked; widen when
    # multi-claim checks need it.
    index, fact = open_facts[0]
    try:
        found = await corpus.search_live(fact.web_queries[:1], ports)
    except (WebSearchError, TimeoutError) as error:
        _log.info("news search skipped: %s", type(error).__name__)
        return state
    known = {document.source.url for document in state.evidence}
    pages = [d for d in found.documents if d.source.url not in known]
    dated = fact.claim_date is not None
    pairs = [(index, fact, page) for page in pages if dated]
    assessed, usages, partial = await assess_pairs(deps, pairs)
    return state.model_copy(
        update={
            "web_search_calls": state.web_search_calls + found.calls,
            "news_search_calls": state.news_search_calls + found.calls,
            "evidence": [*state.evidence, *pages],
            "injection_events": [*state.injection_events, *found.dropped],
            "assessed": [*state.assessed, *assessed],
            "limitations": [*state.limitations, *partial],
            "models": [*state.models, *usages],
        }
    )
