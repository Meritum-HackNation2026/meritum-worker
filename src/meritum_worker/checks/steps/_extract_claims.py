"""Extract up to 5 dated claims and tell facts from opinions and predictions.

Features:
    US-SPR-03, US-SPR-06, US-SPR-07, US-ZRD-05, F-06, F-07
"""

from meritum_core.shared.llm import Prompt

from meritum_worker.checks.constants import (
    LIMITATION_MAX_CHARS,
    MAX_CLAIMS_PER_CHECK,
    NEEDS_CLARIFICATION_MESSAGE,
    OUT_OF_SCOPE_MESSAGE,
    URL_UNAVAILABLE_CODE,
    URL_UNAVAILABLE_MESSAGE,
)
from meritum_worker.checks.models import (
    CheckDeps,
    CheckState,
    ClaimExtraction,
    ExtractedClaim,
)
from meritum_worker.checks.prompts import (
    EXTRACTION_INSTRUCTIONS,
    LINKED_PAGE_INSTRUCTIONS,
    PUBLISHED_ON_INSTRUCTIONS,
    QUESTION_AND_PAGE_INSTRUCTIONS,
    UNREAD_LINK_INSTRUCTIONS,
)
from meritum_worker.checks.usage import model_usage


async def extract_claims(state: CheckState, deps: CheckDeps) -> CheckState:
    """Ask the model for the input's claims; the user text goes only as data.

    A linked page that was read goes as its own data item after the citizen's
    text, and the model is asked for the page's two to four main claims; a
    question about the article is then no request for clarification. For a
    page that was not read the model gets the address: a claim read from it is
    also searched in the fact-checkers' index by the address itself, and no
    claim ends the check as url_unavailable, never as needs_clarification.

    A request not about information ends as out_of_scope and an input with no
    claim as needs_clarification, both with a message and no claims. Otherwise
    facts come first, the first MAX_CLAIMS_PER_CHECK go on with a date each and
    the rest are named in the limitations. A claim the text does not date
    (or dates by its publication) gets the linked page's metadata date
    (input_published_at), else today. A known publication date goes into the
    instructions, so the model counts relative dates ("wczoraj") from it.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; only the model is called.

    Returns:
        The state with its claims and limitations, or with a result that is not
        a verdict.

    A model failure propagates; the workflow maps it to technical_failure.

    Features:
        US-SPR-03, US-SPR-06, US-SPR-07, US-ZRD-05, F-06, F-07
    """
    if state.result is not None:
        return state
    link = state.job.request.url
    page = state.page_text or None
    unread_link = str(link) if link is not None and page is None else None
    prompt = Prompt(
        instructions=_instructions(state, unread_link), data=_data(state, unread_link)
    )
    answer = await deps.llm.complete(prompt, ClaimExtraction)
    state = state.model_copy(
        update={"models": [*state.models, model_usage(answer.usage)]}
    )
    extraction = answer.output
    if extraction.out_of_scope:
        result = state.with_message("out_of_scope", OUT_OF_SCOPE_MESSAGE)
        return state.model_copy(update={"result": result})
    if not extraction.claims and unread_link is not None:
        # We could not read the page: say that, not "which claim do you mean".
        failure = state.technical_failure(URL_UNAVAILABLE_CODE, URL_UNAVAILABLE_MESSAGE)
        return state.model_copy(update={"result": failure})
    if not extraction.claims:
        result = state.with_message("needs_clarification", NEEDS_CLARIFICATION_MESSAGE)
        return state.model_copy(update={"result": result})
    # sorted() is stable: facts first, each group in the order of the input.
    ranked = sorted(extraction.claims, key=lambda claim: not claim.is_fact)
    kept = [_with_link_phrase(c, unread_link) for c in ranked[:MAX_CLAIMS_PER_CHECK]]
    skipped = ranked[MAX_CLAIMS_PER_CHECK:]
    return state.model_copy(
        update={
            "claims": [_dated(claim, state) for claim in kept],
            "limitations": [*state.limitations, *map(_skipped_note, skipped)],
        }
    )


def _instructions(state: CheckState, unread_link: str | None) -> str:
    instructions = EXTRACTION_INSTRUCTIONS
    has_page = bool(state.page_text)
    if has_page:
        instructions += LINKED_PAGE_INSTRUCTIONS
    if has_page and state.has_text:
        instructions += QUESTION_AND_PAGE_INSTRUCTIONS
    if unread_link is not None:
        instructions += UNREAD_LINK_INSTRUCTIONS
    if state.published_at is not None:
        published = state.published_at.isoformat()
        instructions += PUBLISHED_ON_INSTRUCTIONS.format(published=published)
    return instructions


def _data(state: CheckState, unread_link: str | None) -> tuple[str, ...]:
    # The citizen's text first; the page, or the address of an unread one, after.
    if not state.has_text:
        return (state.question,)
    text = state.job.request.text or ""
    extra = state.page_text or unread_link or ""
    return (text, extra) if extra and extra not in text else (text,)


def _with_link_phrase(claim: ExtractedClaim, unread_link: str | None) -> ExtractedClaim:
    # The fact-checkers' index may know the article by its address.
    if unread_link is None or not claim.is_fact:
        return claim
    phrases = [unread_link, *claim.fact_check_phrases]
    return claim.model_copy(update={"fact_check_phrases": phrases})


def _dated(claim: ExtractedClaim, state: CheckState) -> ExtractedClaim:
    # The page's metadata date beats a publication date the model read in its text.
    page_date = state.published_at
    is_undated = claim.claim_date is None
    says_published = claim.claim_date_source == "input_published_at"
    if page_date is not None and (is_undated or says_published):
        return claim.model_copy(
            update={"claim_date": page_date, "claim_date_source": "input_published_at"}
        )
    if is_undated and state.image_date is not None:
        # A date read from the image is text, not a publication date (F-33).
        return claim.model_copy(
            update={"claim_date": state.image_date, "claim_date_source": "text"}
        )
    if is_undated:
        today = state.job.received_at.date()
        return claim.model_copy(
            update={"claim_date": today, "claim_date_source": "today"}
        )
    return claim.model_copy(
        update={"claim_date_source": claim.claim_date_source or "text"}
    )


def _skipped_note(claim: ExtractedClaim) -> str:
    return claim.claim[:LIMITATION_MAX_CHARS]
