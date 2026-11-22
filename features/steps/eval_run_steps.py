"""Steps of the evaluation run scenarios (worker#38); they call the public API."""

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import EvalCaseSet, EvalRun
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import EvalRunInput
from meritum_core.notifications.fakes import InMemoryNotificationRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import (
    CheckDeps,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.observability import (
    EvalRunDeps,
    GoldenSet,
    compare_runs,
    load_golden_set,
    run_eval_run,
)
from meritum_worker.observability.fakes import InMemoryCaseSets, InMemoryEvalRuns

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = load_golden_set(ROOT / "evals" / "golden" / "cases.json")
STUB_ANSWER = ROOT / "features" / "fixtures" / "llm_stub_answer.json"
STAFF = "google:1234567890"
OWN_CASES = 12


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


def _setup(context: Context, case_sets: InMemoryCaseSets) -> None:
    context.runs = InMemoryEvalRuns()
    context.inbox = InMemoryNotificationRepository()
    context.deps = EvalRunDeps(
        runs=context.runs,
        case_sets=case_sets,
        deps_for=lambda _case: _check_deps(),
        notifications=context.inbox,
        max_concurrency=4,
        clock=lambda: datetime.now(UTC),
    )


def _start(
    context: Context,
    run_id: str,
    case_set: EvalCaseSet,
    case_file: str | None = None,
) -> EvalRun:
    payload = EvalRunInput(
        run_id=run_id,
        case_set=case_set,
        case_file=case_file,
        corpus_version="2026-11-20T10:00Z",
        user_id=STAFF,
    )
    output = asyncio.run(run_eval_run(payload.model_dump(mode="json"), context.deps))
    return output.run


@given("backend zleca workflow przebiegu ewaluacji dla golden setu")
def backend_orders_golden_run(context: Context) -> None:
    _setup(context, InMemoryCaseSets(golden=GOLDEN))


@when("przebieg się kończy")
def run_finishes(context: Context) -> None:
    context.run = _start(context, "run-1", "golden")


@then(
    "w bazie jest EvalRun z miernikami, datą, corpus_version i wynikami"
    " każdego przypadku"
)
def run_is_stored(context: Context) -> None:
    stored = asyncio.run(context.runs.get("run-1"))
    assert stored == context.run
    assert stored is not None
    assert stored.metrics is not None
    assert stored.finished_at is not None
    assert stored.corpus_version == "2026-11-20T10:00Z"
    assert len(stored.cases) == len(GOLDEN.root)


@then(
    "emitowane jest zdarzenie powiadomienia o końcu przebiegu dla analityka,"
    " który go uruchomił"
)
def staff_user_is_notified(context: Context) -> None:
    [note] = asyncio.run(context.inbox.list_for("user_id", STAFF))
    assert note.kind == "eval_run_done"


@given("zestaw z pliku CSV zapisany przez backend")
def csv_saved_by_backend(context: Context) -> None:
    own = tuple(
        c for c in GOLDEN.root if c.related_case is None and c.injection is None
    )[:OWN_CASES]
    _setup(
        context,
        InMemoryCaseSets(golden=GOLDEN, files={"jury.csv": GoldenSet(own)}),
    )
    context.golden_run = _start(context, "run-golden", "golden")


@when("backend zleca przebieg na tym zestawie")
def backend_orders_file_run(context: Context) -> None:
    context.run = _start(context, "run-file", "user_file", "jury.csv")


@then("przebieg liczy te same mierniki co na golden secie")
def same_metrics(context: Context) -> None:
    assert context.run.metrics is not None
    assert context.golden_run.metrics is not None
    assert set(context.run.metrics.model_dump()) == set(
        context.golden_run.metrics.model_dump()
    )
    assert context.run.metrics.cases == OWN_CASES


@given("dwa zapisane przebiegi")
def two_stored_runs(context: Context) -> None:
    _setup(context, InMemoryCaseSets(golden=GOLDEN))
    context.before = _start(context, "run-a", "golden")
    after = context.before.model_copy(update={"id": "run-b"})
    first, *rest = after.cases
    outcome = "correct" if first.outcome != "correct" else "wrong_decisive"
    flipped = first.model_copy(update={"outcome": outcome})
    context.after = after.model_copy(update={"cases": (flipped, *rest)})


@when("backend prosi o porównanie")
def backend_asks_comparison(context: Context) -> None:
    context.comparison = compare_runs(context.before, context.after)


@then("wynik podaje różnice mierników i przypadki, które zmieniły wynik")
def comparison_has_differences(context: Context) -> None:
    assert context.comparison.metrics
    assert [c.case_id for c in context.comparison.changed_cases] == [
        context.after.cases[0].case_id
    ]
