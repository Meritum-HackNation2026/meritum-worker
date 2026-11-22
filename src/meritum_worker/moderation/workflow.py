"""The `escalate_claim` workflow body: hand one claim of a finished check over.

Features:
    US-MOD-03, US-MOD-06, F-24, ADR-03, ADR-22
"""

from datetime import UTC, datetime

from meritum_core.jobs.contracts import ESCALATE_CLAIM, EscalateClaimOutput

from meritum_worker.moderation.cases import refer
from meritum_worker.moderation.models import ModerationDeps, Referral


async def run_escalate_claim(
    payload: dict[str, object], deps: ModerationDeps
) -> EscalateClaimOutput:
    """Create or update the case of one claim; also counts a result-cache hit.

    The claim text comes from the finished check. A click and a dispute always
    end in a case; a cache hit only counts the repeat (a case appears for a
    high-risk topic or a second unanswered question). The backend announces the
    case after the output returns.

    Args:
        payload: the `EscalateClaimInput` JSON object.
        deps: the moderation ports.

    Returns:
        The output with the escalation.

    Raises:
        LookupError: the check is unfinished or has no claim at that index; the
            backend checks that first, so this is a stale id.

    Features:
        US-MOD-03, US-MOD-06, F-24, ADR-03, ADR-22
    """
    job = ESCALATE_CLAIM.input.model_validate(payload)
    claim = await deps.results.claim(job.check_id, job.claim_index)
    if claim is None:
        msg = f"check {job.check_id} has no claim {job.claim_index}"
        raise LookupError(msg)
    record = await deps.records.get(job.check_id)
    asker = job.check_id if record is None else record.user_id or record.session_id
    referral = Referral(
        claim=claim,
        check_id=job.check_id,
        asker=asker,
        trigger=job.reason,
        now=datetime.now(UTC),
        justification=job.justification_masked,
    )
    return EscalateClaimOutput(escalation=await refer(referral, deps))
