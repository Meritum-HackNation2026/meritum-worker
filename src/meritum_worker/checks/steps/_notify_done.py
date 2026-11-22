"""Announce the end of a long voice-message check in the citizen's inbox.

Features:
    US-POW-01, US-SPR-11, F-08
"""

from datetime import UTC, datetime

from meritum_worker.checks.constants import CHECK_LINK, LONG_AUDIO_SECONDS
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.checks.notifications import save_notification


async def notify_done(state: CheckState, deps: CheckDeps) -> CheckState:
    """Save a check_done notification after a recording over LONG_AUDIO_SECONDS.

    The citizen may have left while the batch transcription ran; the backend
    pushes the inbox entry live. The id comes from the check id, so a retried
    step replaces the entry instead of adding a second one. It is kept 30
    days and goes with the record (retention, erasure).

    Args:
        state: the finished check.
        deps: the ports; only the notification inbox is called.

    Returns:
        The same state.

    Features:
        US-POW-01, US-SPR-11, F-08
    """
    if (state.audio_seconds or 0) <= LONG_AUDIO_SECONDS:
        return state
    job = state.job
    await save_notification(
        deps.notifications,
        key=state.check_id,
        kind="check_done",
        link=CHECK_LINK.format(check_id=state.check_id),
        now=datetime.now(UTC),
        check_id=state.check_id,
        # Exactly one recipient: the account when signed in, else the session.
        user_id=job.user_id,
        session_id=job.session_id if job.user_id is None else None,
    )
    return state
