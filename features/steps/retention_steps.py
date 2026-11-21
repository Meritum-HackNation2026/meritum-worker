"""Steps of the retention and erasure scenarios in features/security.feature.

They run on the in-memory app repositories, the in-memory workflow store and a
temporary files volume; no DBOS, no database.
"""

import asyncio
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import (
    CaseClaim,
    CheckRecord,
    ModeratorCase,
    Notification,
)
from meritum_core.shared.blobs import BlobSettings
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.security import (
    InMemoryWorkflowStore,
    RetentionDeps,
    build_retention_deps,
    erase_subject,
    run_retention,
)

NOW = datetime.now(UTC)
OLD, NEW = "chk_old", "chk_new"
SESSION, OTHER = "s_12345678", "s_87654321"
FRESH_AUDIO = "audio_" + "b" * 32
OLD_AUDIO = "audio_" + "a" * 32


def _deps(context: Context) -> RetentionDeps:
    directory = Path(tempfile.mkdtemp())
    context.directory = directory
    context.workflows = InMemoryWorkflowStore()
    return build_retention_deps(
        DatabaseSettings(provider="memory"),
        BlobSettings(provider="filesystem", directory=directory),
        workflows=context.workflows,
    )


def _record(check_id: str, session: str, retention_until: datetime) -> CheckRecord:
    return CheckRecord(
        check_id=check_id,
        session_id=session,
        channel="web",
        received_at=retention_until - timedelta(days=30),
        answered_at=retention_until - timedelta(days=30),
        question_masked="Płaca minimalna wynosi 4806 zł",
        status="done",
        verdicts=["confirmed"],
        source_ids=[],
        corpus_version="c1",
        models=[],
        retention_until=retention_until,
    )


def _notification(check_id: str, session: str) -> Notification:
    return Notification(
        id=f"n_{check_id}",
        kind="check_done",
        session_id=session,
        check_id=check_id,
        link=f"/checks/{check_id}",
        created_at=NOW - timedelta(days=31),
        retention_until=NOW + timedelta(days=1),
    )


def _case(check_ids: list[str]) -> ModeratorCase:
    claim = CaseClaim(claim="Płaca minimalna wynosi 4806 zł", check_ids=check_ids)
    return ModeratorCase(
        id="#S-1",
        state="open",
        reasons=["insufficient_evidence"],
        summary="Pytanie o płacę minimalną",
        claims=[claim],
        first_seen=NOW - timedelta(days=31),
        last_seen=NOW,
    )


def _check_input(session: str, audio_id: str | None = None) -> dict[str, object]:
    request: dict[str, object] = {"channel": "web", "text": "Płaca minimalna"}
    if audio_id is not None:
        request["audio_id"] = audio_id
    return {"request": request, "session_id": session, "received_at": NOW.isoformat()}


def _seed(context: Context, records: list[CheckRecord]) -> None:
    app = context.deps.app
    for record in records:
        asyncio.run(app.records.save(record))
        asyncio.run(
            app.notifications.save(_notification(record.check_id, record.session_id))
        )
    asyncio.run(app.cases.save(_case([r.check_id for r in records])))


def _file(context: Context, blob_id: str, age: timedelta) -> Path:
    directory = context.directory
    assert isinstance(directory, Path)
    path = directory / blob_id
    path.write_bytes(b"OggS")
    stamp = (NOW - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


@given("CheckRecord z retention_until we wczorajszej dacie")
def record_expired_yesterday(context: Context) -> None:
    context.deps = _deps(context)
    _seed(
        context,
        [
            _record(OLD, SESSION, NOW - timedelta(days=1)),
            _record(NEW, OTHER, NOW + timedelta(days=29)),
        ],
    )
    created = NOW - timedelta(days=29)
    context.workflows.add(OLD, "check", _check_input(SESSION), created_at=created)
    context.workflows.add(NEW, "check", _check_input(OTHER), created_at=created)
    escalation = {"check_id": OLD, "claim_index": 0, "reason": "recommended_clicked"}
    context.workflows.add("esc_old", "escalate_claim", escalation, created_at=created)


@given(
    "w wolumenie plików nagranie audio_ sprzed 31 dni, którego nie użyło żadne"
    " sprawdzenie"
)
def orphan_audio(context: Context) -> None:
    context.deps = _deps(context)
    context.old_audio = _file(context, OLD_AUDIO, timedelta(days=31))
    context.fresh_audio = _file(context, FRESH_AUDIO, timedelta(days=1))


@given('backend zleca usunięcie dla session_id "{session}"')
def erasure_requested(context: Context, session: str) -> None:
    context.deps = _deps(context)
    context.session = session
    _seed(
        context,
        [
            _record(OLD, session, NOW + timedelta(days=20)),
            _record(NEW, OTHER, NOW + timedelta(days=20)),
        ],
    )
    context.audio = _file(context, OLD_AUDIO, timedelta(hours=1))
    context.other_audio = _file(context, FRESH_AUDIO, timedelta(hours=1))
    store = context.workflows
    store.add(OLD, "check", _check_input(session, OLD_AUDIO), created_at=NOW)
    store.add("chk_running", "check", _check_input(session), created_at=NOW, done=False)
    store.add(NEW, "check", _check_input(OTHER, FRESH_AUDIO), created_at=NOW)
    escalation = {"check_id": OLD, "claim_index": 0, "reason": "recommended_clicked"}
    store.add("esc_old", "escalate_claim", escalation, created_at=NOW)


@when("dzienny workflow retencji działa")
def retention_runs(context: Context) -> None:
    context.report = asyncio.run(run_retention(context.deps, NOW))


@when("workflow usuwania kończy się")
def erasure_finishes(context: Context) -> None:
    payload = {"kind": "session_id", "value": context.session}
    context.output = asyncio.run(erase_subject(payload, context.deps))


@then(
    "zapis, jego powiadomienia, powiązania ze sprawami i dane workflowu w tabelach"
    " DBOS są usunięte"
)
def expired_record_is_gone(context: Context) -> None:
    app = context.deps.app
    assert asyncio.run(app.records.get(OLD)) is None
    assert asyncio.run(app.records.get(NEW)) is not None
    assert asyncio.run(app.notifications.list_for("session_id", SESSION)) == []
    assert len(asyncio.run(app.notifications.list_for("session_id", OTHER))) == 1
    case = asyncio.run(app.cases.get("#S-1"))
    assert case is not None
    assert case.check_ids == [NEW]
    assert context.workflows.ids() == {NEW}


@then("nagranie jest usunięte, a nagranie sprzed dnia zostaje")
def orphan_audio_is_gone(context: Context) -> None:
    assert not context.old_audio.exists()
    assert context.fresh_audio.exists()
    assert context.report.blobs == 1


@then(
    "w bazie nie ma żadnego zapisu, powiadomienia, powiązania ze sprawą ani danych"
    " DBOS z tym session_id"
)
def subject_is_gone(context: Context) -> None:
    app, session = context.deps.app, context.session
    assert asyncio.run(app.records.list_for("session_id", session)) == []
    assert asyncio.run(app.notifications.list_for("session_id", session)) == []
    case = asyncio.run(app.cases.get("#S-1"))
    assert case is not None
    assert case.check_ids == [NEW]
    assert session not in json.dumps(context.workflows.payloads())
    assert context.workflows.ids() == {NEW}
    assert not context.audio.exists()
    assert context.other_audio.exists()
    assert context.output.deleted > 0
