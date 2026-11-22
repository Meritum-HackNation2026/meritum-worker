"""One evaluation run: each case's run, and the report the metrics make of them.

Features:
    US-OBS-04, US-OBS-05, F-27
"""

from typing import Annotated, Literal

from meritum_core.checks import CheckResult
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.observability.models import GoldenCase

type Outcome = Literal["wrong_decisive", "non_verdict", "wrong_abstention", "correct"]
"""Case outcome, from the worst (US-OBS-04)."""
type Ratio = Annotated[float, Field(ge=0, le=1)] | None
"""Share of the cases a metric applies to; None when it applies to none."""


class CaseRun(BaseModel):
    """What one case's check produced, as the CheckRecord saw it.

    Attributes:
        case: The case.
        result: The check's result; a technical failure when the check raised.
        seconds: received_at to answered_at of the CheckRecord.
        input_tokens: Prompt tokens of every model call.
        output_tokens: Answer tokens of every model call.
        cost_usd: Cost of every model call.
        models: ``provider/model`` of every model called.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """

    model_config = ConfigDict(frozen=True)

    case: GoldenCase
    result: CheckResult
    seconds: Annotated[float, Field(ge=0)]
    input_tokens: Annotated[int, Field(ge=0)] = 0
    output_tokens: Annotated[int, Field(ge=0)] = 0
    cost_usd: Annotated[float, Field(ge=0)] = 0.0
    models: tuple[str, ...] = ()


class CaseScore(BaseModel):
    """One case in the report.

    Attributes:
        id: The case id.
        scenario: Its scenario A-J.
        expected: The expected verdict, or the state when it is not done.
        predicted: The main claim's verdict, or the state when it is not done.
        outcome: Where the prediction falls in the fixed order.
        seconds: Time from the CheckRecord.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """

    model_config = ConfigDict(frozen=True)

    id: str
    scenario: str
    expected: str
    predicted: str
    outcome: Outcome
    seconds: float


class ScenarioScore(BaseModel):
    """Quality per scenario, so runs on different models compare by scenario.

    Attributes:
        scenario: The scenario A-J.
        cases: How many cases it has.
        correct: How many ended with the correct outcome.
        accuracy: correct / cases.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """

    model_config = ConfigDict(frozen=True)

    scenario: str
    cases: int
    correct: int
    accuracy: float


class EvalReport(BaseModel):
    """The metrics of one run; one run per model gives a comparable table.

    shortcut: local report type until the EvalRun contract (core#36) lands;
    switch to it then so the evaluation page can store and compare runs.

    Attributes:
        models: ``provider/model`` of every model the run called.
        cases: How many cases ran.
        macro_f1: Verdict macro-F1, every non-verdict state one error class.
        citation_coverage: Decisive claims with at least one citation.
        citation_correctness: Citations whose host is among the case's sources.
        abstention: Abstaining cases answered with the expected abstention.
        robustness: Attack cases with the correct outcome.
        median_seconds: Median time, failed cases included.
        p95_seconds: 95th percentile of time.
        max_seconds: Longest time.
        input_tokens_per_check: Mean prompt tokens per check.
        output_tokens_per_check: Mean answer tokens per check.
        output_tokens_per_second: Answer tokens over the whole time of the
            checks that got any (end-to-end throughput); 0 when none did.
        cost_per_check_usd: Mean model cost per check.
        cost_100_checks_usd: Cost of 100 checks at that mean.
        channel_consistency: other_channel repeats whose CheckResult JSON has the
            repeated case's state, verdicts and cited sources.
        information_loop: insufficient_evidence answers that reached the
            moderator queue (an escalation).
        scenarios: Quality per scenario.
        outcomes: Every case.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """

    model_config = ConfigDict(frozen=True)

    models: tuple[str, ...]
    cases: int
    macro_f1: float
    citation_coverage: Ratio
    citation_correctness: Ratio
    abstention: Ratio
    robustness: Ratio
    median_seconds: float
    p95_seconds: float
    max_seconds: float
    input_tokens_per_check: float
    output_tokens_per_check: float
    output_tokens_per_second: float
    cost_per_check_usd: float
    cost_100_checks_usd: float
    channel_consistency: Ratio
    information_loop: Ratio
    scenarios: tuple[ScenarioScore, ...]
    outcomes: tuple[CaseScore, ...]
