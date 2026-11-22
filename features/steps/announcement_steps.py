"""Steps of the scenario where a moderator's answer reaches the asker's inbox."""

import asyncio
from datetime import timedelta

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CaseClaim, CheckRecord, ModeratorCase
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from moderation_steps import NOW, STUB_CLAIM, moderation_deps

from meritum_worker.checks import notify_case_answers

SESSION = "session-asker-1"


@given('sprawa "{case_id}" z jednym sprawdzeniem, na którą moderator odpowiedział')
def answered_case(context: Context, case_id: str) -> None:
    deps = moderation_deps(context)
    context.inbox = InMemoryNotificationRepository()
    asyncio.run(
        deps.records.save(
            CheckRecord(
                check_id="check-asked-1",
                session_id=SESSION,
                channel="web",
                received_at=NOW,
                answered_at=NOW,
                question_masked="pytanie",
                status="done",
                verdicts=[],
                source_ids=[],
                models=[],
                corpus_version="none",
                retention_until=NOW + timedelta(days=30),
            )
        )
    )
    case = ModeratorCase(
        id=case_id,
        state="answered",
        reasons=["user_dispute"],
        summary="Zgłoszony błąd twierdzenia",
        claims=[CaseClaim(claim=STUB_CLAIM, check_ids=["check-asked-1"])],
        first_seen=NOW,
        last_seen=NOW,
    )
    asyncio.run(deps.cases.save(case))


@when("worker rozsyła odpowiedzi moderatorów")
def announce(context: Context) -> None:
    asyncio.run(notify_case_answers(moderation_deps(context), context.inbox, NOW))


@then('pytający dostaje powiadomienie "{kind}" z numerem sprawy "{case_id}"')
def asker_notified(context: Context, kind: str, case_id: str) -> None:
    found = asyncio.run(context.inbox.list_for("session_id", SESSION))
    assert [(n.kind, n.case_id) for n in found] == [(kind, case_id)]


@then("drugie rozesłanie nie dodaje następnego")
def no_duplicate(context: Context) -> None:
    asyncio.run(notify_case_answers(moderation_deps(context), context.inbox, NOW))
    found = asyncio.run(context.inbox.list_for("session_id", SESSION))
    assert len(found) == 1
