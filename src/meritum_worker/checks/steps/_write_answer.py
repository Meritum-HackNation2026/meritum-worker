"""Write the answer: verdicts from the core rules, explanations from the model.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-02, US-ZRD-05, US-OBS-01, US-BEZ-07,
    F-07, F-15, F-22
"""

import logging
from collections.abc import Mapping
from datetime import UTC, date, datetime

from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import (
    CatalogEntry,
    ClaimResult,
    IncidentMatch,
    LimitationCode,
    ModelUsage,
    ai_marker_for,
)
from meritum_core.evidence import compute_verdict_changes, rate_review
from meritum_core.security.pii import mask_personal_data
from pydantic import ValidationError

from meritum_worker import evidence
from meritum_worker.checks.answers import AnswerDraft, answer_prompt, plain_text
from meritum_worker.checks.constants import (
    ANSWER_ATTEMPTS,
    DRAFT_MAX_CHARS,
    EXPLANATION_MAX_CHARS,
    LIMITATION_MAX_CHARS,
    UNRESOLVED_MAX_CHARS,
)
from meritum_worker.checks.fact_check_constants import FACT_CHECK_UNAVAILABLE_NOTE
from meritum_worker.checks.models import CheckDeps, CheckState, ExtractedClaim
from meritum_worker.checks.usage import model_usage

_log = logging.getLogger(__name__)


async def write_answer(state: CheckState, deps: CheckDeps) -> CheckState:
    """Judge each fact by the core rules, then ask the model to explain it.

    The verdict, strength, citations and "what would change the verdict" come
    from code; the model writes only the explanation, unresolved and the
    limitations, kept apart from the citations. Opinions and predictions get
    "not_verifiable". With no fact the model writes only the limitations. A
    rule break is a failure.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the model and the personal-data masking gate.

    Returns:
        The state with the result: done with the AI marker of the answering call,
        or technical_failure without claims when the answer breaks the contract
        rules.

    A model failure propagates; the workflow maps it to technical_failure.

    Features:
        US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, US-BEZ-07, F-07, F-22
    """
    if state.result is not None:
        return state
    facts = [claim for claim in state.claims if claim.is_fact]
    catalog = {entry.domain: entry for entry in deps.catalog}
    judged = [_judge(state, catalog, i, fact) for i, fact in enumerate(facts)]
    prompt = answer_prompt(state.question, facts, judged)
    models = list(state.models)
    result = state.technical_failure()
    for attempt in range(1, ANSWER_ATTEMPTS + 1):
        # A model answer breaking the contract is random: one more call (worker#194).
        answer = await deps.llm.complete(prompt, AnswerDraft)
        usage = model_usage(answer.usage)
        models.append(usage)
        broken = _broken_rule(facts, answer.output)
        try:
            if broken is None:
                result = _result_from_draft(state, facts, judged, answer.output, usage)
                break
        except ValidationError as error:
            broken = _error_types(error)
        _log.warning("write_answer attempt %d broke the contract: %s", attempt, broken)
    preview = None
    if result.status == "done":
        explanations = (
            [claim.explanation for claim in answer.output.claims] if facts else []
        )
        text = "\n\n".join([*explanations, *answer.output.limitations]).strip()
        masked = await mask_personal_data(text, deps.pii)
        preview = masked.text[:DRAFT_MAX_CHARS].strip() or None
    return state.model_copy(
        update={"result": result, "models": models, "draft": preview}
    )


def _result_from_draft(
    state: CheckState,
    facts: list[ExtractedClaim],
    judged: list[evidence.Judgement],
    draft: AnswerDraft,
    usage: ModelUsage,
) -> CheckResult:
    if not facts:
        # Only opinions: nothing for the model to judge, whatever it answered.
        draft = draft.model_copy(update={"claims": []})
    answered = [
        _answered(fact, judgement, written, state.incidents.get(fact.claim))
        for fact, judgement, written in zip(facts, judged, draft.claims, strict=True)
    ]
    unverifiable = [_not_verifiable(c) for c in state.claims if not c.is_fact]
    draft_code = _draft_code(state, facts)
    notes = dict.fromkeys(
        [
            (draft_code, plain_text(text, LIMITATION_MAX_CHARS))
            for text in draft.limitations
        ]
        + [(_code(text), text) for text in state.limitations]
        + state.image_notes
    )
    return CheckResult(
        check_id=state.check_id,
        status="done",
        claims=[*answered, *unverifiable],
        limitations=[text for _, text in notes],
        limitation_codes=[code for code, _ in notes],
        corpus_version=state.corpus_version,
        ai_marker=ai_marker_for(usage, datetime.now(UTC)),
    )


def _broken_rule(facts: list[ExtractedClaim], draft: AnswerDraft) -> str | None:
    # One explanation per fact, or the answer cannot be tied to its claims;
    # with no fact the explanations are dropped, whatever the model wrote.
    if facts and len(draft.claims) != len(facts):
        return f"{len(draft.claims)} explanations for {len(facts)} facts"
    return None


def _error_types(error: ValidationError) -> str:
    # Locations and messages only: the input is the model's text, never logged.
    errors = error.errors(include_input=False, include_url=False)
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in errors)


def _code(text: str) -> LimitationCode:
    return (
        "fact_check_unavailable"
        if text == FACT_CHECK_UNAVAILABLE_NOTE
        else "corpus_scope"
    )


def _draft_code(state: CheckState, facts: list[ExtractedClaim]) -> LimitationCode:
    # Facts searched with nothing found in the corpus or on the web.
    return "no_publications" if facts and not state.evidence else "corpus_scope"


def _judge(
    state: CheckState,
    catalog: Mapping[str, CatalogEntry],
    index: int,
    fact: ExtractedClaim,
) -> evidence.Judgement:
    citations = [v.citation for v in state.citations if v.fact == index]
    # extract_claims dated every fact; the contract rejects one it did not.
    rated = [
        (
            i in state.same_claim_reviews,
            rate_review(f.found, cache_control=f.cache_control),
        )
        for i, f in enumerate(state.fact_checks)
        if f.fact == index
    ]
    premises, context = evidence.split_reviews([(s, r.evidence) for s, r in rated])
    return evidence.judge(
        citations,
        catalog=catalog,
        claim_date=fact.claim_date or date.min,
        reviews=premises,
        review_context=context,
    )


def _answered(
    fact: ExtractedClaim,
    judged: evidence.Judgement,
    written: evidence.ClaimExplanation,
    incident: IncidentMatch | None,
) -> ClaimResult:
    claim_date = fact.claim_date or date.min
    changes = compute_verdict_changes(
        judged.verdict,
        judged.citations,
        claim_date=claim_date,
        reviews=judged.claim_review_premises,
        unresolved=written.unresolved,
    )
    return ClaimResult.model_validate(
        {
            "claim": fact.claim,
            "claim_date": fact.claim_date,
            "claim_date_source": fact.claim_date_source,
            **judged.model_dump(),
            "explanation": plain_text(written.explanation, EXPLANATION_MAX_CHARS),
            "unresolved": written.unresolved
            and plain_text(written.unresolved, UNRESOLVED_MAX_CHARS),
            "would_change_verdict": changes,
            # Context next to the verdict, computed above without it.
            "incident": incident,
        }
    )


def _not_verifiable(claim: ExtractedClaim) -> ClaimResult:
    # extract_claims dated every claim; the contract rejects one it did not.
    return ClaimResult.model_validate(
        {
            "claim": claim.claim,
            "claim_date": claim.claim_date,
            "claim_date_source": claim.claim_date_source,
            "verdict": "not_verifiable",
            "explanation": claim.explanation,
        }
    )
