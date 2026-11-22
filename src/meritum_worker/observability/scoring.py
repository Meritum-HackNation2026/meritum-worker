"""Turn the case runs of one evaluation into its report (US-OBS-04).

Features:
    US-OBS-04, US-OBS-05, F-27
"""

import statistics
from collections.abc import Sequence

from meritum_worker.observability.constants import (
    ABSTAINING_VERDICTS,
    COST_SAMPLE_CHECKS,
    DECISIVE_VERDICTS,
    LATENCY_PERCENTILE,
    REPORT_DECIMALS,
    UNANSWERED_VERDICT,
)
from meritum_worker.observability.outcomes import (
    case_outcome,
    expected_label,
    macro_f1,
)
from meritum_worker.observability.quality import (
    abstention_rate,
    citation_recall,
    fact_check_hit_rate,
    host,
    share,
)
from meritum_worker.observability.report import (
    CaseRun,
    CaseScore,
    EvalReport,
    Ratio,
    ScenarioScore,
)


def score_runs(runs: Sequence[CaseRun]) -> EvalReport:
    """Compute every metric of the report from the case runs.

    Time comes from each case's CheckRecord, failed cases included, so a
    technical failure stays in the median.

    Args:
        runs: One run per case, in file order.

    Returns:
        The report.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    scores = [_score(run) for run in runs]
    pairs = list(zip(scores, runs, strict=True))
    seconds = sorted(run.seconds for run in runs) or [0.0]
    count = max(len(runs), 1)
    cost = sum(run.cost_usd for run in runs) / count
    abstaining = [s for s in scores if s.expected in ABSTAINING_VERDICTS]
    attacks = [s for s, run in pairs if run.case.injection is not None]
    unanswered = [run for s, run in pairs if s.predicted == UNANSWERED_VERDICT]
    return EvalReport(
        models=tuple(sorted({model for run in runs for model in run.models})),
        corpus_versions=tuple(sorted({run.result.corpus_version for run in runs})),
        cases=len(runs),
        macro_f1=_round(macro_f1([(s.expected, _f1_label(s)) for s in scores])),
        accuracy=share([s.outcome == "correct" for s in scores]),
        abstention_rate=abstention_rate(runs),
        citation_recall=citation_recall(runs),
        fact_check_hit_rate=fact_check_hit_rate(runs),
        citation_coverage=_citation_coverage(runs),
        citation_correctness=_citation_correctness(runs),
        abstention=share([s.outcome == "correct" for s in abstaining]),
        robustness=share([s.outcome == "correct" for s in attacks]),
        median_seconds=_round(statistics.median(seconds)),
        p95_seconds=_round(_percentile(seconds)),
        max_seconds=_round(seconds[-1]),
        input_tokens_per_check=_round(sum(r.input_tokens for r in runs) / count),
        output_tokens_per_check=_round(sum(r.output_tokens for r in runs) / count),
        output_tokens_per_second=_tokens_per_second(runs),
        cost_per_check_usd=_round(cost),
        cost_100_checks_usd=_round(cost * COST_SAMPLE_CHECKS),
        channel_consistency=_channel_consistency(runs),
        information_loop=share([r.result.escalation is not None for r in unanswered]),
        scenarios=_scenarios(scores),
        outcomes=tuple(scores),
    )


def _score(run: CaseRun) -> CaseScore:
    predicted, outcome = case_outcome(run.case, run.result)
    return CaseScore(
        id=run.case.id,
        scenario=run.case.scenario,
        expected=expected_label(run.case),
        predicted=predicted,
        outcome=outcome,
        seconds=run.seconds,
        check_id=run.check_id,
    )


def _f1_label(score: CaseScore) -> str:
    # An acceptable alternative is the expected verdict for F1 (worker#170).
    return score.expected if score.outcome == "correct" else score.predicted


def _round(value: float) -> float:
    return round(value, REPORT_DECIMALS)


def _tokens_per_second(runs: Sequence[CaseRun]) -> float:
    # Checks without answer tokens (failures, screenshots) would dilute the speed.
    answered = [run for run in runs if run.output_tokens]
    seconds = sum(run.seconds for run in answered)
    return (
        _round(sum(run.output_tokens for run in answered) / seconds) if seconds else 0.0
    )


def _percentile(ordered: Sequence[float]) -> float:
    if len(ordered) == 1:
        return ordered[0]
    cuts = statistics.quantiles(ordered, n=100, method="inclusive")
    return cuts[LATENCY_PERCENTILE - 1]


def _citation_coverage(runs: Sequence[CaseRun]) -> Ratio:
    claims = [c for run in runs for c in run.result.claims]
    decisive = [c for c in claims if c.verdict in DECISIVE_VERDICTS]
    return share([bool(c.citations) for c in decisive])


def _citation_correctness(runs: Sequence[CaseRun]) -> Ratio:
    # A citation is correct when its source's host is one the case lists.
    hits: list[bool] = []
    for run in runs:
        hosts = {host(str(s.url)) for s in run.case.sources}
        cited = [c for claim in run.result.claims for c in claim.citations]
        if hosts:
            hits += [host(str(c.source.url)) in hosts for c in cited]
    return share(hits)


def _channel_consistency(runs: Sequence[CaseRun]) -> Ratio:
    # Channels render the same CheckResult (US-WTY-03): same state, verdicts, sources.
    by_id = {run.case.id: run for run in runs}
    hits = [
        _comparable(run) == _comparable(by_id[run.case.related_case])
        for run in runs
        if run.case.variant == "other_channel" and run.case.related_case in by_id
    ]
    return share(hits)


def _comparable(run: CaseRun) -> tuple[str, list[str], list[str]]:
    # The JSON fields every channel shows the same; wording may differ.
    claims = run.result.claims
    cited = {str(c.source.url) for claim in claims for c in claim.citations}
    return run.result.status, sorted(c.verdict for c in claims), sorted(cited)


def _scenarios(scores: Sequence[CaseScore]) -> tuple[ScenarioScore, ...]:
    result: list[ScenarioScore] = []
    for scenario in sorted({s.scenario for s in scores}):
        own = [s for s in scores if s.scenario == scenario]
        correct = sum(s.outcome == "correct" for s in own)
        result.append(
            ScenarioScore(
                scenario=scenario,
                cases=len(own),
                correct=correct,
                accuracy=_round(correct / len(own)),
            )
        )
    return tuple(result)
