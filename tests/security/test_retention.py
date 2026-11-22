"""Which rows, workflows and files retention and erasure select; in-memory ports."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CheckRecord
from meritum_core.shared.blobs import BlobSettings
from meritum_core.shared.database import DatabaseSettings

from meritum_worker.security import (
    InMemoryWorkflowStore,
    RetentionDeps,
    about_checks,
    audio_id,
    build_retention_deps,
    erase_subject,
    names_subject,
    run_retention,
)

NOW = datetime(2026, 11, 21, 3, 0, tzinfo=UTC)
AUDIO = "audio_" + "a" * 32
HASH = "c" * 64


def _deps(store: InMemoryWorkflowStore, directory: Path | None = None) -> RetentionDeps:
    blobs = (
        None
        if directory is None
        else BlobSettings(provider="filesystem", directory=directory)
    )
    return build_retention_deps(
        DatabaseSettings(provider="memory"), blobs, workflows=store
    )


def _file(directory: Path, name: str, age: timedelta) -> Path:
    path = directory / name
    path.write_bytes(b"OggS")
    stamp = (NOW - age).timestamp()
    os.utime(path, (stamp, stamp))
    return path


def test_names_subject_matches_only_the_given_identifier() -> None:
    payload = {"session_id": "s_12345678", "user_id": "u_1"}
    assert names_subject(payload, "session_id", "s_12345678")
    assert not names_subject(payload, "user_id", "s_12345678")
    assert not names_subject(None, "session_id", "s_12345678")


def test_about_checks_needs_a_string_check_id_among_the_deleted() -> None:
    assert about_checks({"check_id": "chk_1"}, {"chk_1"})
    assert not about_checks({"check_id": "chk_2"}, {"chk_1"})
    assert not about_checks({"check_id": 1}, {"1"})
    assert not about_checks(None, {"chk_1"})


def test_audio_id_reads_the_request_and_ignores_other_shapes() -> None:
    assert audio_id({"request": {"audio_id": AUDIO}}) == AUDIO
    assert audio_id({"request": {"text": "x"}}) is None
    assert audio_id({"request": "x"}) is None
    assert audio_id(None) is None


def test_retention_deletes_every_workflow_older_than_30_days() -> None:
    store = InMemoryWorkflowStore()
    old, fresh = NOW - timedelta(days=31), NOW - timedelta(days=29)
    store.add("ping_old", "ping", None, created_at=old)
    store.add("ping_fresh", "ping", None, created_at=fresh)
    store.add("running_old", "check", None, created_at=old, done=False)
    report = asyncio.run(run_retention(_deps(store), NOW))
    assert store.ids() == {"ping_fresh"}
    assert report.workflows == 2  # the old ping and the stuck old check


def test_retention_drops_erasure_runs_after_an_hour() -> None:
    store = InMemoryWorkflowStore()
    payload = {"kind": "session_id", "value": "s_12345678"}
    store.add("del_old", "delete_subject", payload, created_at=NOW - timedelta(hours=2))
    store.add("del_new", "delete_subject", payload, created_at=NOW)
    old_running = NOW - timedelta(hours=2)
    store.add(
        "del_running", "delete_subject", payload, created_at=old_running, done=False
    )
    asyncio.run(run_retention(_deps(store), NOW))
    assert store.ids() == {"del_new", "del_running"}


def test_retention_sweeps_only_old_blob_files(tmp_path: Path) -> None:
    old = _file(tmp_path, AUDIO, timedelta(days=31))
    partial = _file(tmp_path, "image_" + "b" * 32 + ".part", timedelta(days=31))
    foreign = _file(tmp_path, "notes.txt", timedelta(days=31))
    fresh = _file(tmp_path, "audio_" + "c" * 32, timedelta(days=29))
    report = asyncio.run(run_retention(_deps(InMemoryWorkflowStore(), tmp_path), NOW))
    assert not old.exists()
    assert not partial.exists()
    assert foreign.exists()
    assert fresh.exists()
    assert report.blobs == 2  # the old audio and the old partial file


def test_retention_without_blob_store_or_database_deletes_nothing_else() -> None:
    report = asyncio.run(run_retention(_deps(InMemoryWorkflowStore()), NOW))
    assert report.removed_case_checks == 0
    assert report.model_dump() == {
        "records": 0,
        "notifications": 0,
        "workflows": 0,
        "blobs": 0,
        "removed_case_checks": 0,
        "full_texts": 0,
        "archives": 0,
    }


def test_erasure_skips_malformed_audio_ids(tmp_path: Path) -> None:
    store = InMemoryWorkflowStore()
    request = {"request": {"audio_id": "../etc/passwd"}, "session_id": "s_12345678"}
    store.add("chk_1", "check", request, created_at=NOW)
    payload = {"kind": "session_id", "value": "s_12345678"}
    output = asyncio.run(erase_subject(payload, _deps(store, tmp_path)))
    assert store.ids() == set()
    assert output.deleted == 1


def test_erasure_rejects_another_contract_version() -> None:
    payload = {"kind": "session_id", "value": "s_12345678", "contract_version": 99}
    with pytest.raises(ValueError, match="contract_version"):
        asyncio.run(erase_subject(payload, _deps(InMemoryWorkflowStore())))


def _record(check_id: str, channel_user_hash: str) -> CheckRecord:
    return CheckRecord(
        check_id=check_id,
        session_id=channel_user_hash,
        channel="discord",
        received_at=NOW,
        answered_at=NOW,
        question_masked="Płaca minimalna wynosi 4806 zł",
        status="done",
        verdicts=["confirmed"],
        source_ids=[],
        corpus_version="c1",
        models=[],
        retention_until=NOW + timedelta(days=30),
        channel_user_hash=channel_user_hash,
    )


def test_second_erasure_pass_deletes_a_record_saved_after_the_first() -> None:
    deps = _deps(InMemoryWorkflowStore())
    payload = {"kind": "channel_user_hash", "value": HASH}
    asyncio.run(erase_subject(payload, deps))
    # A cancelled check whose save step was already running lands its record late.
    asyncio.run(deps.app.records.save(_record("chk_late", HASH)))
    asyncio.run(deps.app.records.save(_record("chk_other", "d" * 64)))
    output = asyncio.run(erase_subject(payload, deps))
    assert asyncio.run(deps.app.records.list_for("channel_user_hash", HASH)) == []
    assert asyncio.run(deps.app.records.get("chk_other")) is not None
    assert output.deleted == 1


def test_erasure_by_channel_user_hash_drops_their_checks_and_audio(
    tmp_path: Path,
) -> None:
    store = InMemoryWorkflowStore()
    audio = _file(tmp_path, AUDIO, timedelta(hours=1))
    request = {"request": {"audio_id": AUDIO}, "channel_user_hash": HASH}
    store.add("chk_1", "check", request, created_at=NOW)
    store.add("chk_2", "check", {"channel_user_hash": "d" * 64}, created_at=NOW)
    payload = {"kind": "channel_user_hash", "value": HASH}
    asyncio.run(erase_subject(payload, _deps(store, tmp_path)))
    assert store.ids() == {"chk_2"}
    assert not audio.exists()


def _recheck(check_id: str, old_check_id: str) -> dict[str, object]:
    return {
        "old_check_id": old_check_id,
        "check_id": check_id,
        "corpus_version": "2026-11-21T02:00Z",
        "claim": "Płaca minimalna wynosi 4806 zł",
    }


def _erasure_deps(store: InMemoryWorkflowStore) -> RetentionDeps:
    return build_retention_deps(
        DatabaseSettings(provider="memory"),
        None,
        workflows=store,
        recheck_workflows=("recheck_claim",),
    )


def test_erasure_drops_the_rechecks_of_the_persons_checks() -> None:
    store = InMemoryWorkflowStore()
    store.add("chk_1", "check", {"channel_user_hash": HASH}, created_at=NOW)
    store.add("re_1", "recheck_claim", _recheck("re_1", "chk_1"), created_at=NOW)
    store.add("re_2", "recheck_claim", _recheck("re_2", "chk_9"), created_at=NOW)
    payload = {"kind": "channel_user_hash", "value": HASH}
    asyncio.run(erase_subject(payload, _erasure_deps(store)))
    assert store.ids() == {"re_2"}


def test_erasure_drops_a_recheck_whose_own_record_names_the_person() -> None:
    # The earlier check already left by retention; the recheck saved a record.
    store = InMemoryWorkflowStore()
    store.add("re_1", "recheck_claim", _recheck("re_1", "chk_gone"), created_at=NOW)
    deps = _erasure_deps(store)
    asyncio.run(deps.app.records.save(_record("re_1", HASH)))
    payload = {"kind": "channel_user_hash", "value": HASH}
    asyncio.run(erase_subject(payload, deps))
    assert store.ids() == set()
