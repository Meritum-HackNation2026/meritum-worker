"""Steps for features/observability.feature; they call only the public API."""

from pathlib import Path

from behave import given, then, when
from behave.runner import Context

from meritum_worker.observability import load_golden_set

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "golden" / "cases.json"


@given("plik golden setu w repozytorium")
def golden_file_in_repo(context: Context) -> None:
    context.path = GOLDEN


@when("skrypt waliduje przypadki")
def script_validates_cases(context: Context) -> None:
    context.golden = load_golden_set(context.path)


@then(
    "każdy przypadek ma wejście, kanał, oczekiwany stan albo werdykt głównego"
    " twierdzenia i scenariusz A–J"  # ruff: ignore[ambiguous-unicode-character-string]  # step text copied from the issue's Gherkin
)
def every_case_is_complete(context: Context) -> None:
    for case in context.golden.root:
        assert case.text or case.url or case.image_text, case.id
        assert case.channel, case.id
        assert case.main_claim, case.id
        assert case.expected_status != "done" or case.expected_verdict, case.id
        assert case.expected_behavior, case.id
        assert case.scenario in "ABCDEFGHIJ", case.id


@given("przypadki scenariusza H")
def scenario_h_cases(context: Context) -> None:
    golden = load_golden_set(GOLDEN)
    context.cases = [case for case in golden.root if case.scenario == "H"]


@then(
    "istnieje wariant z powtórzeniem w tej samej sesji i wariant z powtórzeniem"
    " z innego kanału"
)
def both_repeat_variants_exist(context: Context) -> None:
    variants = {case.variant for case in context.cases}
    assert {"same_session", "other_channel"} <= variants
