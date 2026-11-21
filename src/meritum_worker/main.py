"""Entry point: launch DBOS, register queues and wait for work."""

import os
import signal
import threading
from functools import cache
from typing import Any

from dbos import DBOS, DBOSConfig, WorkflowSerializationFormat
from meritum_core.jobs.contracts import APPLICATION_NAME, CHECK, DEFAULT_QUEUE, PING
from meritum_core.shared.llm import LlmSettings

from meritum_worker import checks, jobs
from meritum_worker.checks.factory import build_check_deps, build_check_runtime


def env() -> str:
    """The environment name (MERITUM_ENV): local, dev or prd.

    Returns:
        The name; the worker runs only jobs enqueued with it.

    Features:
        none (infrastructure)
    """
    return os.environ.get("MERITUM_ENV", "local")


@DBOS.workflow(name=PING.name, serialization_type=WorkflowSerializationFormat.PORTABLE)
def ping_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Smoke-test workflow (see meritum_core.jobs.contracts.PING).

    Args:
        payload: the `PingInput` JSON object.

    Returns:
        The `PingOutput` JSON object.

    Features:
        ADR-03
    """
    return jobs.ping(payload, env())


@cache
def check_deps() -> checks.CheckDeps:
    """The ports of the `check` workflow, built once per process.

    Returns:
        The model from ``MERITUM_LLM_*`` and the record repository.

    Features:
        US-SPR-01, F-22
    """
    return build_check_deps(LlmSettings())


@DBOS.workflow(name=CHECK.name, serialization_type=WorkflowSerializationFormat.PORTABLE)
async def check_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Check one request (see meritum_core.jobs.contracts.CHECK).

    Args:
        payload: the `CheckInput` JSON object.

    Returns:
        The `CheckOutput` JSON object; progress goes to the PROGRESS_KEY stream.

    Features:
        US-SPR-01, US-OBS-01, F-22, ADR-03
    """
    return await checks.run_check(
        payload, DBOS.workflow_id or "", check_deps(), build_check_runtime()
    )


def config() -> DBOSConfig:
    """DBOS settings from the environment (written by the deploy on the host).

    Returns:
        The config; the schema holds the DBOS system tables of this env.

    Features:
        none (infrastructure)
    """
    return {
        "name": APPLICATION_NAME,
        "system_database_url": os.environ.get(
            "MERITUM_DBOS_URL", "postgresql://meritum:meritum@localhost:5432/meritum"
        ),
        "dbos_system_schema": os.environ.get("MERITUM_DBOS_SCHEMA", "worker_local"),
        # The backend enqueues with app_version=<env>; only this env's jobs run here.
        "application_version": env(),
    }


def main() -> None:
    """Run the worker until SIGTERM or SIGINT.

    Features:
        ADR-03
    """
    DBOS(config=config())
    DBOS.launch()
    DBOS.register_queue(DEFAULT_QUEUE)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    DBOS.logger.info("meritum-worker ready (env=%s)", env())
    stop.wait()
    DBOS.destroy()


if __name__ == "__main__":
    main()
