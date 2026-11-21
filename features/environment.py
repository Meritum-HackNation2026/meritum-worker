"""behave hooks: every scenario starts with an empty state."""

from behave.runner import Context


def before_scenario(context: Context, _scenario: object) -> None:
    context.payload = {}
    context.result = {}
