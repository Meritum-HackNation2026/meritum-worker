"""Steps of features/notifications.feature: a recheck after a new corpus snapshot.

The corpus is the in-memory writer, records and the inbox are in memory, and the
recheck runs the whole `check` workflow inline on recorded model answers and a
recorded Fact Check Tools API reply; no network, no database.
"""

import asyncio
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import httpx2
from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CheckRecord
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus import Passage
from meritum_core.corpus.catalog import load_catalog
from meritum_core.moderation.fakes import (
    InMemoryHighRiskTopicRepository,
    InMemoryModeratorCaseRepository,
    InMemoryStaffRepository,
)
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.security.pii import NullPiiGate
from pydantic import SecretStr

from meritum_worker import corpus
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
)
from meritum_worker.notifications import (
    RecheckDeps,
    announce_recheck,
    plan_rechecks,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
SCHEDULED = datetime(2026, 1, 8, 10, 0, tzinfo=UTC)
ASKED_AT = SCHEDULED - timedelta(days=3)
OLD_CHECK = "check-unanswered-1"
SESSION = "session-recheck-1"
CLAIM = "PAP usunęła depeszę o wypowiedzi posła przed wyborami 15 października 2023"
SOURCE = "gov.pl/komunikat-pap"
FACT = ExtractedClaim(
    claim=CLAIM,
    kind="fact",
    explanation="Twierdzenie o zdarzeniu, które da się sprawdzić.",
    claim_date=date(2023, 10, 15),
    claim_date_source="text",
)
FIXTURE_OF = {"fałszywe": "fact_check_demagog.json"}
"""The recorded API reply giving each verdict; any other finds no rating."""


@given('twierdzenie z werdyktem "brak wystarczających dowodów" sprzed 3 dni')
def unanswered_claim(context: Context) -> None:
    context.records = InMemoryCheckRecordRepository()
    context.results = InMemoryCheckResults()
    context.results.add(OLD_CHECK, ASKED_AT, [(CLAIM, True)])
    asyncio.run(
        context.records.save(
            CheckRecord(
                check_id=OLD_CHECK,
                session_id=SESSION,
                channel="web",
                received_at=ASKED_AT,
                answered_at=ASKED_AT,
                question_masked=CLAIM,
                status="done",
                verdicts=["insufficient_evidence"],
                source_ids=[],
                models=[],
                corpus_version="2026-01-05T10:00Z",
                retention_until=ASKED_AT + timedelta(days=30),
            )
        )
    )
    context.inbox = InMemoryNotificationRepository()
    context.verdict = "fałszywe"


@given('ponowne sprawdzenie znowu daje "brak wystarczających dowodów"')
def same_verdict(context: Context) -> None:
    context.verdict = "brak wystarczających dowodów"


def _store_with_new_document() -> corpus.CorpusWriterPort:
    store = corpus.build_corpus_writer()
    previous = SCHEDULED - timedelta(hours=1)
    asyncio.run(corpus.take_snapshot(store, scheduled=previous))
    document = corpus.Document(
        source_id=SOURCE,
        url="https://www.gov.pl/web/komunikat-pap",
        domain="gov.pl",
        publisher_id="kprm",
        license="public",
        fetched_at=SCHEDULED - timedelta(minutes=30),
        checksum="0" * 64,
        full_text="PAP nie usunęła depeszy o wypowiedzi posła.",
    )
    asyncio.run(store.save_document(document, []))
    asyncio.run(corpus.take_snapshot(store, scheduled=SCHEDULED))
    return store


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
    passage = Passage(
        passage_id="p-new",
        source_id=SOURCE,
        text="PAP nie usunęła depeszy o wypowiedzi posła.",
        published_on=None,
        fetched_at=SCHEDULED - timedelta(minutes=30),
    )
    deps = RecheckDeps(
        results=context.results,
        records=context.records,
        corpus=FakeCorpusSearch([passage]),
        snapshots=_store_with_new_document(),
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
    check_deps = _check_deps(context, moderation)
    context.plans = asyncio.run(plan_rechecks(SCHEDULED, deps, SCHEDULED))
    for plan in context.plans:
        payload = plan.job.model_dump(mode="json")
        output = asyncio.run(
            run_check(payload, plan.check_id, check_deps, InlineCheckRuntime())
        )
        asyncio.run(announce_recheck(plan, output.result, deps, SCHEDULED))


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
