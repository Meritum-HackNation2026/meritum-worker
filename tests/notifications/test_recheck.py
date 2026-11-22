import asyncio
from datetime import UTC, datetime, timedelta

from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import Channel, CheckRecord, ClaimResult
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus import Passage
from meritum_core.notifications.fakes import InMemoryNotificationRepository

from meritum_worker import corpus
from meritum_worker.checks import FakeCorpusSearch
from meritum_worker.moderation import InMemoryCheckResults
from meritum_worker.notifications import (
    Recheck,
    RecheckDeps,
    announce_recheck,
    plan_rechecks,
    recheck_input,
)

SCHEDULED = datetime(2026, 1, 8, 10, 0, tzinfo=UTC)
CLAIM = "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"
HASH = "a" * 64


def _record(
    check_id: str, asked: datetime, channel: Channel = "web", user: str | None = None
) -> CheckRecord:
    sessionless = channel != "web"
    return CheckRecord(
        check_id=check_id,
        session_id=HASH if sessionless else f"session-{check_id}",
        user_id=user,
        channel=channel,
        channel_user_hash=HASH if sessionless else None,
        received_at=asked,
        answered_at=asked,
        question_masked=CLAIM,
        status="done",
        verdicts=["insufficient_evidence"],
        source_ids=[],
        models=[],
        corpus_version="2026-01-05T10:00Z",
        retention_until=asked + timedelta(days=30),
    )


def _passage(source_id: str) -> Passage:
    return Passage(
        passage_id=f"p-{source_id}",
        source_id=source_id,
        text="Minimalne wynagrodzenie wynosi 4666 zł.",
        published_on=None,
        fetched_at=SCHEDULED - timedelta(minutes=30),
    )


def _document(source_id: str, fetched: datetime) -> corpus.Document:
    return corpus.Document(
        source_id=source_id,
        url=f"https://www.gov.pl/{source_id}",
        domain="gov.pl",
        publisher_id="kprm",
        license="public",
        fetched_at=fetched,
        checksum="0" * 64,
        full_text="Minimalne wynagrodzenie wynosi 4666 zł.",
    )


class World:
    def __init__(self) -> None:
        self.records = InMemoryCheckRecordRepository()
        self.results = InMemoryCheckResults()
        self.store = corpus.build_corpus_writer()
        self.inbox = InMemoryNotificationRepository()
        self.found: list[Passage] = []

    def ask(self, record: CheckRecord, *, kept: bool = True) -> None:
        self.results.add(record.check_id, record.received_at, [(CLAIM, True)])
        if kept:
            asyncio.run(self.records.save(record))

    def snapshots(self, *, old: list[str], new: list[str]) -> None:
        fetched = SCHEDULED - timedelta(minutes=30)
        for source_id in old:
            asyncio.run(self.store.save_document(_document(source_id, fetched), []))
        if old or new:
            earlier = SCHEDULED - timedelta(hours=1)
            asyncio.run(corpus.take_snapshot(self.store, scheduled=earlier))
        for source_id in new:
            asyncio.run(self.store.save_document(_document(source_id, fetched), []))
        asyncio.run(corpus.take_snapshot(self.store, scheduled=SCHEDULED))

    def deps(self) -> RecheckDeps:
        return RecheckDeps(
            results=self.results,
            records=self.records,
            corpus=FakeCorpusSearch(self.found),
            snapshots=self.store,
            inbox=self.inbox,
        )

    def plan(self, now: datetime = SCHEDULED) -> list[Recheck]:
        return asyncio.run(plan_rechecks(SCHEDULED, self.deps(), now))


def _world(asked: datetime = SCHEDULED - timedelta(days=3)) -> World:
    world = World()
    world.ask(_record("old-1", asked))
    world.snapshots(old=[], new=["gov-new"])
    world.found = [_passage("gov-new")]
    return world


def test_a_similar_new_document_plans_one_recheck_of_the_claim() -> None:
    [plan] = _world().plan()
    assert plan.old_check_id == "old-1"
    assert plan.corpus_version == "2026-01-08T10:00Z"
    assert plan.check_id != "old-1"
    assert plan.claim == CLAIM


def test_the_plan_does_not_name_the_asker() -> None:
    [plan] = _world().plan()
    assert "session-old-1" not in plan.model_dump_json()


def test_the_recheck_reads_the_asker_from_the_earlier_record() -> None:
    world = _world()
    [plan] = world.plan()
    later = SCHEDULED + timedelta(minutes=5)
    job = asyncio.run(recheck_input(plan, world.records, later))
    assert job is not None
    assert (job.request.text, job.session_id, job.received_at) == (
        CLAIM,
        "session-old-1",
        later,
    )


def test_no_recheck_input_once_the_asker_was_erased() -> None:
    world = _world()
    [plan] = world.plan()
    asyncio.run(world.records.delete_subject("session_id", "session-old-1"))
    assert asyncio.run(recheck_input(plan, world.records, SCHEDULED)) is None


def test_the_same_snapshot_plans_the_same_check_id() -> None:
    world = _world()
    assert world.plan() == world.plan()


def test_no_recheck_when_the_similar_document_was_in_the_previous_snapshot() -> None:
    world = World()
    world.ask(_record("old-1", SCHEDULED - timedelta(days=3)))
    world.snapshots(old=["gov-old"], new=[])
    world.found = [_passage("gov-old")]
    assert world.plan() == []


def test_no_recheck_when_the_search_finds_only_older_documents() -> None:
    world = World()
    world.ask(_record("old-1", SCHEDULED - timedelta(days=3)))
    world.snapshots(old=["gov-old"], new=["gov-new"])
    world.found = [_passage("gov-old")]
    assert world.plan() == []


def test_no_recheck_when_the_record_is_gone() -> None:
    world = World()
    world.ask(_record("old-1", SCHEDULED - timedelta(days=3)), kept=False)
    world.snapshots(old=[], new=["gov-new"])
    world.found = [_passage("gov-new")]
    assert world.plan() == []


def test_no_recheck_after_the_record_retention() -> None:
    world = _world(asked=SCHEDULED - timedelta(days=29))
    assert world.plan(now=SCHEDULED + timedelta(days=2)) == []


def test_no_recheck_without_the_snapshot() -> None:
    world = World()
    world.ask(_record("old-1", SCHEDULED - timedelta(days=3)))
    world.found = [_passage("gov-new")]
    assert world.plan() == []


def test_a_document_fetched_before_the_question_is_not_new_evidence() -> None:
    world = _world(asked=SCHEDULED - timedelta(minutes=10))
    assert world.plan() == []


def test_a_discord_question_is_rechecked_for_the_same_hashed_user() -> None:
    world = World()
    world.ask(_record("old-1", SCHEDULED - timedelta(days=3), channel="discord"))
    world.snapshots(old=[], new=["gov-new"])
    world.found = [_passage("gov-new")]
    [plan] = world.plan()
    job = asyncio.run(recheck_input(plan, world.records, SCHEDULED))
    assert job is not None
    assert (job.session_id, job.channel_user_hash) == (HASH, HASH)


def _result(plan: Recheck, verdict: str) -> CheckResult:
    # Built unvalidated: the contract wants citations behind a "false" verdict,
    # and only the verdicts matter here.
    claim = ClaimResult.model_construct(claim=CLAIM, verdict=verdict)
    return CheckResult.model_construct(
        check_id=plan.check_id, status="done", claims=[claim]
    )


def test_a_changed_verdict_notifies_the_asker_with_ids_only() -> None:
    world = _world()
    [plan] = world.plan()
    sent = asyncio.run(
        announce_recheck(plan, _result(plan, "false"), world.deps(), SCHEDULED)
    )
    assert sent
    [saved] = asyncio.run(world.inbox.list_for("session_id", "session-old-1"))
    assert (saved.kind, saved.check_id, saved.link) == (
        "new_evidence",
        "old-1",
        "/sprawdzenie/old-1",
    )
    assert CLAIM not in saved.model_dump_json()


def test_the_same_verdict_notifies_nobody() -> None:
    world = _world()
    [plan] = world.plan()
    result = _result(plan, "insufficient_evidence")
    assert not asyncio.run(announce_recheck(plan, result, world.deps(), SCHEDULED))
    assert asyncio.run(world.inbox.list_for("session_id", "session-old-1")) == []


def test_a_signed_in_asker_is_notified_on_the_account() -> None:
    world = World()
    record = _record("old-1", SCHEDULED - timedelta(days=3), user="google:1234567890")
    world.ask(record)
    world.snapshots(old=[], new=["gov-new"])
    world.found = [_passage("gov-new")]
    [plan] = world.plan()
    asyncio.run(announce_recheck(plan, _result(plan, "false"), world.deps(), SCHEDULED))
    [saved] = asyncio.run(world.inbox.list_for("user_id", "google:1234567890"))
    assert saved.session_id is None
