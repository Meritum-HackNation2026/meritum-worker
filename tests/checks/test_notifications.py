import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from meritum_core.checks.contracts import NotificationKind
from meritum_core.notifications.fakes import InMemoryNotificationRepository

from meritum_worker.checks import save_notification

NOW = datetime(2026, 11, 22, 12, tzinfo=UTC)
KINDS: list[tuple[NotificationKind, dict[str, str]]] = [
    ("check_progress", {"check_id": "check-1"}),
    ("check_done", {"check_id": "check-1"}),
    ("moderator_answer", {"case_id": "#S-12"}),
    ("new_evidence", {"check_id": "check-1"}),
    ("case_assigned", {"case_id": "#S-12"}),
    ("system", {}),
]


@pytest.mark.parametrize(("kind", "about"), KINDS)
def test_every_kind_is_saved_for_an_account_with_30_days_of_retention(
    kind: NotificationKind, about: dict[str, str]
) -> None:
    inbox = InMemoryNotificationRepository()
    asyncio.run(
        save_notification(
            inbox,
            key=f"{kind}-1",
            kind=kind,
            link="/",
            now=NOW,
            user_id="google:1234567890",
            **about,
        )
    )
    [saved] = asyncio.run(inbox.list_for("user_id", "google:1234567890"))
    assert saved.kind == kind
    assert saved.retention_until == NOW + timedelta(days=30)


def test_a_session_gets_the_notification_when_nobody_is_signed_in() -> None:
    inbox = InMemoryNotificationRepository()
    asyncio.run(
        save_notification(
            inbox,
            key="k",
            kind="system",
            link="/",
            now=NOW,
            session_id="session-1",
        )
    )
    assert len(asyncio.run(inbox.list_for("session_id", "session-1"))) == 1


def test_the_same_key_replaces_the_entry_on_a_retried_step() -> None:
    inbox = InMemoryNotificationRepository()
    for _ in range(2):
        asyncio.run(
            save_notification(
                inbox,
                key="k",
                kind="system",
                link="/",
                now=NOW,
                session_id="session-1",
            )
        )
    assert len(asyncio.run(inbox.list_for("session_id", "session-1"))) == 1


@pytest.mark.parametrize(
    "user_id", ["1234567890", "google:", ":1234567890", "google:12 34"]
)
def test_a_user_id_outside_provider_subject_is_refused(user_id: str) -> None:
    with pytest.raises(ValueError, match="provider"):
        asyncio.run(
            save_notification(
                InMemoryNotificationRepository(),
                key="k",
                kind="system",
                link="/",
                now=NOW,
                user_id=user_id,
            )
        )
