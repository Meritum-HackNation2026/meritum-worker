"""Workflow bodies as plain functions, so tests need no DBOS runtime."""

from typing import Any

from meritum_core.jobs.contracts import CONTRACT_VERSION, PING


def ping(payload: dict[str, Any], env: str) -> dict[str, Any]:
    """Echo the message back with the worker's environment.

    Returns:
        A `PingOutput` as a JSON object.

    Raises:
        ValueError: the payload has an unsupported contract version.
    """
    data = PING.input.model_validate(payload)
    if data.contract_version != CONTRACT_VERSION:
        msg = f"unsupported contract_version {data.contract_version}"
        raise ValueError(msg)
    return PING.output(message=data.message, worker_env=env).model_dump(mode="json")
