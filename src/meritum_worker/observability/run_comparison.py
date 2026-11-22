"""Compare two stored runs: metric differences and the cases whose outcome changed.

Features:
    US-OBS-06, US-POW-05, F-28, ADR-28
"""

from meritum_core.checks.contracts import EvalMetrics, EvalOutcome, EvalRun
from pydantic import BaseModel, ConfigDict

from meritum_worker.observability.constants import REPORT_DECIMALS


class MetricChange(BaseModel):
    """One metric in both runs.

    Attributes:
        metric: the ``EvalMetrics`` field.
        before: its value in the first run; None when it applies to no case.
        after: its value in the second run.
        change: after minus before; None when either value is None.

    Features:
        US-OBS-06, F-28
    """

    model_config = ConfigDict(frozen=True)

    metric: str
    before: float | None
    after: float | None
    change: float | None


class ChangedCase(BaseModel):
    """A case that ended with another outcome in the second run.

    Attributes:
        case_id: the case id.
        scenario: its scenario A-J.
        before: its outcome in the first run.
        after: its outcome in the second run.
        predicted_before: its predicted label in the first run.
        predicted_after: its predicted label in the second run.

    Features:
        US-OBS-06, F-28
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    scenario: str
    before: EvalOutcome
    after: EvalOutcome
    predicted_before: str
    predicted_after: str


class RunComparison(BaseModel):
    """Two runs side by side, for the evaluation page.

    Attributes:
        before: id of the first run.
        after: id of the second run.
        metrics: every metric in both runs.
        changed_cases: cases present in both with another outcome.
        only_before: ids of cases only the first run has.
        only_after: ids of cases only the second run has.

    Features:
        US-OBS-06, F-28
    """

    model_config = ConfigDict(frozen=True)

    before: str
    after: str
    metrics: tuple[MetricChange, ...]
    changed_cases: tuple[ChangedCase, ...]
    only_before: tuple[str, ...]
    only_after: tuple[str, ...]


def compare_runs(before: EvalRun, after: EvalRun) -> RunComparison:
    """Compare two finished runs.

    Args:
        before: the earlier run.
        after: the later run.

    Returns:
        The metric differences (after minus before) and the cases that changed.

    Raises:
        ValueError: a run has no metrics, so it did not finish.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-28
    """
    if before.metrics is None or after.metrics is None:
        msg = "only a finished run can be compared"
        raise ValueError(msg)
    first = {case.case_id: case for case in before.cases}
    second = {case.case_id: case for case in after.cases}
    changed = tuple(
        ChangedCase(
            case_id=case_id,
            scenario=case.scenario,
            before=first[case_id].outcome,
            after=case.outcome,
            predicted_before=first[case_id].predicted,
            predicted_after=case.predicted,
        )
        for case_id, case in second.items()
        if case_id in first and first[case_id].outcome != case.outcome
    )
    return RunComparison(
        before=before.id,
        after=after.id,
        metrics=_changes(before.metrics, after.metrics),
        changed_cases=changed,
        only_before=tuple(case_id for case_id in first if case_id not in second),
        only_after=tuple(case_id for case_id in second if case_id not in first),
    )


def _changes(before: EvalMetrics, after: EvalMetrics) -> tuple[MetricChange, ...]:
    old, new = before.model_dump(), after.model_dump()
    return tuple(
        MetricChange(
            metric=name,
            before=old[name],
            after=new[name],
            change=None
            if old[name] is None or new[name] is None
            else round(new[name] - old[name], REPORT_DECIMALS),
        )
        for name in old
    )
