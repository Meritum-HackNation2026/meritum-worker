"""Steps for features/checks.feature; they call only the public API."""

from behave import given, then, when
from behave.runner import Context
from meritum_core.jobs.contracts import CONTRACT_VERSION

from meritum_worker import jobs


@given('wiadomość "{message}" w bieżącej wersji kontraktu')
def message_in_current_contract(context: Context, message: str) -> None:
    context.payload = {"contract_version": CONTRACT_VERSION, "message": message}


@when('worker w środowisku "{env}" wykona ping')
def worker_pings(context: Context, env: str) -> None:
    context.result = jobs.ping(context.payload, env)


@then('odpowiedź zawiera wiadomość "{message}" i środowisko "{env}"')
def reply_has_message_and_env(context: Context, message: str, env: str) -> None:
    assert context.result["message"] == message
    assert context.result["worker_env"] == env
