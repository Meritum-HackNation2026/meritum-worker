from collections.abc import Callable

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import Citation, ClaimResult, Escalation, Source
from pydantic import HttpUrl

from meritum_worker.observability import CaseRun, GoldenCase

MAIN_CLAIM = "W Pcimiu jest nowa strefa parkowania."


def _case(**changes: object) -> GoldenCase:
    raw: dict[str, object] = {
        "id": "D-own-test",
        "scenario": "D",
        "origin": "own",
        "channel": "web",
        "text": "Czy w Pcimiu jest nowa strefa parkowania?",
        "main_claim": MAIN_CLAIM,
        "expected_status": "done",
        "expected_verdict": "insufficient_evidence",
        "expected_behavior": "Mówi, jakie źródło rozstrzygnęłoby sprawę.",
    }
    return GoldenCase.model_validate(raw | changes)


def _claim(
    verdict: str, text: str = MAIN_CLAIM, cites: tuple[str, ...] = ()
) -> ClaimResult:
    # model_construct: decisive verdicts need full premises, irrelevant to scoring.
    citations = [
        Citation.model_construct(source=Source.model_construct(url=HttpUrl(url)))
        for url in cites
    ]
    return ClaimResult.model_construct(claim=text, verdict=verdict, citations=citations)


def _result(
    status: str = "done",
    claims: tuple[ClaimResult, ...] = (),
    check_id: str = "check-1",
    *,
    escalated: bool = False,
) -> CheckResult:
    escalation = Escalation.model_construct(state="recommended") if escalated else None
    return CheckResult.model_construct(
        check_id=check_id,
        status=status,
        claims=list(claims),
        escalation=escalation,
        corpus_version="none",
    )


type MakeRun = Callable[..., CaseRun]
type Make[T] = Callable[..., T]


def _run(
    golden: GoldenCase, outcome: CheckResult, seconds: float = 1.0, **usage: object
) -> CaseRun:
    # model_construct: results built with model_construct do not revalidate.
    return CaseRun.model_construct(
        None, case=golden, result=outcome, seconds=seconds, **usage
    )


@pytest.fixture
def run() -> MakeRun:
    """A case run from a case and a result."""
    return _run


@pytest.fixture
def case() -> Make[GoldenCase]:
    """A valid D case; keyword arguments replace its fields."""
    return _case


@pytest.fixture
def claim() -> Make[ClaimResult]:
    """A claim result with a verdict, the main claim's text and cited URLs."""
    return _claim


@pytest.fixture
def result() -> Make[CheckResult]:
    """A check result with a state and claims."""
    return _result
