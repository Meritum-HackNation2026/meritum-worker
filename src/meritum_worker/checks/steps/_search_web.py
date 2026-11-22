"""Search the web for the checked facts, next to the corpus search.

Features:
    US-KOR-04, US-SPR-04, US-WTY-03, US-OBS-01, F-13, F-22, ADR-07
"""

from meritum_worker import corpus
from meritum_worker.checks.constants import LIMITATION_MAX_CHARS, SEARCH_WEB_STEP
from meritum_worker.checks.models import CheckDeps, CheckState


async def search_web(state: CheckState, deps: CheckDeps) -> CheckState:
    """Search catalogue domains live; pages past quarantine become evidence.

    Each fact is searched by the model's keyword queries (Polish and English;
    the claim text when it gave none), masked before they leave. A page with an
    instruction is dropped: its ``source_dropped`` event goes to the record
    and its address to the limitations. A check with no fact skips the step.
    Pages past quarantine also go to ``deps.live_pages``, when the worker has
    one, for the next corpus snapshot (worker#90).

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; web search, the page fetcher, the detector and the
            masking gate are called.

    Returns:
        The state with the new evidence, events, limitations and search count.

    A web search failure or timeout propagates; the workflow maps it to
    technical_failure with code web_search_unavailable.

    Features:
        US-KOR-04, US-SPR-04, US-WTY-03, US-OBS-01, F-13, F-22, ADR-07
    """
    if state.result is not None:
        return state
    facts = [q for claim in state.claims if claim.is_fact for q in claim.web_queries]
    if not facts:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, SEARCH_WEB_STEP]}
        )
    ports = corpus.LiveSearchPorts(
        web_search=deps.web_search,
        pages=deps.pages,
        injection=deps.injection,
        pii=deps.pii,
        catalog=deps.catalog,
    )
    found = await corpus.search_live(facts, ports)
    if deps.live_pages is not None:
        # The check answers on its own snapshot; these pages join the next one.
        await deps.live_pages.enqueue(found.pages)
    return state.model_copy(
        update={
            "web_search_calls": state.web_search_calls + found.calls,
            "evidence": [*state.evidence, *found.documents],
            "injection_events": [*state.injection_events, *found.dropped],
            "limitations": [
                *state.limitations,
                *(str(e.source_url)[:LIMITATION_MAX_CHARS] for e in found.dropped),
            ],
        }
    )
