"""Hand unanswered claims to the moderators: cases made without a click.

Features:
    US-MOD-01, US-MOD-02, US-POW-05, US-SPR-01, US-OBS-01, F-22, F-24, F-26
"""

from datetime import UTC, datetime

from meritum_core.checks import Escalation

from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.checks.notifications import save_notification
from meritum_worker.moderation import (
    PANEL_LINK,
    UNANSWERED_VERDICT,
    ModerationDeps,
    Referral,
    case_recipients,
    refer,
)


async def moderator_cases(state: CheckState, deps: CheckDeps) -> CheckState:
    """Create or update the case of each unanswered claim and set the escalation.

    A single unanswered claim of an ordinary topic leaves the escalation
    ``recommended``; a high-risk topic or a repeat opens (or joins) a case, which
    the moderators get as a ``case_assigned`` notification (the backend does not
    announce cases the worker opens). The escalation is the first case's, else
    ``recommended``; a check with no unanswered claim has none.

    Args:
        state: the check after write_answer.
        deps: the ports; the moderation ports and the inbox are called.

    Returns:
        The state with the escalation on its result.

    Features:
        US-MOD-01, US-MOD-02, US-POW-05, F-24, F-26
    """
    moderation = deps.moderation
    result = state.result
    if moderation is None or result is None:
        return state
    unanswered = [c for c in result.claims if c.verdict == UNANSWERED_VERDICT]
    if not unanswered:
        return state
    now = datetime.now(UTC)
    asker = state.job.user_id or state.job.session_id or ""
    escalation = Escalation(state="recommended")
    for claim in unanswered:
        referral = Referral(claim.claim, state.check_id, asker, "unanswered", now)
        found = await refer(referral, moderation)
        if found.case_id is not None:
            await _announce(found.case_id, state, deps, moderation, now)
            if escalation.case_id is None:
                escalation = found
    return state.model_copy(
        update={"result": result.model_copy(update={"escalation": escalation})}
    )


async def _announce(
    case_id: str,
    state: CheckState,
    deps: CheckDeps,
    moderation: ModerationDeps,
    now: datetime,
) -> None:
    for inbox in await case_recipients(moderation):
        await save_notification(
            deps.notifications,
            key=f"{case_id}:{inbox}:{state.check_id}",
            kind="case_assigned",
            link=PANEL_LINK,
            now=now,
            user_id=inbox,
            case_id=case_id,
        )
