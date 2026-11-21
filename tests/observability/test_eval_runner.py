"""The evaluation run on the stub model: no network, no database (ADR-28)."""

import asyncio
from datetime import timedelta
from pathlib import Path
from typing import override

import pytest
from meritum_core.checks.contracts import CheckRecord
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import (
    LlmProvider,
    LlmResult,
    LlmSettings,
    Prompt,
    build_llm,
)
from pydantic import BaseModel

from meritum_worker.checks import CheckDeps, FakePageFetcher
from meritum_worker.observability import (
    GoldenCase,
    GoldenSet,
    load_golden_set,
    run_eval,
)
from meritum_worker.observability.factory import build_eval_deps

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = load_golden_set(ROOT / "evals" / "golden" / "cases.json")
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"


class _SlowRecords(InMemoryCheckRecordRepository):
    """Saves every record as answered 42 s after it was received."""

    @override
    async def save(self, record: CheckRecord) -> None:
        late = record.received_at + timedelta(seconds=42)
        await super().save(record.model_copy(update={"answered_at": late}))


class _BrokenLlm:
    @staticmethod
    async def complete[T: BaseModel](prompt: Prompt, output: type[T]) -> LlmResult[T]:
        raise RuntimeError(prompt, output)


def _deps(records: InMemoryCheckRecordRepository | None = None) -> CheckDeps:
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=STUB_ANSWER)
    return CheckDeps(
        llm=build_llm(settings),
        records=records or InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
    )


def test_every_case_runs_in_file_order_with_time_from_the_record() -> None:
    deps = _deps(_SlowRecords())
    runs = asyncio.run(run_eval(GOLDEN, lambda _case: deps, max_concurrency=4))
    assert [r.case.id for r in runs] == [c.id for c in GOLDEN.root]
    assert all(r.seconds == pytest.approx(42) for r in runs)
    assert {r.models for r in runs if r.result.status == "done"} == {("stub/stub",)}


def test_a_check_that_raises_ends_as_technical_failure() -> None:
    broken = CheckDeps(
        llm=_BrokenLlm(),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
    )
    runs = asyncio.run(run_eval(GOLDEN, lambda _case: broken, max_concurrency=2))
    assert {r.result.status for r in runs} == {"technical_failure"}
    assert all(0 <= r.seconds < 1 and r.models == () for r in runs)


def test_forced_model_fault_fails_only_its_case(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MERITUM_LLM_STUB_FIXTURES", str(STUB_ANSWER))
    deps_for = build_eval_deps(LlmSettings())

    def status(case: GoldenCase) -> str:
        return next(r for r in runs if r.case.id == case.id).result.status

    runs = asyncio.run(run_eval(GOLDEN, deps_for, max_concurrency=4))
    faulty = [c for c in GOLDEN.root if c.fault == "llm"]
    assert faulty
    assert {status(c) for c in faulty} == {"technical_failure"}
    assert status(GOLDEN.root[0]) == "done"


def test_failed_check_keeps_its_time_from_the_record() -> None:
    no_answers = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=None)
    deps = _deps(_SlowRecords())
    broken = CheckDeps(
        llm=build_llm(no_answers), records=deps.records, pages=deps.pages, pii=deps.pii
    )
    runs = asyncio.run(run_eval(GOLDEN, lambda _case: broken, max_concurrency=4))
    assert {r.result.status for r in runs} == {"technical_failure"}
    assert all(r.seconds == pytest.approx(42) for r in runs)


def test_screenshot_without_text_is_out_of_scope() -> None:
    raw = [c.model_dump(mode="json") for c in GOLDEN.root]
    screenshot = next(c for c in raw if c.get("image_text"))
    screenshot["text"] = None
    cases = GoldenSet.model_validate(raw)
    runs = asyncio.run(run_eval(cases, lambda _case: _deps(), max_concurrency=4))
    found = next(r for r in runs if r.case.id == screenshot["id"])
    # No OCR yet: the system answers a screenshot alone with out_of_scope (README).
    assert found.result.status == "out_of_scope"
    assert found.models == ()
    assert len(runs) == len(raw)
