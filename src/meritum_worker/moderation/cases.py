"""Create a moderator case for a claim or add the claim to the case that holds it.

Features:
    US-MOD-01, US-MOD-02, US-MOD-06, F-24, ADR-22, ADR-35
"""

from meritum_core.checks import Escalation
from meritum_core.checks.contracts import (
    CaseClaim,
    CaseReason,
    CheckRecord,
    ModeratorCase,
)

from meritum_worker.moderation.constants import (
    BASE_REASON,
    CASE_ID_PREFIX,
    SIMILARITY_WINDOW,
    SUMMARY_MAX_CHARS,
)
from meritum_worker.moderation.grouping import similar_case, similar_past
from meritum_worker.moderation.models import ModerationDeps, Referral
from meritum_worker.moderation.topics import Classified, classify


def _summary(referral: Referral) -> str:
    text = referral.claim
    if referral.justification is not None:
        text = (
            f"Zgłoszony błąd: {referral.claim} Uzasadnienie: {referral.justification}"
        )
    return text[:SUMMARY_MAX_CHARS]


def _asker(record: CheckRecord | None) -> str | None:
    return None if record is None else record.user_id or record.session_id


async def _askers(check_ids: list[str], deps: ModerationDeps) -> set[str]:
    found = {_asker(await deps.records.get(check_id)) for check_id in check_ids}
    return {asker for asker in found if asker is not None}


def _with(reasons: list[CaseReason], *added: CaseReason | None) -> list[CaseReason]:
    return list(dict.fromkeys([*reasons, *(r for r in added if r is not None)]))


def _topic_fields(
    case: ModeratorCase | None, topic: Classified | None
) -> dict[str, object]:
    if case is not None and case.high_risk_topic is not None:
        return {}
    if topic is None:
        return {}
    return {"high_risk_topic": topic[0], "high_risk_classified_by": topic[1]}


async def _next_id(deps: ModerationDeps) -> str:
    numbers = [
        int(c.id.removeprefix(CASE_ID_PREFIX)) for c in await deps.cases.list_cases()
    ]
    return f"{CASE_ID_PREFIX}{max(numbers, default=0) + 1}"


async def _join(
    case: ModeratorCase,
    index: int,
    referral: Referral,
    topic: Classified | None,
    deps: ModerationDeps,
) -> Escalation:
    group = case.claims[index]
    is_new_check = referral.check_id not in case.check_ids
    askers = await _askers(case.check_ids, deps)
    claims = list(case.claims)
    if referral.check_id not in group.check_ids:
        claims[index] = group.model_copy(
            update={"check_ids": [*group.check_ids, referral.check_id]}
        )
    reasons = _with(
        case.reasons,
        BASE_REASON.get(referral.trigger),
        "repeated_unanswered" if is_new_check else None,
        "high_risk" if topic else None,
    )
    update: dict[str, object] = {
        "claims": claims,
        "reasons": reasons,
        "last_seen": referral.now,
        "distinct_askers": case.distinct_askers
        + (is_new_check and referral.asker not in askers),
        **_topic_fields(case, topic),
    }
    await deps.cases.save(case.model_copy(update=update))
    return Escalation(state="updated", case_id=case.id)


async def _create(
    referral: Referral, topic: Classified | None, deps: ModerationDeps
) -> Escalation:
    window_start = referral.now - SIMILARITY_WINDOW
    past = [
        p
        for p in await deps.results.unanswered_since(window_start)
        if p.check_id != referral.check_id
    ]
    earlier = await similar_past(referral.claim, past, deps.embeddings)
    reasons = _with(
        [],
        BASE_REASON.get(referral.trigger),
        "repeated_unanswered" if earlier else None,
        "high_risk" if topic else None,
    )
    if not reasons:
        return Escalation(state="recommended")
    check_ids = list(dict.fromkeys([referral.check_id, *(p.check_id for p in earlier)]))
    askers = await _askers([p.check_id for p in earlier], deps) | {referral.asker}
    case = ModeratorCase(
        id=await _next_id(deps),
        state="open",
        reasons=reasons,
        summary=_summary(referral),
        claims=[CaseClaim(claim=referral.claim, check_ids=check_ids)],
        distinct_askers=len(askers),
        first_seen=referral.now,
        last_seen=referral.now,
        high_risk_topic=topic[0] if topic else None,
        high_risk_classified_by=topic[1] if topic else None,
    )
    await deps.cases.save(case)
    return Escalation(state="created", case_id=case.id)


async def refer(referral: Referral, deps: ModerationDeps) -> Escalation:
    """Hand a claim to the moderators: join its open case, open one, or only recommend.

    A claim similar to one in an open case of the last SIMILARITY_WINDOW joins
    that case (state ``updated``). Otherwise a click and a dispute open a case;
    an unanswered claim opens one only when its topic is high-risk or a similar
    unanswered claim of another check came earlier, and is otherwise only
    ``recommended``, without a case number. The number is returned after the
    case was saved.

    Args:
        referral: the claim and who handed it over.
        deps: the moderation ports.

    Returns:
        The escalation: created or updated with the case id, or recommended.

    Features:
        US-MOD-01, US-MOD-02, US-MOD-06, F-24, ADR-22, ADR-35
    """
    topic = await classify(
        referral.claim, await deps.topics.list_topics(), deps.embeddings
    )
    since = referral.now - SIMILARITY_WINDOW
    async with deps.lock:
        recent = [
            c for c in await deps.cases.list_cases("open") if c.last_seen >= since
        ]
        found = await similar_case(referral.claim, recent, deps.embeddings)
        if found is not None:
            case, index = found
            return await _join(case, index, referral, topic, deps)
        return await _create(referral, topic, deps)
