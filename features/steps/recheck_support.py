"""Shared world of the recheck steps: one unanswered claim and a new snapshot."""

import asyncio
from datetime import UTC, datetime, timedelta

from meritum_core.checks.contracts import CheckRecord
from meritum_core.corpus import Passage

from meritum_worker import corpus

SCHEDULED = datetime(2026, 1, 8, 10, 0, tzinfo=UTC)
ASKED_AT = SCHEDULED - timedelta(days=3)
OLD_CHECK = "check-unanswered-1"
CLAIM = "PAP usunęła depeszę o wypowiedzi posła przed wyborami 15 października 2023"
SOURCE = "gov.pl/komunikat-pap"
NEW_TEXT = "PAP nie usunęła depeszy o wypowiedzi posła."


def old_record(session: str) -> CheckRecord:
    """The record of the check that left CLAIM unanswered three days ago."""
    return CheckRecord(
        check_id=OLD_CHECK,
        session_id=session,
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


def new_passage() -> Passage:
    """The passage the claim's search finds in the new snapshot."""
    return Passage(
        passage_id="p-new",
        source_id=SOURCE,
        text=NEW_TEXT,
        published_on=None,
        fetched_at=SCHEDULED - timedelta(minutes=30),
    )


def store_with_new_document() -> corpus.CorpusWriterPort:
    """An in-memory corpus whose SCHEDULED snapshot adds one official document."""
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
        full_text=NEW_TEXT,
    )
    asyncio.run(store.save_document(document, []))
    asyncio.run(corpus.take_snapshot(store, scheduled=SCHEDULED))
    return store
