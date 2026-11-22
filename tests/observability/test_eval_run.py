"""The `eval_run` workflow on the stub model and in-memory ports (US-OBS-06)."""

import asyncio
import json
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import EvalRunInput
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.blobs import (
    BlobKind,
    BlobProvider,
    BlobSettings,
    build_blob_store,
)
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.observability import (
    EvalCaseSets,
    EvalRunDeps,
    GoldenSet,
    load_golden_set,
    run_eval_run,
)
from meritum_worker.observability.adapters import BlobCaseSets
from meritum_worker.observability.fakes import InMemoryCaseSets, InMemoryEvalRuns

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = load_golden_set(ROOT / "evals" / "golden" / "cases.json")
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"
USER = "google:1234567890"
NOW = datetime(2026, 11, 22, 12, tzinfo=UTC)


def _check_deps() -> CheckDeps:
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=STUB_ANSWER)
    return CheckDeps(
        llm=build_llm(settings),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
        **corpus_ports(),
    )


def _deps(
    case_sets: EvalCaseSets | None = None,
) -> tuple[EvalRunDeps, InMemoryEvalRuns, InMemoryNotificationRepository]:
    runs = InMemoryEvalRuns()
    inbox = InMemoryNotificationRepository()
    deps = EvalRunDeps(
        runs=runs,
        case_sets=case_sets or InMemoryCaseSets(golden=GOLDEN),
        deps_for=lambda _case: _check_deps(),
        notifications=inbox,
        max_concurrency=4,
        clock=lambda: NOW,
    )
    return deps, runs, inbox


def _input(**changes: object) -> Mapping[str, object]:
    raw: dict[str, object] = {
        "run_id": "run-1",
        "case_set": "golden",
        "corpus_version": "2026-11-20T10:00Z",
        "user_id": USER,
    }
    return EvalRunInput.model_validate(raw | changes).model_dump(mode="json")


def test_a_finished_run_is_stored_with_metrics_and_every_case() -> None:
    deps, runs, _ = _deps()
    output = asyncio.run(run_eval_run(_input(), deps))
    stored = asyncio.run(runs.get("run-1"))
    assert stored == output.run
    assert stored is not None
    assert stored.status == "done"
    assert stored.corpus_version == "2026-11-20T10:00Z"
    assert stored.user_id == USER
    assert stored.metrics is not None
    assert stored.metrics.cases == len(GOLDEN.root)
    assert [c.case_id for c in stored.cases] == [c.id for c in GOLDEN.root]
    assert stored.models == ("stub/stub",)
    assert stored.finished_at is not None


def test_the_end_notifies_the_user_who_started_the_run() -> None:
    deps, _, inbox = _deps()
    asyncio.run(run_eval_run(_input(), deps))
    [note] = asyncio.run(inbox.list_for("user_id", USER))
    assert note.kind == "eval_run_done"
    assert note.link.endswith("run-1")


def test_a_retried_workflow_does_not_notify_twice() -> None:
    deps, _, inbox = _deps()
    for _ in range(2):
        asyncio.run(run_eval_run(_input(), deps))
    assert len(asyncio.run(inbox.list_for("user_id", USER))) == 1


async def _blobbed(cases: GoldenSet) -> tuple[BlobCaseSets, str]:
    store = build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    data = json.dumps([c.model_dump(mode="json") for c in cases.root]).encode()
    ref = await store.put(
        data,
        kind=BlobKind.DATASET,
        content_type="application/json",
        expires_at=datetime.now(UTC) + timedelta(days=1),
    )
    return BlobCaseSets(ROOT / "evals" / "golden" / "cases.json", store), ref.blob_id


def test_a_user_file_runs_the_same_metrics() -> None:
    own = GoldenSet(GOLDEN.root[:30])
    sets, blob_id = asyncio.run(_blobbed(own))
    deps, _, _ = _deps(sets)
    golden = asyncio.run(run_eval_run(_input(), deps)).run
    output = asyncio.run(
        run_eval_run(
            _input(
                run_id="run-2",
                case_set="user_file",
                case_file="jury.json",
                dataset_blob_id=blob_id,
            ),
            deps,
        )
    )
    assert output.run.case_file == "jury.json"
    assert output.run.metrics is not None
    assert output.run.metrics.cases == 30
    assert golden.metrics is not None
    assert set(output.run.metrics.model_dump()) == set(golden.metrics.model_dump())


def test_a_missing_file_ends_as_a_failed_run_and_still_notifies() -> None:
    store = build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    sets = BlobCaseSets(ROOT / "evals" / "golden" / "cases.json", store)
    deps, runs, inbox = _deps(sets)
    output = asyncio.run(
        run_eval_run(
            _input(
                case_set="user_file",
                case_file="absent.json",
                dataset_blob_id="dataset_aabbccddeeff00112233445566778899",
            ),
            deps,
        )
    )
    assert output.run.status == "failed"
    assert output.run.metrics is None
    assert output.run.finished_at is not None
    assert asyncio.run(runs.get("run-1")) == output.run
    assert len(asyncio.run(inbox.list_for("user_id", USER))) == 1


def test_an_input_that_is_not_an_eval_run_is_refused() -> None:
    deps, _, _ = _deps()
    with pytest.raises(ValueError, match="run_id"):
        asyncio.run(run_eval_run({"case_set": "golden"}, deps))
