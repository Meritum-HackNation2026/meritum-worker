"""Inbox notifications no check step creates: answers, new evidence, service health.

A moderator's answer, new evidence for an earlier question and a change in the
service's health. Every entry goes through ``save_notification`` and its key
makes a repeated run replace the entry instead of adding one.

Features:
    US-POW-01, US-POW-04, F-26
"""

from collections.abc import Sequence
from datetime import datetime

from meritum_core.checks.contracts import CheckRecord, SystemMessageCode
from meritum_core.jobs.contracts import ReadinessReport
from meritum_core.notifications import NotificationRepository

from meritum_worker.checks.constants import CHECK_LINK, NOTIFICATION_RETENTION
from meritum_worker.checks.notifications import save_notification
from meritum_worker.moderation import (
    PANEL_LINK,
    SIMILARITY_WINDOW,
    ModerationDeps,
    case_recipients,
    similar_flags,
)


def _recipient(record: CheckRecord | None) -> tuple[str | None, str | None] | None:
    # Exactly one recipient: the account when signed in, else the session.
    if record is None:
        return None
    if record.user_id is not None:
        return record.user_id, None
    return None, record.session_id


async def notify_case_answers(
    deps: ModerationDeps, inbox: NotificationRepository, now: datetime
) -> int:
    """Tell every asker of an answered case that a moderator answered it.

    Only cases touched within NOTIFICATION_RETENTION count, so an entry the
    retention already removed is not brought back by a later run.

    Args:
        deps: the moderation ports.
        inbox: the notification repository.
        now: the time of the run.

    Returns:
        How many notifications were saved.

    Features:
        US-POW-04, F-26
    """
    sent = 0
    for case in await deps.cases.list_cases("answered"):
        if case.last_seen < now - NOTIFICATION_RETENTION:
            continue
        for check_id in dict.fromkeys(c for g in case.claims for c in g.check_ids):
            who = _recipient(await deps.records.get(check_id))
            if who is None:
                continue
            await save_notification(
                inbox,
                key=f"moderator_answer:{case.id}:{check_id}",
                kind="moderator_answer",
                link=CHECK_LINK.format(check_id=check_id),
                now=now,
                check_id=check_id,
                case_id=case.id,
                user_id=who[0],
                session_id=who[1],
            )
            sent += 1
    return sent


async def notify_new_evidence(
    answered: Sequence[str],
    check_id: str,
    deps: ModerationDeps,
    inbox: NotificationRepository,
    now: datetime,
) -> int:
    """Tell earlier askers of a similar unanswered claim that it now has an answer.

    Args:
        answered: the claims of ``check_id`` that got a verdict.
        check_id: the check that answered them.
        deps: the moderation ports.
        inbox: the notification repository.
        now: the time of the event.

    Returns:
        How many notifications were saved.

    Features:
        US-POW-04, F-26
    """
    past = [
        p
        for p in await deps.results.unanswered_since(now - SIMILARITY_WINDOW)
        if p.check_id != check_id
    ]
    earlier: set[str] = set()
    for claim in answered:
        flags = await similar_flags(claim, [p.claim for p in past], deps.embeddings)
        earlier |= {p.check_id for p, same in zip(past, flags, strict=True) if same}
    sent = 0
    for old in sorted(earlier):
        who = _recipient(await deps.records.get(old))
        if who is None:
            continue
        await save_notification(
            inbox,
            key=f"new_evidence:{old}:{check_id}",
            kind="new_evidence",
            link=CHECK_LINK.format(check_id=old),
            now=now,
            check_id=old,
            user_id=who[0],
            session_id=who[1],
        )
        sent += 1
    return sent


async def notify_service_state(
    report: ReadinessReport,
    deps: ModerationDeps,
    inbox: NotificationRepository,
    now: datetime,
) -> int:
    """Tell the staff when the worker degrades or recovers; a repeat says nothing.

    The staff are the case recipients. The newest system entry of each tells
    the last state, so only a change is announced.

    Args:
        report: what the readiness check found.
        deps: the moderation ports.
        inbox: the notification repository.
        now: the time of the run.

    Returns:
        How many notifications were saved.

    Features:
        US-POW-01, F-26
    """
    degraded = bool(report.missing_env or report.unavailable_providers)
    sent = 0
    for staff in await case_recipients(deps):
        last = next(
            (
                n.message_code
                for n in await inbox.list_for("user_id", staff)
                if n.kind == "system"
            ),
            None,
        )
        code: SystemMessageCode | None = (
            None
            if degraded == (last == "service_degraded")
            else "service_degraded"
            if degraded
            else "service_restored"
        )
        if code is None or (last is None and not degraded):
            continue
        await save_notification(
            inbox,
            key=f"system:{code}:{staff}:{now.isoformat()}",
            kind="system",
            link=PANEL_LINK,
            now=now,
            user_id=staff,
            message_code=code,
        )
        sent += 1
    return sent
