"""Steps of the coded technical-failure scenario in features/checks.feature (#70)."""

from behave import given, then, when
from behave.runner import Context
from check_support import DEFAULT_TEXT, deps, run
from meritum_core.checks.contracts import CONTRACT_VERSION


@given("worker na kontrakcie v{version:d} z meritum-core")
def worker_uses_contract(_context: Context, version: int) -> None:
    assert version == CONTRACT_VERSION


@when("model nie odpowiada w kroku write_answer")
def model_has_no_answer(context: Context) -> None:
    context.deps = deps("llm_stub_extraction_only.json")
    run(context, DEFAULT_TEXT)


@then('failure_code wynosi "{code}"')
def result_has_failure_code(context: Context, code: str) -> None:
    assert context.result.result.failure_code == code


@then('message nie zaczyna się od "{prefix}"')
def result_has_no_copy_key(context: Context, prefix: str) -> None:
    assert not (context.result.result.message or "").startswith(prefix)
