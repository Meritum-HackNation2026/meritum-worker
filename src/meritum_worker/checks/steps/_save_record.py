"""Save the CheckRecord of the finished check.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from datetime import UTC, datetime

from meritum_core.checks.contracts import CheckRecord

from meritum_worker.checks.constants import RECORD_RETENTION
from meritum_worker.checks.models import CheckDeps, CheckState


async def save_record(state: CheckState, deps: CheckDeps) -> CheckState:
    """Build the audit record from the state and save it; a retry replaces it.

    Args:
        state: the check after write_answer.
        deps: the ports; only the record repository is called.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    await deps.records.save(build_record(state, answered_at=datetime.now(UTC)))
    return state


def build_record(state: CheckState, *, answered_at: datetime) -> CheckRecord:
    """Build the CheckRecord of a check; kept for 30 days from receipt.

    Args:
        state: the check after write_answer.
        answered_at: when the answer was sent.

    Returns:
        The record.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    job = state.job
    result = state.final_result()
    cited = {c.source.id for claim in result.claims for c in claim.citations}
    return CheckRecord(
        check_id=state.check_id,
        # CheckInput guarantees a session id or a user id.
        session_id=job.session_id or job.user_id or "",
        user_id=job.user_id,
        channel=job.request.channel,
        channel_user_hash=job.channel_user_hash,
        received_at=job.received_at,
        answered_at=answered_at,
        question_masked=state.question,
        status=result.status,
        verdicts=[claim.verdict for claim in result.claims],
        source_ids=sorted(cited),
        corpus_version=result.corpus_version,
        models=state.models,
        escalation=result.escalation,
        retention_until=job.received_at + RECORD_RETENTION,
    )
