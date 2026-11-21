"""Gate configurations, the cases and the answers the comparison scores.

Models, versions and regions live in the config files of ``evals/gates/``,
never in code.

Features:
    US-BEZ-01, US-OBS-04, US-SPR-06, F-27, ADR-35
"""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel

type Seconds = Annotated[float, Field(ge=0)]
"""Wall-clock time of one gate call."""
type Label = Annotated[str, Field(min_length=1, max_length=100)]
"""A short free-form name, e.g. a provider or a region."""


class Frozen(BaseModel):
    """Base of every gate model: immutable, unknown fields rejected.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """

    model_config = ConfigDict(frozen=True, extra="forbid")


class GateModel(Frozen):
    """What a configuration runs on; every field goes to the report.

    Attributes:
        provider: Who serves the model, e.g. ``model_armor`` or ``workers_ai``.
        model: The model or template id.
        version: The model version the run used.
        region: Where the text is processed.
        price_per_call_usd: Mean price of one call; 0 inside a free tier.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """

    provider: Label
    model: Label
    version: Label
    region: Label
    price_per_call_usd: Annotated[float, Field(ge=0)] = 0.0


class _Config(Frozen):
    name: Label
    runs_on: GateModel


class InjectionConfig(_Config):
    """An injection classifier screened live on the golden set's texts.

    Attributes:
        gate: Always ``injection``.
        settings: ``InjectionGateSettings`` fields; secrets stay in the
            ``MERITUM_INJECTION_GATE_*`` environment.

    Features:
        US-OBS-04, US-BEZ-01, F-19, F-27, ADR-23, ADR-35
    """

    gate: Literal["injection"]
    settings: dict[str, str]


class DlpConfig(_Config):
    """The personal-data masking run live on the DLP case file.

    Attributes:
        gate: Always ``dlp``.
        settings: ``PiiGateSettings`` fields; the project may come from
            ``MERITUM_PII_*``.
        cases: The DLP case file, relative to the config file.

    Features:
        US-OBS-04, US-BEZ-01, US-BEZ-04, F-20, F-27, ADR-35
    """

    gate: Literal["dlp"]
    settings: dict[str, str]
    cases: Path


class RerankerConfig(_Config):
    """Two meritum-eval reports on the golden set, with and without the reranker.

    Attributes:
        gate: Always ``reranker``.
        with_reranker: Report of the run with ``MERITUM_RERANKER`` set.
        without_reranker: Report of the run with the null gate.

    Features:
        US-OBS-04, US-BEZ-01, US-KOR-02, F-12, F-27, ADR-35
    """

    gate: Literal["reranker"]
    with_reranker: Path
    without_reranker: Path


class NliConfig(_Config):
    """The NLI stance pre-check, compared only: its answers come from a file.

    Attributes:
        gate: Always ``nli``.
        calls: The recorded answers, relative to the config file.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-06, ADR-35
    """

    gate: Literal["nli"]
    calls: Path


class ClassifierConfig(_Config):
    """The input classifier, compared only: its answers come from a file.

    Attributes:
        gate: Always ``input_classifier``.
        cases: The input cases with their expected class, relative to the file.
        calls: The recorded answers, relative to the config file.

    Features:
        US-BEZ-01, US-OBS-04, US-SPR-06, F-07, F-27, ADR-35
    """

    gate: Literal["input_classifier"]
    cases: Path
    calls: Path


type GateConfig = Annotated[
    InjectionConfig | DlpConfig | RerankerConfig | NliConfig | ClassifierConfig,
    Field(discriminator="gate"),
]
"""One configuration file of ``evals/gates/``."""


class GateConfigFile(RootModel[GateConfig]):
    """Validates one configuration file.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """


class GateCall(Frozen):
    """One gate call on one case.

    Attributes:
        case_id: The golden or DLP case.
        output: Text left after cutting flagged ranges, or the masked text.
        seconds: Time of the call.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-35
    """

    case_id: Label
    output: str
    seconds: Seconds


class DlpCase(Frozen):
    """A text with invented personal data and content that must stay.

    Attributes:
        id: Unique id.
        text: The text; no real personal data (AGENTS.md).
        personal: Items the masking must remove.
        keep: Public figures' names, amounts and institution addresses that
            must stay unchanged.

    Features:
        US-OBS-04, US-BEZ-01, US-BEZ-04, F-20, F-27
    """

    id: Label
    text: str
    personal: tuple[str, ...] = ()
    keep: tuple[str, ...] = ()


class DlpCases(RootModel[tuple[DlpCase, ...]]):
    """The DLP case file.

    Features:
        US-OBS-04, US-BEZ-01, US-BEZ-04, F-20, F-27
    """
