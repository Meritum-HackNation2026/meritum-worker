"""Entry point: launch DBOS, register queues and wait for work."""

import os
import signal
import threading
from typing import Any

from dbos import DBOS, DBOSConfig, WorkflowSerializationFormat
from meritum_core.jobs.contracts import APPLICATION_NAME, DEFAULT_QUEUE, PING

from meritum_worker import jobs

ENV = os.environ.get("MERITUM_ENV", "local")


@DBOS.workflow(name=PING.name, serialization_type=WorkflowSerializationFormat.PORTABLE)
def ping_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Smoke-test workflow (see meritum_core.jobs.contracts.PING).

    Returns:
        The `PingOutput` JSON object.
    """
    return jobs.ping(payload, ENV)


def config() -> DBOSConfig:
    """DBOS settings from the environment (written by the deploy on the host).

    Returns:
        The config; the schema holds the DBOS system tables of this env.
    """
    return {
        "name": APPLICATION_NAME,
        "system_database_url": os.environ.get(
            "MERITUM_DBOS_URL", "postgresql://meritum:meritum@localhost:5432/meritum"
        ),
        "dbos_system_schema": os.environ.get("MERITUM_DBOS_SCHEMA", "worker_local"),
        # The backend enqueues with app_version=<env>; only this env's jobs run here.
        "application_version": ENV,
    }


def main() -> None:
    """Run the worker until SIGTERM or SIGINT."""
    DBOS(config=config())
    DBOS.launch()
    DBOS.register_queue(DEFAULT_QUEUE)
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    DBOS.logger.info("meritum-worker ready (env=%s)", ENV)
    stop.wait()
    DBOS.destroy()


if __name__ == "__main__":
    main()
