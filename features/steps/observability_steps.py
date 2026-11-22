"""Steps for features/observability.feature; they call only the public API."""

import asyncio
import csv
import json
import math
import os
import shutil
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import override

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CheckRecord
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import CheckDeps, FakePageFetcher, audio_ports, web_ports
from meritum_worker.observability import (
    GoldenCase,
    GoldenSet,
    TooFewCasesError,
    load_eval_cases,
    load_golden_set,
    meritum_eval,
    run_eval,
    score_runs,
)

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "cases.json"


@given("plik golden setu w repozytorium")
def golden_file_in_repo(context: Context) -> None:
    context.path = GOLDEN


@when("skrypt waliduje przypadki")
def script_validates_cases(context: Context) -> None:
    context.golden = load_golden_set(context.path)


@then(
    "każdy przypadek ma wejście, kanał, oczekiwany stan albo werdykt głównego"
    " twierdzenia i scenariusz A–J"  # ruff: ignore[ambiguous-unicode-character-string]  # step text copied from the issue's Gherkin
)
def every_case_is_complete(context: Context) -> None:
    for case in context.golden.root:
        assert case.text or case.url or case.image_text, case.id
        assert case.channel, case.id
        assert case.main_claim, case.id
        assert case.expected_status != "done" or case.expected_verdict, case.id
        assert case.expected_behavior, case.id
        assert case.scenario in "ABCDEFGHIJ", case.id


@given("przypadki scenariusza H")
def scenario_h_cases(context: Context) -> None:
    golden = load_golden_set(GOLDEN)
    context.cases = [case for case in golden.root if case.scenario == "H"]


@then(
    "istnieje wariant z powtórzeniem w tej samej sesji i wariant z powtórzeniem"
    " z innego kanału"
)
def both_repeat_variants_exist(context: Context) -> None:
    variants = {case.variant for case in context.cases}
    assert {"same_session", "other_channel"} <= variants


# --- evaluation run (worker#25) ---------------------------------------------------

STUB_ANSWER = GOLDEN.parents[2] / "features" / "fixtures" / "llm_stub_answer.json"
JURY_CASES = 30
MEDIAN_WITH_FAILURE = 20.0
SLOWEST = 50.0
REPORT_METRICS = (
    "macro_f1",
    "citation_coverage",
    "citation_correctness",
    "abstention",
    "robustness",
    "median_seconds",
    "max_seconds",
    "cost_100_checks_usd",
    "channel_consistency",
    "information_loop",
)


def _self_contained(count: int) -> list[GoldenCase]:
    # The first cases whose references point only at cases already taken.
    taken: list[GoldenCase] = []
    for case in load_golden_set(GOLDEN).root:
        refs = {case.related_case, case.injection and case.injection.clean_case}
        if refs - {None} <= {c.id for c in taken}:
            taken.append(case)
    return taken[:count]


def _csv_cell(value: object) -> str:
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


@given("plik CSV z 30 przypadkami w formacie przypadków")
def jury_csv(context: Context) -> None:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    context.path = folder / "jury.csv"
    context.report_path = folder / "report.json"
    rows = [case.model_dump(mode="json") for case in _self_contained(JURY_CASES)]
    with context.path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(GoldenCase.model_fields))
        writer.writeheader()
        writer.writerows({k: _csv_cell(v) for k, v in row.items()} for row in rows)


@when('członek jury uruchamia "uv run meritum-eval --cases jury.csv"')
def jury_runs_eval(context: Context) -> None:
    stub = {
        "MERITUM_LLM_PROVIDER": "stub",
        "MERITUM_LLM_STUB_FIXTURES": str(STUB_ANSWER),
    }
    previous = {name: os.environ.get(name) for name in stub}
    os.environ.update(stub)
    try:
        meritum_eval(
            ["--cases", str(context.path), "--output", str(context.report_path)]
        )
    finally:
        for name, value in previous.items():
            os.environ.pop(name, None)
            if value is not None:
                os.environ[name] = value


@then(
    "raport podaje macro-F1, pokrycie i poprawność cytowań, wstrzymanie, odporność,"
    " medianę i maksimum czasu, koszt 100 testów, spójność kanałów i pętlę informacji"
)
def report_has_metrics(context: Context) -> None:
    report = json.loads(context.report_path.read_text(encoding="utf-8"))
    assert report["cases"] == JURY_CASES
    for metric in REPORT_METRICS:
        assert metric in report, metric
    assert {s["scenario"] for s in report["scenarios"]} <= set("ABCDEFGHIJ")


class _ShiftedRecords(InMemoryCheckRecordRepository):
    """Saves every record as answered a fixed time after it was received."""

    def __init__(self, seconds: float) -> None:
        super().__init__()
        self._delay = timedelta(seconds=seconds)

    @override
    async def save(self, record: CheckRecord) -> None:
        answered = record.received_at + self._delay
        await super().save(record.model_copy(update={"answered_at": answered}))


def _case(slug: str) -> GoldenCase:
    return GoldenCase.model_validate(
        {
            "id": f"D-own-{slug}",
            "scenario": "D",
            "origin": "own",
            "channel": "web",
            "text": "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł",
            "main_claim": "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł",
            "expected_status": "done",
            "expected_verdict": "insufficient_evidence",
            "expected_behavior": "Mówi, jakie źródło rozstrzygnęłoby sprawę.",
        }
    )


def _deps(seconds: float, fixtures: Path | None) -> CheckDeps:
    settings = LlmSettings(provider=LlmProvider.STUB, stub_fixtures=fixtures)
    return CheckDeps(
        llm=build_llm(settings),
        records=_ShiftedRecords(seconds),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
    )


@given("przypadek kończy się stanem technical_failure")
def failed_case(context: Context) -> None:
    # The stub without answers fails like an unavailable model provider.
    context.cases = GoldenSet.model_validate([_case(s) for s in ("a", "b", "c")])
    context.deps = {
        "D-own-a": _deps(10, STUB_ANSWER),
        "D-own-b": _deps(SLOWEST, None),
        "D-own-c": _deps(MEDIAN_WITH_FAILURE, STUB_ANSWER),
    }


@when("skrypt liczy czas")
def script_scores(context: Context) -> None:
    deps = context.deps
    runs = asyncio.run(run_eval(context.cases, lambda c: deps[c.id], 1))
    assert runs[1].result.status == "technical_failure"
    context.report = score_runs(runs)


@then("czas przypadku z CheckRecord liczy się do mediany")
def failure_in_median(context: Context) -> None:
    assert math.isclose(context.report.median_seconds, MEDIAN_WITH_FAILURE)
    assert math.isclose(context.report.max_seconds, SLOWEST)


@then("stan niebędący werdyktem jest w macro-F1 osobną klasą błędu")
def non_verdict_is_a_class(context: Context) -> None:
    # insufficient_evidence: tp 2, fn 1 -> F1 4/5; non_verdict: fp 1 -> 0.
    assert math.isclose(context.report.macro_f1, 0.4)


@given("plik z 12 przypadkami")
def small_file(context: Context) -> None:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    context.path = folder / "jury.json"
    cases = [case.model_dump(mode="json") for case in _self_contained(12)]
    context.path.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")


@when("skrypt waliduje wejście")
def script_validates_input(context: Context) -> None:
    try:
        load_eval_cases(context.path)
    except TooFewCasesError as error:
        context.error = error
    else:
        context.error = None


@then("kończy się błędem z liczbą wymaganych przypadków")
def error_names_required_count(context: Context) -> None:
    assert context.error is not None
    assert "30" in str(context.error)
    assert "12" in str(context.error)
