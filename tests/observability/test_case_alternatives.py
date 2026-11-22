"""Alternative verdicts, check dates and ids across the golden files (worker#181)."""

import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from meritum_worker.observability import GoldenCase

FOLDER = Path(__file__).resolve().parents[2] / "evals" / "golden"
FILES = ("cases.json", "fact-checks.json")


def raw(**changes: object) -> dict[str, object]:
    case: dict[str, object] = {
        "id": "D-own-test",
        "scenario": "D",
        "origin": "own",
        "channel": "web",
        "text": "Czy w Pcimiu jest nowa strefa parkowania?",
        "main_claim": "W Pcimiu jest nowa strefa parkowania.",
        "expected_status": "done",
        "expected_verdict": "insufficient_evidence",
        "expected_behavior": "Mówi, jakie źródło rozstrzygnęłoby sprawę.",
    }
    return case | changes


def _ids(name: str) -> list[str]:
    cases = json.loads((FOLDER / name).read_text(encoding="utf-8"))
    return [GoldenCase.model_validate(case).id for case in cases]


@pytest.mark.parametrize("name", FILES)
def test_every_case_in_the_file_validates_on_its_own(name: str) -> None:
    assert _ids(name)


def test_case_ids_do_not_repeat_across_files() -> None:
    golden, fact_checks = (set(_ids(name)) for name in FILES)
    assert not golden & fact_checks


def test_alternative_verdicts_and_check_date_are_optional() -> None:
    plain = GoldenCase.model_validate(raw())
    assert plain.acceptable_verdicts == ()
    assert plain.checked_at is None


def test_case_keeps_alternative_verdicts_and_check_date() -> None:
    case = GoldenCase.model_validate(
        raw(acceptable_verdicts=["false", "not_verifiable"], checked_at="2026-11-22")
    )
    assert case.acceptable_verdicts == ("false", "not_verifiable")
    assert case.checked_at == date(2026, 11, 22)


@pytest.mark.parametrize(
    "changes",
    [
        {"acceptable_verdicts": ["insufficient_evidence"]},
        {"acceptable_verdicts": ["false", "false"]},
        {"acceptable_verdicts": ["maybe"]},
        {
            "expected_status": "out_of_scope",
            "expected_verdict": None,
            "acceptable_verdicts": ["false"],
        },
        {"checked_at": "22.11.2026"},
    ],
    ids=[
        "alternative repeats the verdict",
        "alternative listed twice",
        "unknown alternative",
        "alternative without a verdict",
        "check date not ISO",
    ],
)
def test_invalid_alternative_or_date_is_rejected(changes: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        GoldenCase.model_validate(raw(**changes))
