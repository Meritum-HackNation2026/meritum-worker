"""Steps of features/notifications.feature: a recheck after a new corpus snapshot.

The corpus is the in-memory writer, records and the inbox are in memory, and the
recheck runs the whole `check` workflow inline on recorded model answers and a
recorded Fact Check Tools API reply; no network, no database.
"""

import asyncio
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx2
from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus.catalog import load_catalog
from meritum_core.jobs.contracts import EscalateClaimInput
from meritum_core.moderation.fakes import (
    InMemoryHighRiskTopicRepository,
    InMemoryModeratorCaseRepository,
    InMemoryStaffRepository,
)
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.security.pii import NullPiiGate
from pydantic import SecretStr
from recheck_support import (
    ASKED_AT,
    CLAIM,
    OLD_CHECK,
    SCHEDULED,
    new_passage,
    old_record,
    store_with_new_document,
)

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    ClaimExtraction,
    ExtractedClaim,
    FakeCorpusSearch,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    corpus_ports,
    run_check,
    web_ports,
)
from meritum_worker.checks.factory import build_fact_check
from meritum_worker.corpus import FactCheckProvider, FactCheckSettings
from meritum_worker.evidence import ClaimExplanation, RecordedLlm, ReviewMatch
from meritum_worker.moderation import (
    InMemoryCheckResults,
    ModerationDeps,
    ScriptedEmbeddings,
    run_escalate_claim,
)
from meritum_worker.notifications import (
    RecheckDeps,
    announce_recheck,
    plan_rechecks,
    recheck_input,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SESSION = "session-recheck-1"
FACT = ExtractedClaim(
    claim=CLAIM,
    kind="fact",
    explanation="Twierdzenie o zdarzeniu, które da się sprawdzić.",
    claim_date=date(2023, 10, 15),
    claim_date_source="text",
)
UNANSWERED = "insufficient_evidence"
FIXTURE_OF = {"fałszywe": "fact_check_demagog.json"}
"""The recorded API reply giving each verdict; any other finds no rating."""


@given('twierdzenie z werdyktem "brak wystarczających dowodów" sprzed 3 dni')
def unanswered_claim(context: Context) -> None:
    context.records = InMemoryCheckRecordRepository()
    context.results = InMemoryCheckResults()
    context.results.add(OLD_CHECK, ASKED_AT, [(CLAIM, True)])
    asyncio.run(context.records.save(old_record(SESSION)))
    context.inbox = InMemoryNotificationRepository()
    context.verdict = "fałszywe"


@given('ponowne sprawdzenie znowu daje "brak wystarczających dowodów"')
def same_verdict(context: Context) -> None:
    context.verdict = "brak wystarczających dowodów"


def _check_deps(context: Context, moderation: ModerationDeps) -> CheckDeps:
    body = (
        FIXTURES / FIXTURE_OF.get(context.verdict, "fact_check_empty.json")
    ).read_bytes()
    reply = httpx2.Response(
        200, content=body, headers={"Cache-Control": "max-age=3600"}
    )
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(lambda _: reply))
    settings = FactCheckSettings(
        provider=FactCheckProvider.GOOGLE, api_key=SecretStr("k-recorded")
    )
    explained = ClaimExplanation(
        explanation="Ocena fact-checkera prowadzi do tego werdyktu.",
        unresolved="Brak innych źródeł rozstrzygających twierdzenie.",
    )
    llm = RecordedLlm(
        {},
        ClaimExtraction(out_of_scope=False, claims=[FACT]),
        ReviewMatch(same_claim=True),
        AnswerDraft(claims=[explained], limitations=["Sprawdzono indeks ocen."]),
    )
    deps = CheckDeps(
        llm=llm,
        records=context.records,
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **corpus_ports(),
        **web_ports(),
    )
    return replace(
        deps,
        catalog=load_catalog(),
        fact_check=build_fact_check(settings, client),
        notifications=context.inbox,
        moderation=moderation,
    )


def _recheck(context: Context) -> None:
    deps = RecheckDeps(
        results=context.results,
        records=context.records,
        corpus=FakeCorpusSearch([new_passage()]),
        snapshots=store_with_new_document(),
        inbox=context.inbox,
    )
    moderation = ModerationDeps(
        cases=InMemoryModeratorCaseRepository(),
        topics=InMemoryHighRiskTopicRepository(),
        staff=InMemoryStaffRepository(),
        records=context.records,
        embeddings=ScriptedEmbeddings({}),
        results=context.results,
    )
    context.moderation = moderation
    check_deps = _check_deps(context, moderation)
    context.plans = asyncio.run(plan_rechecks(SCHEDULED, deps, SCHEDULED))
    for plan in context.plans:
        job = asyncio.run(recheck_input(plan, context.records, SCHEDULED))
        assert job is not None
        payload = job.model_dump(mode="json")
        output = asyncio.run(
            run_check(payload, plan.check_id, check_deps, InlineCheckRuntime())
        )
        asyncio.run(announce_recheck(plan, output.result, deps, SCHEDULED))
        context.outputs = [*getattr(context, "outputs", []), output]


@when(
    "nowa migawka zawiera podobny dokument urzędowy"
    ' i ponowne sprawdzenie daje "{verdict}"'
)
def recheck_with_verdict(context: Context, verdict: str) -> None:
    context.verdict = verdict
    _recheck(context)


@when("workflow kończy się")
def recheck_ends(context: Context) -> None:
    _recheck(context)


@then("sesja dostaje powiadomienie new_evidence, a nowy wynik ma własny CheckRecord")
def session_notified(context: Context) -> None:
    [plan] = context.plans
    found = asyncio.run(context.inbox.list_for("session_id", SESSION))
    assert [(n.kind, n.check_id) for n in found] == [("new_evidence", OLD_CHECK)]
    record = asyncio.run(context.records.get(plan.check_id))
    assert record is not None
    assert record.check_id != OLD_CHECK
    assert record.verdicts == ["false"]


@then("żadne powiadomienie nie jest wysyłane")
def nobody_notified(context: Context) -> None:
    assert len(context.plans) == 1
    assert asyncio.run(context.inbox.list_for("session_id", SESSION)) == []


@given('wynik ponownego sprawdzenia z werdyktem "brak wystarczających dowodów"')
def unanswered_recheck(context: Context) -> None:
    unanswered_claim(context)
    same_verdict(context)
    _recheck(context)
    # DBOS keeps the recheck's output like any check's; the results read it there.
    for output in context.outputs:
        result = output.result
        claims = [(c.claim, c.verdict == UNANSWERED) for c in result.claims]
        context.results.add(result.check_id, SCHEDULED, claims)


@when("użytkownik przekazuje to twierdzenie moderatorom")
def refer_recheck(context: Context) -> None:
    [plan] = context.plans
    payload = EscalateClaimInput(
        check_id=plan.check_id, claim_index=0, reason="recommended_clicked"
    ).model_dump(mode="json")
    context.escalation = asyncio.run(run_escalate_claim(payload, context.moderation))


@then("powstaje sprawa z tym twierdzeniem")
def case_with_claim(context: Context) -> None:
    [plan] = context.plans
    escalation = context.escalation.escalation
    assert escalation.state == "created"
    assert escalation.case_id is not None
    case = asyncio.run(context.moderation.cases.get(escalation.case_id))
    assert case is not None
    assert [(c.claim, c.check_ids) for c in case.claims] == [(CLAIM, [plan.check_id])]
