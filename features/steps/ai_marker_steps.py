"""Steps of the AI marker on a finished check (features/checks.feature).

Features:
    US-BEZ-07
"""

from behave import then
from behave.runner import Context


@then(
    "CheckResult ma znacznik AI z dostawcą i modelem wywołania,"
    " które napisało odpowiedź"
)
def result_has_ai_marker(context: Context) -> None:
    """The marker names the provider and model of the answering call.

    Args:
        context: the behave context with ``result`` and ``record`` from the run.

    Features:
        US-BEZ-07
    """
    marker = context.result.result.ai_marker
    answer = context.record.models[-1]  # write_answer makes the last model call
    assert marker is not None
    assert marker.ai_generated
    assert (marker.provider, marker.model) == (answer.provider, answer.model)
    assert marker.generated_at <= context.record.answered_at
