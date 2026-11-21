"""Save an inbox notification for one session or one signed-in account.

Features:
    US-POW-01, US-POW-04, F-26
"""

from datetime import datetime
from uuid import NAMESPACE_URL, uuid5

from meritum_core.checks.contracts import Notification, NotificationKind
from meritum_core.notifications import NotificationRepository

from meritum_worker.checks.constants import NOTIFICATION_RETENTION, USER_ID_PATTERN


async def save_notification(  # ruff: ignore[too-many-arguments] - one keyword per Notification field
    inbox: NotificationRepository,
    *,
    key: str,
    kind: NotificationKind,
    link: str,
    now: datetime,
    user_id: str | None = None,
    session_id: str | None = None,
    check_id: str | None = None,
    case_id: str | None = None,
) -> Notification:
    """Save a notification the backend lists and pushes over SSE.

    The id comes from ``key``, so a retried workflow step replaces the entry
    instead of adding a second one. It is kept NOTIFICATION_RETENTION.

    Args:
        inbox: the notification repository.
        key: what makes the event unique, e.g. the check id and kind.
        kind: what the notification is about.
        link: the in-app path to open.
        now: when the event happened.
        user_id: the signed-in recipient, ``{provider}:{subject}``.
        session_id: the browser session, when nobody is signed in.
        check_id: the check it is about.
        case_id: the moderator case it is about.

    Returns:
        The saved notification.

    Raises:
        ValueError: user_id is not ``{provider}:{subject}``.

    Features:
        US-POW-01, US-POW-04, F-26
    """
    if user_id is not None and not USER_ID_PATTERN.match(user_id):
        msg = f"user_id {user_id!r} is not {{provider}}:{{subject}}"
        raise ValueError(msg)
    notification = Notification(
        id=uuid5(NAMESPACE_URL, key).hex,
        kind=kind,
        link=link,
        created_at=now,
        retention_until=now + NOTIFICATION_RETENTION,
        user_id=user_id,
        session_id=session_id,
        check_id=check_id,
        case_id=case_id,
    )
    await inbox.save(notification)
    return notification
