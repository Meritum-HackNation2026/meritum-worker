"""Steps of features/moderation.feature on in-memory cases, embeddings and results."""

import asyncio
from datetime import UTC, datetime, timedelta

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import Escalation
from meritum_core.checks.contracts import Channel, CheckRecord, ModeratorCase
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import EscalateClaimInput
from meritum_core.moderation import HighRiskTopic
from meritum_core.moderation.fakes import (
    InMemoryHighRiskTopicRepository,
    InMemoryModeratorCaseRepository,
    InMemoryStaffRepository,
)
from meritum_core.shared.embeddings import Vector

from meritum_worker.moderation import (
    InMemoryCheckResults,
    ModerationDeps,
    Referral,
    ScriptedEmbeddings,
    refer,
    run_escalate_claim,
)

NOW = datetime.now(UTC)
DIESEL = "Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?"
PARAPHRASE = "Czy Pcim wprowadza zakaz wjazdu diesli do centrum?"
STUB_CLAIM = "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"
VECTORS: dict[str, Vector] = {
    DIESEL: (1.0, 0.1),
    PARAPHRASE: (1.0, 0.2),
    "inflacja wynosi 5%": (1.0, 0.0),
    "inflacja wynosi 15%": (1.0, 0.01),
    "Czy szczepionki są bezpieczne?": (1.0, 0.0),
    "zdrowie: szczepion": (1.0, 0.1),
}


def moderation_deps(context: Context) -> ModerationDeps:
    if not hasattr(context, "moderation"):
        context.results = InMemoryCheckResults()
        context.moderation = ModerationDeps(
            cases=InMemoryModeratorCaseRepository(),
            topics=InMemoryHighRiskTopicRepository(),
            staff=InMemoryStaffRepository(),
            records=InMemoryCheckRecordRepository(),
            embeddings=ScriptedEmbeddings(VECTORS),
            results=context.results,
        )
    deps = context.moderation
    assert isinstance(deps, ModerationDeps)
    return deps


def _record(context: Context, check_id: str, channel: Channel = "web") -> None:
    asyncio.run(
        moderation_deps(context).records.save(
            CheckRecord(
                check_id=check_id,
                session_id=f"session_{check_id}",
                channel=channel,
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


def earlier(context: Context, claim: str, check_id: str, channel: Channel) -> None:
    moderation_deps(context)
    context.results.add(check_id, NOW - timedelta(hours=2), [(claim, True)])
    _record(context, check_id, channel)


def _come(context: Context, claim: str, check_id: str, trigger: str) -> None:
    _record(context, check_id)
    referral = Referral(claim, check_id, f"session_{check_id}", trigger, NOW)  # ty: ignore[invalid-argument-type]
    context.escalation = asyncio.run(refer(referral, moderation_deps(context)))
    context.check_id = check_id


def _case(context: Context) -> ModeratorCase:
    escalation = context.escalation
    assert isinstance(escalation, Escalation)
    assert escalation.case_id is not None
    case = asyncio.run(moderation_deps(context).cases.get(escalation.case_id))
    assert case is not None
    return case


@given("twierdzenie bez odpowiedzi zadane przez formularz WWW")
def asked_on_the_web(context: Context) -> None:
    earlier(context, DIESEL, "web_1", "web")


@when("podobne twierdzenie bez odpowiedzi przychodzi z Discorda")
def asked_on_discord(context: Context) -> None:
    _come(context, PARAPHRASE, "discord_1", "unanswered")


@then('powstaje jedna sprawa z powodem "{reason}" i oboma sprawdzeniami')
def one_case_with_both(context: Context, reason: str) -> None:
    case = _case(context)
    assert reason in case.reasons
    assert set(case.check_ids) == {"web_1", "discord_1"}
    assert len(asyncio.run(moderation_deps(context).cases.list_cases())) == 1


@then('Escalation ma state "{state}" i numer sprawy')
def escalation_with_case(context: Context, state: str) -> None:
    assert context.escalation.state == state
    assert context.escalation.case_id is not None


@given('lista tematów administratora zawiera "{topic}"')
def admin_topic(context: Context, topic: str) -> None:
    topic_list = moderation_deps(context).topics
    asyncio.run(
        topic_list.save_topic(HighRiskTopic(name=topic, keywords=["szczepion"]))
    )


@when("twierdzenie bez odpowiedzi dotyczy szczepionek")
def about_vaccines(context: Context) -> None:
    _come(context, "Czy szczepionki są bezpieczne?", "vax_1", "unanswered")


@then(
    'powstaje sprawa z powodem "{reason}", high_risk_topic "{topic}" i'
    ' high_risk_classified_by "{by}"'
)
def high_risk_case(context: Context, reason: str, topic: str, by: str) -> None:
    case = _case(context)
    assert reason in case.reasons
    assert (case.high_risk_topic, case.high_risk_classified_by) == (topic, by)


@given('pytanie bez odpowiedzi "{claim}"')
def unanswered_question(context: Context, claim: str) -> None:
    earlier(context, claim, "first_1", "web")


@given("użytkownik przekazał to pytanie moderatorom")
def clicked(context: Context) -> None:
    moderation_deps(context)
    payload = EscalateClaimInput(
        check_id="first_1", claim_index=0, reason="recommended_clicked"
    ).model_dump(mode="json")
    output = asyncio.run(run_escalate_claim(payload, context.moderation))
    assert output.escalation.state == "created"


@when('przychodzi parafraza "{claim}"')
def paraphrase(context: Context, claim: str) -> None:
    _come(context, claim, "second_1", "unanswered")


@then(
    "oba zgłoszenia są w jednej sprawie, a Escalation ma numer sprawy dopiero po"
    " potwierdzonym zapisie"
)
def both_in_one_case(context: Context) -> None:
    case = _case(context)  # the number is read back from the saved case
    assert {"first_1", "second_1"} <= set(case.check_ids)
    assert len(asyncio.run(moderation_deps(context).cases.list_cases())) == 1


@given('otwarta sprawa o "{claim}"')
def open_case(context: Context, claim: str) -> None:
    earlier(context, claim, "open_1", "web")
    payload = EscalateClaimInput(
        check_id="open_1", claim_index=0, reason="recommended_clicked"
    ).model_dump(mode="json")
    context.open_case = asyncio.run(
        run_escalate_claim(payload, moderation_deps(context))
    )


@when('przychodzi twierdzenie bez odpowiedzi "{claim}"')
def other_claim(context: Context, claim: str) -> None:
    _come(context, claim, "other_1", "unanswered")


@then("nie dołącza do tej sprawy")
def not_joined(context: Context) -> None:
    assert context.escalation.case_id != context.open_case.escalation.case_id
    assert context.escalation.state == "recommended"
