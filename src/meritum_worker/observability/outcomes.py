"""Case outcome by the main claim and verdict macro-F1 (US-OBS-04).

Features:
    US-OBS-04, US-OBS-05, F-27
"""

from collections.abc import Sequence

from meritum_core.checks import CheckResult

from meritum_worker.observability.constants import (
    ABSTAINING_VERDICTS,
    DECISIVE_VERDICTS,
    NON_VERDICT_CLASS,
    OUTCOME_ORDER,
)
from meritum_worker.observability.models import GoldenCase
from meritum_worker.observability.report import Outcome


def expected_label(case: GoldenCase) -> str:
    """The expected verdict, or the expected state when it is not done.

    Args:
        case: The case.

    Returns:
        The label.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    return case.expected_verdict or case.expected_status


def case_outcome(case: GoldenCase, result: CheckResult) -> tuple[str, Outcome]:
    """Score the case by its main claim; several matches keep the worst outcome.

    The claims matching the main claim count; when none matches, every claim
    does. A result that is not done is its state.

    Args:
        case: The case.
        result: The check's result.

    Returns:
        The predicted label and its outcome.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    expected = expected_label(case)
    predicted = _predicted_labels(case, result)
    scored = [(label, _outcome(expected, label)) for label in predicted]
    return min(scored, key=lambda pair: OUTCOME_ORDER.index(pair[1]))


def macro_f1(pairs: Sequence[tuple[str, str]]) -> float:
    """Macro-F1 over (expected, predicted) labels.

    A predicted state that is not a verdict and not the expected label falls
    into one separate error class (US-OBS-04); a met expected state counts as
    its own class.

    Args:
        pairs: Expected and predicted label of each case.

    Returns:
        The mean F1 over every class seen; 0 without cases.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    classed = [(e, p if _keeps_label(e, p) else NON_VERDICT_CLASS) for e, p in pairs]
    classes = {label for pair in classed for label in pair}
    scores = [_f1(label, classed) for label in classes]
    return sum(scores) / len(scores) if scores else 0.0


def _f1(label: str, classed: list[tuple[str, str]]) -> float:
    hits = sum(e == p == label for e, p in classed)
    expected = sum(e == label for e, _ in classed)
    predicted = sum(p == label for _, p in classed)
    return 2 * hits / (expected + predicted)


def _keeps_label(expected: str, predicted: str) -> bool:
    is_verdict = predicted in DECISIVE_VERDICTS or predicted in ABSTAINING_VERDICTS
    return is_verdict or predicted == expected


def _predicted_labels(case: GoldenCase, result: CheckResult) -> list[str]:
    if result.status != "done" or not result.claims:
        return [result.status]
    main = [c for c in result.claims if _same_claim(c.claim, case.main_claim)]
    return [claim.verdict for claim in main or result.claims]


def _same_claim(found: str, main: str) -> bool:
    found, main = _normal(found), _normal(main)
    return found in main or main in found


def _normal(text: str) -> str:
    return " ".join(text.casefold().split()).rstrip(".")


def _outcome(expected: str, predicted: str) -> Outcome:
    if predicted == expected:
        return "correct"
    if predicted in DECISIVE_VERDICTS:
        return "wrong_decisive"
    if predicted in ABSTAINING_VERDICTS:
        return "wrong_abstention"
    return "non_verdict"
