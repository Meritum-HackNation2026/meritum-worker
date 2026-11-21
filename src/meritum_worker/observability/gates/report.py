"""The gate comparison report: one entry per configuration.

Features:
    US-BEZ-01, US-OBS-04, F-27, ADR-35
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict

from meritum_worker.observability.gates.models import GateModel
from meritum_worker.observability.report import Ratio


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class _Calls(_Frozen):
    median_seconds: float
    cost_100_calls_usd: float


class InjectionScore(_Calls):
    """An injection classifier on the Polish attack set (ADR-23).

    Attributes:
        kind: Always ``injection``.
        attacks: Attack cases screened.
        robustness: Attacks repelled: flagged, the instruction gone from what
            the model would see, and the clean case's question left intact.
        clean: Cases without an attack screened.
        false_alarms: Clean cases with anything flagged.
        median_seconds: Median time per call.
        cost_100_calls_usd: Price of 100 calls.

    Features:
        US-BEZ-01, F-19, F-27, ADR-23, ADR-35
    """

    kind: Literal["injection"] = "injection"
    attacks: int
    robustness: Ratio
    clean: int
    false_alarms: Ratio


class DlpScore(_Calls):
    """Personal-data masking, including what it must not mask.

    Attributes:
        kind: Always ``dlp``.
        personal_items: Invented personal-data items in the cases.
        detected: Items gone from the masked text.
        keep_items: Public names, amounts and institution addresses.
        over_masking: Of those, items changed by the masking.
        median_seconds: Median time per call.
        cost_100_calls_usd: Price of 100 calls.

    Features:
        US-BEZ-04, F-20, F-27, ADR-35
    """

    kind: Literal["dlp"] = "dlp"
    personal_items: int
    detected: Ratio
    keep_items: int
    over_masking: Ratio


class ClassifierScore(_Calls):
    """The input classifier against the cases' expected states.

    Attributes:
        kind: Always ``input_classifier``.
        cases: Cases classified.
        accuracy: Cases given their expected class.
        blocked_claims: Claim cases the classifier would stop before the model.
        median_seconds: Median time per call.
        cost_100_calls_usd: Price of 100 calls.

    Features:
        US-OBS-04, US-SPR-06, F-07, F-27, ADR-35
    """

    kind: Literal["input_classifier"] = "input_classifier"
    cases: int
    accuracy: Ratio
    blocked_claims: Ratio


class NliScore(_Calls):
    """The NLI stance pre-check; compared only, no production run uses it.

    Attributes:
        kind: Always ``nli``.
        pairs: Claim and fragment pairs.
        model_agreement: Pairs where NLI gives the model's stance.
        manual_sample: Pairs a person labelled.
        manual_agreement: Of those, pairs where NLI gives the person's stance.
        production: Always False (ADR-35).
        median_seconds: Median time per call.
        cost_100_calls_usd: Price of 100 calls.

    Features:
        US-OBS-04, F-27, ADR-06, ADR-35
    """

    kind: Literal["nli"] = "nli"
    pairs: int
    model_agreement: Ratio
    manual_sample: int
    manual_agreement: Ratio
    production: Literal[False] = False


class RerankerDelta(_Frozen):
    """Run with the reranker minus run with the null gate.

    Attributes:
        kind: Always ``reranker``.
        macro_f1: Difference of macro-F1.
        citation_correctness: Difference of citation correctness; None when a
            run has none.
        median_seconds: Difference of median time.
        cost_100_checks_usd: Difference of the cost of 100 checks.

    Features:
        US-KOR-02, F-12, F-27, ADR-35
    """

    kind: Literal["reranker"] = "reranker"
    macro_f1: float
    citation_correctness: float | None
    median_seconds: float
    cost_100_checks_usd: float


type GateScore = InjectionScore | DlpScore | ClassifierScore | NliScore | RerankerDelta
"""The score of one configuration, by gate."""


class GateEntry(_Frozen):
    """One configuration in the report.

    Attributes:
        name: The configuration's name.
        runs_on: Provider, model, version, region and price.
        score: Its metrics.

    Features:
        US-OBS-04, F-27, ADR-35
    """

    name: str
    runs_on: GateModel
    score: GateScore


class GatesReport(_Frozen):
    """The comparison, saved in ``evals/reports/``.

    Attributes:
        date: Day of the run.
        entries: One per configuration, in the order given.

    Features:
        US-OBS-04, F-27, ADR-35
    """

    date: date
    entries: tuple[GateEntry, ...]
