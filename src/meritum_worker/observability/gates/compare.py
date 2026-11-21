"""Load gate configurations and turn each into a report entry.

Features:
    US-BEZ-01, US-OBS-04, F-27, ADR-35
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from meritum_core.security.injection import InjectionGatePort
from meritum_core.security.pii import PiiGatePort

from meritum_worker.observability.gates.models import (
    DlpCases,
    DlpConfig,
    GateCalls,
    GateConfig,
    GateConfigFile,
    InjectionConfig,
    RecordedConfig,
    RerankerConfig,
    StanceCalls,
)
from meritum_worker.observability.gates.report import (
    GateEntry,
    GateScore,
    GatesReport,
)
from meritum_worker.observability.gates.runner import mask_cases, screen_cases
from meritum_worker.observability.gates.scoring import (
    reranker_delta,
    score_classifier,
    score_dlp,
    score_injection,
    score_nli,
)
from meritum_worker.observability.models import GoldenSet
from meritum_worker.observability.report import EvalReport


@dataclass(frozen=True)
class GateBuilders:
    """Builds the live gate a configuration names.

    Attributes:
        injection: The classifier gate of an injection configuration.
        pii: The masking gate of a DLP configuration.

    Features:
        US-OBS-04, US-BEZ-01, US-BEZ-04, F-27, ADR-35
    """

    injection: Callable[[InjectionConfig], InjectionGatePort]
    pii: Callable[[DlpConfig], PiiGatePort]


def load_gate_config(path: Path) -> GateConfig:
    """Read a configuration; its file paths become relative to it.

    Args:
        path: A file of ``evals/gates/``.

    Returns:
        The configuration.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """
    config = GateConfigFile.model_validate_json(path.read_text(encoding="utf-8")).root
    here = path.parent
    match config:
        case DlpConfig():
            return config.model_copy(update={"cases": here / config.cases})
        case RecordedConfig():
            return config.model_copy(update={"calls": here / config.calls})
        case RerankerConfig():
            on, off = config.with_reranker, config.without_reranker
            changes = {"with_reranker": here / on, "without_reranker": here / off}
            return config.model_copy(update=changes)
        case InjectionConfig():
            return config


async def compare_gates(
    configs: Sequence[GateConfig],
    golden: GoldenSet,
    builders: GateBuilders,
    day: date,
) -> GatesReport:
    """Score every configuration, live gates one call at a time.

    Args:
        configs: Loaded configurations.
        golden: The golden set.
        builders: Builds the live gates.
        day: Date of the run.

    Returns:
        The report.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """
    entries = [
        GateEntry(
            name=config.name,
            runs_on=config.runs_on,
            score=await _score(config, golden, builders),
        )
        for config in configs
    ]
    return GatesReport(date=day, entries=tuple(entries))


async def _score(
    config: GateConfig, golden: GoldenSet, builders: GateBuilders
) -> GateScore:
    match config:
        case InjectionConfig():
            calls = await screen_cases(golden, builders.injection(config))
            return score_injection(golden, calls, config.runs_on)
        case DlpConfig():
            cases = DlpCases.model_validate_json(_read(config.cases)).root
            calls = await mask_cases(cases, builders.pii(config))
            return score_dlp(cases, calls, config.runs_on)
        case RerankerConfig():
            on = EvalReport.model_validate_json(_read(config.with_reranker))
            off = EvalReport.model_validate_json(_read(config.without_reranker))
            return reranker_delta(on, off)
        case RecordedConfig(gate="nli"):
            stances = StanceCalls.model_validate_json(_read(config.calls)).root
            return score_nli(stances, config.runs_on)
        case RecordedConfig():
            calls = GateCalls.model_validate_json(_read(config.calls)).root
            return score_classifier(golden, calls, config.runs_on)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")
