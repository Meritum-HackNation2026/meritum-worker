"""Evaluation input: JSON or CSV case files of at least 30 cases (US-OBS-05)."""

import csv
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from meritum_worker.observability import (
    GoldenCase,
    TooFewCasesError,
    load_eval_cases,
    load_golden_set,
    meritum_eval,
)

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "cases.json"


def _write_csv(path: Path, cases: list[GoldenCase]) -> None:
    def cell(value: object) -> str:
        if value is None:
            return ""
        return value if isinstance(value, str) else json.dumps(value)

    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(GoldenCase.model_fields))
        writer.writeheader()
        for case in cases:
            row = case.model_dump(mode="json")
            writer.writerow({key: cell(value) for key, value in row.items()})


def test_golden_set_is_a_valid_eval_file() -> None:
    assert len(load_eval_cases(GOLDEN).root) >= 30


def test_csv_holds_the_same_cases_as_json(tmp_path: Path) -> None:
    golden = load_golden_set(GOLDEN)
    path = tmp_path / "jury.csv"
    _write_csv(path, list(golden.root))
    assert load_eval_cases(path) == golden


def test_too_small_file_names_the_required_count(tmp_path: Path) -> None:
    path = tmp_path / "jury.json"
    cases = [c.model_dump(mode="json") for c in load_golden_set(GOLDEN).root]
    plain = [c for c in cases if not c.get("injection") and not c.get("related_case")]
    path.write_text(json.dumps(plain[:12]), encoding="utf-8")
    with pytest.raises(TooFewCasesError, match="at least 30 cases, got 12"):
        load_eval_cases(path)


def test_invalid_csv_case_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "jury.csv"
    path.write_text("id,scenario\n" + "Z-x,Z\n" * 30, encoding="utf-8")
    with pytest.raises(ValidationError):
        load_eval_cases(path)


def test_count_comes_before_case_validation(tmp_path: Path) -> None:
    path = tmp_path / "jury.csv"
    path.write_text("id,scenario\nZ-x,Z\n", encoding="utf-8")
    with pytest.raises(TooFewCasesError, match="got 1"):
        load_eval_cases(path)


def test_csv_with_byte_order_mark_is_read(tmp_path: Path) -> None:
    golden = load_golden_set(GOLDEN)
    path = tmp_path / "jury.csv"
    _write_csv(path, list(golden.root))
    path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
    assert load_eval_cases(path) == golden


@pytest.mark.parametrize(
    ("content", "argv", "message"),
    [
        ("id,scenario,sources\n" + "D-x,D,{nie-json\n" * 30, [], "jury.csv: Expecting"),
        ("[]", [], "jury.json: an evaluation file needs at least 30 cases"),
        ('{"id": "D-x"}', [], "jury.json: a case file holds a list of cases"),
        (GOLDEN.read_text(encoding="utf-8"), ["--max-concurrency", "0"], "argument"),
    ],
    ids=["bad JSON cell", "too few cases", "not a list", "zero concurrency"],
)
def test_bad_input_ends_with_a_message(
    content: str,
    argv: list[str],
    message: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = tmp_path / ("jury.csv" if content.startswith("id,") else "jury.json")
    path.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as stop:
        meritum_eval(["--cases", str(path), *argv])
    assert stop.value.code == 2
    error = capsys.readouterr().err.replace("\n", " ")
    assert "meritum-eval: error:" in error
    assert message in error
