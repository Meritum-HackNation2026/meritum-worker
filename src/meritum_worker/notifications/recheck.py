"""Unanswered claims checked again after a new corpus snapshot (ADR-29).

A claim left at ``insufficient_evidence`` is checked again when the new snapshot
holds a document the claim's search finds and the earlier check could not have
seen. The recheck is a new check with its own CheckRecord; the asker hears of it
only when the verdict changed. Records past their retention are not rechecked.

Features:
    US-POW-03, F-39, ADR-29
"""

from collections.abc import Collection
from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from meritum_core.checks import CheckRecordRepository, CheckRequest, CheckResult
from meritum_core.checks.contracts import CheckRecord
from meritum_core.jobs.contracts import CheckInput

from meritum_worker.checks import CHECK_LINK, save_notification
from meritum_worker.corpus import SNAPSHOT_VERSION_FORMAT, CorpusSnapshot
from meritum_worker.moderation import UNANSWERED_VERDICT, PastClaim
from meritum_worker.notifications.constants import (
    NEW_EVIDENCE_KEY,
    RECHECK_KEY,
    RECHECK_LIMIT,
    RECHECK_SEARCH_LIMIT,
    RECHECK_WINDOW,
    SNAPSHOT_INTERVAL,
)
from meritum_worker.notifications.models import Recheck, RecheckDeps

type _Fresh = dict[str, datetime]
"""Documents new in a snapshot: source id to its fetch time."""


async def plan_rechecks(
    scheduled: datetime, deps: RecheckDeps, now: datetime
) -> list[Recheck]:
    """Pick the unanswered claims the snapshot taken at ``scheduled`` may answer.

    A document is new when the previous hourly snapshot did not hold it with the
    same text. A claim qualifies when its record is still kept, a new document
    was fetched after the question arrived, and the claim's search of the new
    snapshot finds one of those documents.

    Args:
        scheduled: when the snapshot workflow fired; names the snapshot.
        deps: the ports.
        now: the time of the run; the new checks arrive then.

    Returns:
        At most RECHECK_LIMIT rechecks, latest question first; none when the
        snapshot is missing.

    Features:
        US-POW-03, F-39, ADR-29
    """
    version = scheduled.strftime(SNAPSHOT_VERSION_FORMAT)
    current = await deps.snapshots.snapshot(version)
    if current is None:
        return []
    earlier = (scheduled - SNAPSHOT_INTERVAL).strftime(SNAPSHOT_VERSION_FORMAT)
    fresh = _fresh(current, await deps.snapshots.snapshot(earlier))
    plans: list[Recheck] = []
    for past in await deps.results.unanswered_since(now - RECHECK_WINDOW):
        if len(plans) == RECHECK_LIMIT:
            break
        record = await deps.records.get(past.check_id)
        if record is None or record.retention_until <= now:
            continue
        unseen = {s for s, at in fresh.items() if at > record.received_at}
        if unseen and await _finds(past, record, unseen, version, deps):
            plans.append(_recheck(past, version))
    return plans


async def recheck_input(
    recheck: Recheck, records: CheckRecordRepository, now: datetime
) -> CheckInput | None:
    """Build the new check's input: the claim, from the earlier asker.

    The asker comes from the earlier record at the time of the recheck, so a
    person erased after the plan is not checked again.

    Args:
        recheck: the planned recheck.
        records: the check records.
        now: when the new check arrives.

    Returns:
        The input, or None when the earlier record is gone.

    Features:
        US-POW-03, US-BEZ-05, F-20, F-39
    """
    record = await records.get(recheck.old_check_id)
    if record is None:
        return None
    # The same asker as before: a channel without sessions keeps its user hash.
    return CheckInput(
        request=CheckRequest(channel=record.channel, text=recheck.claim),
        session_id=record.session_id,
        user_id=record.user_id,
        channel_user_hash=record.channel_user_hash,
        received_at=now,
    )


async def announce_recheck(
    recheck: Recheck, result: CheckResult, deps: RecheckDeps, now: datetime
) -> bool:
    """Save ``new_evidence`` for the earlier asker when the recheck answered.

    The entry carries the earlier check's id and link only, never the claim.

    Args:
        recheck: the planned recheck.
        result: the new check's result.
        deps: the ports; the records and the inbox are called.
        now: the time of the event.

    Returns:
        Whether a notification was saved.

    Features:
        US-POW-03, F-39
    """
    answered = result.status == "done" and any(
        c.verdict != UNANSWERED_VERDICT for c in result.claims
    )
    record = await deps.records.get(recheck.old_check_id)
    if not answered or record is None:
        return False
    old = recheck.old_check_id
    await save_notification(
        deps.inbox,
        key=NEW_EVIDENCE_KEY.format(old_check_id=old, check_id=recheck.check_id),
        kind="new_evidence",
        link=CHECK_LINK.format(check_id=old),
        now=now,
        check_id=old,
        # Exactly one recipient: the account when signed in, else the session.
        user_id=record.user_id,
        session_id=record.session_id if record.user_id is None else None,
    )
    return True


def _fresh(current: CorpusSnapshot, previous: CorpusSnapshot | None) -> _Fresh:
    before = (
        {(e.source_id, e.checksum) for e in previous.manifest} if previous else set()
    )
    return {
        e.source_id: e.fetched_at
        for e in current.manifest
        if (e.source_id, e.checksum) not in before
    }


async def _finds(
    past: PastClaim,
    record: CheckRecord,
    unseen: Collection[str],
    version: str,
    deps: RecheckDeps,
) -> bool:
    found = await deps.corpus.search(
        past.claim,
        claim_date=record.received_at.date(),
        corpus_version=version,
        limit=RECHECK_SEARCH_LIMIT,
    )
    return any(p.source_id in unseen for p in found)


def _recheck(past: PastClaim, version: str) -> Recheck:
    key = RECHECK_KEY.format(
        old_check_id=past.check_id, claim=past.claim, corpus_version=version
    )
    return Recheck(
        old_check_id=past.check_id,
        check_id=uuid5(NAMESPACE_URL, key).hex,
        corpus_version=version,
        claim=past.claim,
    )
