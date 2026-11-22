"""Find fact-checkers' ratings of the checked facts in the ClaimReview index.

Features:
    US-KOR-01, US-ZRD-03, US-BEZ-03, US-OBS-01, F-14, F-15, F-18, F-22, ADR-24,
    ADR-34
"""

from meritum_worker import corpus
from meritum_worker.checks.fact_check_constants import (
    FACT_CHECK_UNAVAILABLE_NOTE,
    SEARCH_FACT_CHECKS_STEP,
)
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.checks.steps._screen_injection import dropped_page_notes


async def search_fact_checks(state: CheckState, deps: CheckDeps) -> CheckState:
    """Search Google Fact Check Tools API; ratings wait for the evidence step.

    Each fact is searched whole and by its key phrases from extract_claims, in
    parallel and masked before they leave; the API matches phrases literally.
    A rating from a publisher the catalogue knows whose rated claim is close to
    the fact by embeddings is kept for ``assess_evidence``, which decides
    whether it is about our claim; a less close one stays context. Some queries
    failing is no failure. A fact-check article on a fetchable catalogue
    domain is fetched like a web result and may become a citation; Demagog and
    AFP Sprawdzam never are. A failed API (access error, limit, no key) does not
    stop the check: the step ends ``failed`` and the limitation
    ``fact_check_unavailable`` says the index was not checked. An empty answer
    is no rating, not a failure.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; the API, masking gate, fetcher, detector and catalogue.

    Returns:
        The state with the ratings, the articles as evidence, or the limitation.

    Features:
        US-KOR-01, US-ZRD-03, US-BEZ-03, US-OBS-01, F-14, F-15, F-18, F-22, ADR-24,
        ADR-34
    """
    if state.result is not None:
        return state
    facts = [claim for claim in state.claims if claim.is_fact]
    if not facts:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, SEARCH_FACT_CHECKS_STEP]}
        )
    try:
        found = await corpus.search_fact_checks(
            [fact.claim for fact in facts],
            deps.fact_check,
            deps.pii,
            deps.catalog,
            phrases=[fact.fact_check_phrases for fact in facts],
            embeddings=deps.embeddings,
        )
    except corpus.FactCheckUnavailableError:
        return state.model_copy(
            update={
                "failed_steps": [*state.failed_steps, SEARCH_FACT_CHECKS_STEP],
                "limitations": [*state.limitations, FACT_CHECK_UNAVAILABLE_NOTE],
                "retrieval_errors": [
                    *state.retrieval_errors,
                    f"{SEARCH_FACT_CHECKS_STEP}: fact_check_unavailable",
                ],
            }
        )
    pages = await corpus.admit_pages(
        found.article_urls,
        corpus.LiveSearchPorts(
            web_search=deps.web_search,
            pages=deps.pages,
            injection=deps.injection,
            pii=deps.pii,
            catalog=deps.catalog,
        ),
    )
    return state.model_copy(
        update={
            "fact_checks": [*state.fact_checks, *found.findings],
            "evidence": [*state.evidence, *pages.documents],
            "injection_events": [*state.injection_events, *pages.dropped],
            "limitations": [
                *state.limitations,
                *dropped_page_notes(pages.dropped),
            ],
        }
    )
