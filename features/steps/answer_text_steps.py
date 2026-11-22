"""Steps of the citizen-text scenario in features/checks.feature: no code names."""

from behave import given, then
from behave.runner import Context
from check_support import deps


@given("model zwraca wyjaśnienie z nazwą kodu werdyktu albo ograniczenia")
def model_writes_codes(context: Context) -> None:
    context.deps = deps("llm_stub_answer_codes.json")


@then("wyjaśnienie i ograniczenia nie zawierają nazw kodów")
def text_has_no_codes(context: Context) -> None:
    result = context.result.result
    claim = result.claims[0]
    text = " ".join([claim.explanation, claim.unresolved or "", *result.limitations])
    assert "_" not in text, text
    assert "Brak wystarczających dowodów" in text
