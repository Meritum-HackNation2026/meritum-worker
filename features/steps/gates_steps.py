"""Steps for features/gates.feature; live gates are fakes, never a provider."""

import asyncio
import json
import shutil
import tempfile
from datetime import date
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from meritum_core.security.injection import InjectionGatePort, TextRange
from meritum_core.security.pii import NullPiiGate

from meritum_worker.observability import load_golden_set
from meritum_worker.observability.gates import (
    GateBuilders,
    compare_gates,
    load_gate_config,
)

ROOT = Path(__file__).resolve().parents[2]
GATES = ROOT / "evals" / "gates"
GOLDEN = ROOT / "evals" / "golden" / "cases.json"
RUNS_ON = {"provider": "p", "model": "m", "version": "v", "region": "eu"}


class _PayloadGate:
    """Flags the whole text when it holds one of the golden set's attacks."""

    def __init__(self, payloads: set[str]) -> None:
        self._payloads = payloads

    async def screen(self, text: str) -> tuple[TextRange, ...]:
        hit = any(payload in text for payload in self._payloads)
        return (TextRange(0, len(text)),) if hit else ()


def _builders(gate: InjectionGatePort) -> GateBuilders:
    return GateBuilders(injection=lambda _: gate, pii=lambda _: NullPiiGate())


def _folder(context: Context) -> Path:
    folder = Path(tempfile.mkdtemp())
    context.add_cleanup(shutil.rmtree, folder)
    return folder


def _write(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _compare(context: Context, gate: InjectionGatePort | None = None) -> None:
    golden = getattr(context, "golden", None) or load_golden_set(GOLDEN)
    builders = _builders(gate or _PayloadGate(set()))
    run = compare_gates(context.configs, golden, builders, date(2026, 11, 22))
    context.report = asyncio.run(run)


@given(
    "polski zestaw ataków z golden setu i dwie konfiguracje klasyfikatora"
    " (Model Armor w eu, Prompt Guard na Workers AI)"
)
def attacks_and_two_classifiers(context: Context) -> None:
    names = ("injection-model-armor-eu.json", "injection-workers-ai.json")
    context.configs = [load_gate_config(GATES / name) for name in names]


@when("zespół uruchamia porównanie bramek")
def team_runs_gate_comparison(context: Context) -> None:
    golden = load_golden_set(GOLDEN)
    payloads = {c.injection.payload for c in golden.root if c.injection is not None}
    _compare(context, _PayloadGate(payloads))


@then(
    "raport podaje dla każdej odporność według definicji z ADR-23, fałszywe alarmy"
    " na przypadkach bez ataku, czas i koszt"
)
def report_has_robustness_alarms_time_cost(context: Context) -> None:
    assert len(context.report.entries) == len(context.configs)
    for entry in context.report.entries:
        score = entry.score
        assert score.kind == "injection"
        # Whole-text flags lose the question, so only page attacks are repelled.
        assert 0 < score.robustness < 1
        assert score.false_alarms == 0
        assert score.median_seconds >= 0
        assert score.cost_100_calls_usd > 0
        assert entry.runs_on.region
        assert entry.runs_on.version


@given("golden set")
def golden_set(context: Context) -> None:
    context.golden = load_golden_set(GOLDEN)


@when("porównanie uruchamia przebieg z rerankerem i z pustą bramką")
def compare_with_and_without_reranker(context: Context) -> None:
    folder = _folder(context)
    base = json.loads((GATES / "reranker-vertex.json").read_text(encoding="utf-8"))
    report = json.loads(
        (ROOT / "features" / "fixtures" / "eval_report.json").read_text("utf-8")
    )
    _write(folder / "off.json", report)
    _write(folder / "on.json", report | {"macro_f1": 0.75, "median_seconds": 9.0})
    config = base | {"with_reranker": "on.json", "without_reranker": "off.json"}
    context.configs = [load_gate_config(_write(folder / "rerank.json", config))]
    _compare(context)


@then(
    "raport podaje różnicę macro-F1, poprawności cytowań, mediany czasu"
    " i kosztu 100 testów"
)
def report_has_reranker_delta(context: Context) -> None:
    delta = context.report.entries[0].score
    assert delta.kind == "reranker"
    on = (delta.macro_f1, delta.median_seconds)
    assert on == (0.25, -1)
    assert (delta.citation_correctness, delta.cost_100_checks_usd) == (0, 0)


@given("konfiguracja z wstępną oceną wymowy NLI")
def nli_config(context: Context) -> None:
    folder = _folder(context)
    pair = {"claim": "c", "fragment": "f", "seconds": 0.1}
    calls = [
        pair | {"nli": "supports", "model": "supports", "manual": "supports"},
        pair | {"nli": "context", "model": "refutes"},
    ]
    _write(folder / "calls.json", calls)
    config = {"name": "nli", "gate": "nli", "runs_on": RUNS_ON, "calls": "calls.json"}
    context.configs = [load_gate_config(_write(folder / "nli.json", config))]


@when("porównanie się kończy")
def comparison_ends(context: Context) -> None:
    _compare(context)


@then(
    "raport podaje zgodność NLI z oceną modelu i ręczną próbą, a żaden przebieg"
    " produkcyjny nie używa NLI"
)
def report_has_nli_agreement(context: Context) -> None:
    score = context.report.entries[0].score
    assert (score.model_agreement, score.manual_agreement) == (0.5, 1)
    assert score.production is False
    src = ROOT / "src" / "meritum_worker"
    production = [p for p in src.rglob("*.py") if "observability" not in p.parts]
    assert not any(
        "observability.gates" in p.read_text(encoding="utf-8") for p in production
    )


@given(
    "przypadki DLP z fikcyjnymi danymi osobowymi, nazwiskami osób publicznych,"
    " kwotami i adresami instytucji"
)
def dlp_cases(context: Context) -> None:
    context.configs = [load_gate_config(GATES / "dlp-patterns.json")]


@when("porównanie uruchamia bramkę DLP")
def comparison_runs_dlp(context: Context) -> None:
    _compare(context)


@then(
    "raport podaje wykryte dane osobowe i nadmiarowe maskowanie treści, która musi"
    " zostać bez zmian"
)
def report_has_dlp_detection_and_over_masking(context: Context) -> None:
    score = context.report.entries[0].score
    assert score.kind == "dlp"
    assert score.personal_items > 0
    assert score.keep_items > 0
    assert score.detected is not None
    assert score.over_masking is not None


@given("zapisane odpowiedzi klasyfikatora wejścia na golden secie")
def recorded_classifier(context: Context) -> None:
    folder = _folder(context)
    golden = load_golden_set(GOLDEN)
    calls = [{"case_id": c.id, "output": "claim", "seconds": 0.1} for c in golden.root]
    calls[0]["output"] = "out_of_scope"
    _write(folder / "calls.json", calls)
    config = {
        "name": "klasyfikator",
        "gate": "input_classifier",
        "runs_on": RUNS_ON,
        "calls": "calls.json",
    }
    context.configs = [load_gate_config(_write(folder / "classifier.json", config))]


@then(
    "raport podaje trafność i udział twierdzeń, które klasyfikator zatrzymałby"
    " przed głównym modelem"
)
def report_has_classifier_scores(context: Context) -> None:
    score = context.report.entries[0].score
    assert score.kind == "input_classifier"
    assert 0 < score.accuracy < 1
    assert 0 < score.blocked_claims < 1
