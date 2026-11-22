from dataclasses import replace
from datetime import timedelta

from meritum_core.checks.contracts import CaseClaim, ModeratorCase
from meritum_core.jobs.contracts import ReadinessReport
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from tests.moderation.conftest import NOW, Make, record, sync

from meritum_worker.checks import (
    notify_case_answers,
    notify_new_evidence,
    notify_service_state,
)
from meritum_worker.moderation import InMemoryCheckResults
from meritum_worker.moderation.recipients import staff_inbox_id

DIESEL = "Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?"
PARAPHRASE = "Czy Pcim wprowadza zakaz wjazdu diesli do centrum?"
CLOSE: dict[str, tuple[float, ...]] = {DIESEL: (1.0, 0.1), PARAPHRASE: (1.0, 0.2)}


def case(state: str, last_seen_days_ago: int = 1) -> ModeratorCase:
    return ModeratorCase(
        id="#S-1",
        state=state,  # ty: ignore[invalid-argument-type]
        reasons=["user_dispute"],
        summary="Zgłoszony błąd twierdzenia",
        claims=[CaseClaim(claim=DIESEL, check_ids=["c1", "c2"])],
        first_seen=NOW - timedelta(days=3),
        last_seen=NOW - timedelta(days=last_seen_days_ago),
    )


@sync
async def test_every_asker_of_an_answered_case_gets_moderator_answer(
    make: Make,
) -> None:
    deps, inbox = make(), InMemoryNotificationRepository()
    for check_id in ("c1", "c2"):
        await record(deps, check_id)
    await deps.cases.save(case("answered"))
    assert await notify_case_answers(deps, inbox, NOW) == 2
    [saved] = await inbox.list_for("session_id", "s_c1_000")
    assert (saved.kind, saved.case_id, saved.link) == (
        "moderator_answer",
        "#S-1",
        "/sprawdzenie/c1",
    )
    await notify_case_answers(deps, inbox, NOW)
    assert len(await inbox.list_for("session_id", "s_c1_000")) == 1


@sync
async def test_open_and_long_answered_cases_stay_silent(make: Make) -> None:
    deps, inbox = make(), InMemoryNotificationRepository()
    await record(deps, "c1")
    await deps.cases.save(case("open"))
    assert await notify_case_answers(deps, inbox, NOW) == 0
    await deps.cases.save(case("answered", last_seen_days_ago=31))
    assert await notify_case_answers(deps, inbox, NOW) == 0


@sync
async def test_an_earlier_unanswered_asker_hears_of_new_evidence(make: Make) -> None:
    deps, inbox = make(CLOSE), InMemoryNotificationRepository()
    assert isinstance(deps.results, InMemoryCheckResults)
    deps.results.add("c1", NOW - timedelta(days=1), [(DIESEL, True)])
    await record(deps, "c1")
    await record(deps, "c2")
    sent = await notify_new_evidence([PARAPHRASE], "c2", deps, inbox, NOW)
    assert sent == 1
    [saved] = await inbox.list_for("session_id", "s_c1_000")
    assert (saved.kind, saved.check_id) == ("new_evidence", "c1")
    assert await inbox.list_for("session_id", "s_c2_000") == []


@sync
async def test_the_asker_of_the_same_check_is_not_told(make: Make) -> None:
    deps, inbox = make(CLOSE), InMemoryNotificationRepository()
    assert isinstance(deps.results, InMemoryCheckResults)
    deps.results.add("c1", NOW - timedelta(days=1), [(DIESEL, True)])
    await record(deps, "c1")
    assert await notify_new_evidence([DIESEL], "c1", deps, inbox, NOW) == 0


def report(*, missing: list[str]) -> ReadinessReport:
    return ReadinessReport(
        missing_env=missing, unavailable_providers=[], checked_at=NOW
    )


@sync
async def test_staff_hear_when_the_service_degrades_and_when_it_recovers(
    make: Make,
) -> None:
    deps, inbox = make(), InMemoryNotificationRepository()
    deps = replace(deps, admin_emails=frozenset({"a@meritum.pl"}))
    staff = staff_inbox_id("a@meritum.pl")
    await notify_service_state(report(missing=["X"]), deps, inbox, NOW)
    await notify_service_state(report(missing=["X"]), deps, inbox, NOW)
    codes = [n.message_code for n in await inbox.list_for("user_id", staff)]
    assert codes == ["service_degraded"]
    later = NOW + timedelta(minutes=5)
    await notify_service_state(report(missing=[]), deps, inbox, later)
    codes = [n.message_code for n in await inbox.list_for("user_id", staff)]
    assert codes == ["service_restored", "service_degraded"]
