"""Compare main-model configurations on one case file (US-WDR-02, US-OBS-04).

Each configuration is a TOML file with a ``name`` and an ``[llm]`` table of
``LlmSettings`` fields, so no model is named in code. Keys come from the
environment, never from the file.

Features:
    US-WDR-02, US-OBS-04, F-27
"""

import tomllib
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from meritum_core.shared.llm import LlmProvider, LlmSettings
from pydantic import BaseModel, ConfigDict, Field, field_validator

from meritum_worker.observability.constants import API_KEY_FIELDS
from meritum_worker.observability.report import CaseRun, EvalReport
from meritum_worker.observability.scoring import score_runs


class ModelConfig(BaseModel):
    """One candidate main model, read from a config file.

    Attributes:
        name: Label of the candidate in the report.
        llm: The model's settings; unset fields and the API key come from
            ``MERITUM_LLM_*`` and ``OPENROUTER_API_KEY``, unknown fields fail.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    llm: LlmSettings

    @field_validator("llm", mode="before")
    @classmethod
    def _no_key_in_file(cls, value: object) -> object:
        # Config files are committed; a key in one would leak (ADR-14).
        if isinstance(value, dict) and {k.lower() for k in value} & API_KEY_FIELDS:
            msg = "API keys come from the environment, never from the config file"
            raise ValueError(msg)
        return value


class ComparedModel(BaseModel):
    """One candidate's settings and its evaluation report.

    Attributes:
        name: Label of the candidate.
        provider: LLM provider.
        model: Model ID of the provider.
        region: Region or routing of the provider.
        reasoning: Thinking effort.
        zero_data_retention: OpenRouter zero-data-retention routing; None for
            other providers, where the flag means nothing.
        report: The candidate's metrics on the case file.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True)

    name: str
    provider: str
    model: str
    region: str
    reasoning: str
    zero_data_retention: bool | None
    report: EvalReport


class ModelComparison(BaseModel):
    """Every candidate's report on the same case file, for choosing by config.

    Attributes:
        generated_at: When the comparison ran.
        cases_file: The case file every candidate ran on.
        models: One entry per config file, in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    cases_file: str
    models: tuple[ComparedModel, ...]


def load_model_config(path: Path) -> ModelConfig:
    """Read one candidate's config file.

    Args:
        path: TOML file with ``name`` and an ``[llm]`` table.

    Returns:
        The validated config; a file that is not TOML or a missing, unknown
        or invalid field fails while parsing.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    with path.open("rb") as file:
        return ModelConfig.model_validate(tomllib.load(file))


def compare_models(
    entries: Sequence[tuple[ModelConfig, Sequence[CaseRun]]],
    cases_file: str,
    generated_at: datetime,
) -> ModelComparison:
    """Score each candidate's case runs into one comparison.

    Args:
        entries: Each config with its runs on the case file.
        cases_file: The case file the runs come from.
        generated_at: When the comparison ran.

    Returns:
        The comparison, candidates in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    models = tuple(
        ComparedModel(
            name=config.name,
            provider=config.llm.provider,
            model=config.llm.model,
            region=config.llm.region,
            reasoning=config.llm.reasoning,
            zero_data_retention=_zdr(config.llm),
            report=score_runs(runs),
        )
        for config, runs in entries
    )
    return ModelComparison(
        generated_at=generated_at, cases_file=cases_file, models=models
    )


def _zdr(settings: LlmSettings) -> bool | None:
    is_openrouter = settings.provider is LlmProvider.OPENROUTER
    return settings.openrouter_zdr if is_openrouter else None
