"""Tell earlier askers of a similar unanswered claim that this check found an answer.

Features:
    US-POW-04, F-26
"""

from datetime import UTC, datetime

from meritum_worker.checks.announcements import notify_new_evidence as announce
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.moderation import UNANSWERED_VERDICT


async def notify_new_evidence(state: CheckState, deps: CheckDeps) -> CheckState:
    """Save ``new_evidence`` for earlier checks whose similar claim had no answer.

    Args:
        state: the check after write_answer.
        deps: the ports; the moderation ports and the inbox are called.

    Returns:
        The same state.

    Features:
        US-POW-04, F-26
    """
    if deps.moderation is None or state.result is None:
        return state
    answered = [c.claim for c in state.result.claims if c.verdict != UNANSWERED_VERDICT]
    if answered:
        await announce(
            answered,
            state.check_id,
            deps.moderation,
            deps.notifications,
            datetime.now(UTC),
        )
    return state
