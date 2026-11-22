"""Steps of the moderation scenarios that run the whole `check` workflow."""

import asyncio
from dataclasses import replace

from behave import given, then, when
from behave.runner import Context
from check_support import deps as check_deps
from meritum_core.checks import CheckRequest
from meritum_core.moderation import StaffAccount
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from moderation_steps import NOW, STUB_CLAIM, earlier, moderation_deps

from meritum_worker.checks import InlineCheckRuntime, run_check
from meritum_worker.moderation import case_recipients


@given("moderator z kontem w panelu")
def moderator(context: Context) -> None:
    asyncio.run(
        moderation_deps(context).staff.save_account(
            StaffAccount(email="mod@example.org", role="moderator")
        )
    )


@given("to samo pytanie bez odpowiedzi zadała już inna sesja")
def asked_before(context: Context) -> None:
    earlier(context, STUB_CLAIM, "earlier_1", "web")


def _run_pipeline(context: Context) -> None:
    moderation = moderation_deps(context)
    inbox = InMemoryNotificationRepository()
    base = check_deps("llm_stub_answer.json")
    context.deps = replace(
        base, moderation=moderation, notifications=inbox, records=moderation.records
    )
    job: dict[str, object] = {
        "request": CheckRequest(channel="web", text=STUB_CLAIM).model_dump(mode="json"),
        "session_id": "session-behave-moderation",
        "received_at": NOW.isoformat(),
    }
    output = asyncio.run(
        run_check(job, "check-moderation-1", context.deps, InlineCheckRuntime())
    )
    context.escalation = output.result.escalation


@when("sprawdzenie kończy się brakiem dowodów w zwykłym temacie")
def check_without_evidence(context: Context) -> None:
    if not hasattr(context, "moderation"):
        moderation_deps(context)
    _run_pipeline(context)


@then('Escalation ma state "recommended" bez numeru sprawy')
def recommended(context: Context) -> None:
    assert (context.escalation.state, context.escalation.case_id) == (
        "recommended",
        None,
    )


def _inbox(context: Context) -> list[str]:
    return asyncio.run(case_recipients(moderation_deps(context)))


@then("moderatorzy nie dostają powiadomienia")
def nobody_notified(context: Context) -> None:
    kinds = asyncio.run(
        context.deps.notifications.list_for("user_id", _inbox(context)[0])
    )
    assert kinds == []


@then('moderator dostaje powiadomienie "{kind}" z linkiem "{link}"')
def moderator_notified(context: Context, kind: str, link: str) -> None:
    (owner,) = _inbox(context)
    found = asyncio.run(context.deps.notifications.list_for("user_id", owner))
    assert [(n.kind, n.link, n.case_id) for n in found] == [
        (kind, link, context.escalation.case_id)
    ]
