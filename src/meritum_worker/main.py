"""Entry points: the worker (DBOS, queues, workflows) and its deploy migrations."""

import argparse
import asyncio
import os
import signal
import sys
import threading
from datetime import UTC, datetime
from functools import cache
from typing import Any

import psycopg
from dbos import DBOS, DBOSConfig, WorkflowSerializationFormat
from meritum_core.corpus import CorpusSettings
from meritum_core.jobs.contracts import (
    APPLICATION_NAME,
    CHECK,
    DEFAULT_QUEUE,
    DELETE_SUBJECT,
    PING,
)
from meritum_core.shared.blobs import BlobSettings
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.database.adapters import apply_migrations
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings
from meritum_core.shared.llm import LlmSettings

from meritum_worker import checks, corpus, jobs, security
from meritum_worker.checks.factory import build_check_deps, build_check_runtime
from meritum_worker.corpus.adapters import apply_corpus_migrations


@cache
def _euvs_copy() -> corpus.EuvsCopyPort:
    # One copy per process; the sync step reuses it across runs.
    return corpus.build_euvsdisinfo_copy(CorpusSettings())


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
        The model from ``MERITUM_LLM_*`` and the record repository from
        ``MERITUM_DATABASE_*``.

    Features:
        US-SPR-01, F-22
    """
    return build_check_deps(LlmSettings(), DatabaseSettings())


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
    output = await checks.run_check(
        payload, DBOS.workflow_id or "", check_deps(), build_check_runtime()
    )
    return output.model_dump(mode="json")


@DBOS.workflow(
    name=corpus.SYNC_WORKFLOW,
    serialization_type=WorkflowSerializationFormat.PORTABLE,
)
def euvsdisinfo_sync_workflow() -> dict[str, Any]:
    """Refresh the local EUvsDisinfo copy; started by hand, never during a check.

    Returns:
        The ``SyncReport`` JSON; only ``missing_env`` without a token.

    Features:
        US-KOR-08, F-11, ADR-26
    """
    return euvsdisinfo_sync_step()


@DBOS.step(retries_allowed=True)
def euvsdisinfo_sync_step() -> dict[str, Any]:
    """Run ``corpus.run_euvsdisinfo_sync`` as one step; a failure writes nothing.

    Returns:
        The ``SyncReport`` JSON.

    Features:
        US-KOR-08, F-11
    """
    embeddings = build_embeddings(EmbeddingsSettings())
    report = asyncio.run(
        corpus.run_euvsdisinfo_sync(
            os.environ, _euvs_copy(), embeddings, now=datetime.now(UTC)
        )
    )
    if report.missing_env:
        DBOS.logger.warning("EUvsDisinfo sync skipped, missing %s", report.missing_env)
    return report.model_dump(mode="json")


def _retention_deps() -> security.RetentionDeps:
    blobs = BlobSettings() if security.BLOB_PROVIDER_ENV in os.environ else None
    return security.build_retention_deps(DatabaseSettings(), blobs)


async def _erase(payload: dict[str, Any]) -> dict[str, Any]:
    return (await security.erase_subject(payload, _retention_deps())).model_dump()


@DBOS.workflow(
    name=DELETE_SUBJECT.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def delete_subject_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Erase one person (DELETE_SUBJECT); one step keeps what it reads out of history.

    Args:
        payload: the `DeleteSubjectInput` JSON object.

    Returns:
        The `DeleteSubjectOutput` JSON object.

    Features:
        US-BEZ-05, F-20, ADR-03
    """
    return await DBOS.run_step_async({"retries_allowed": True}, _erase, payload)


@DBOS.workflow(name=security.RETENTION_WORKFLOW)
async def retention_workflow(scheduled_at: datetime, _context: object) -> None:
    """Delete data past retention; started hourly by the RETENTION_CRON schedule.

    Args:
        scheduled_at: the schedule's time; the cutoffs count back from it.
        _context: the schedule's context, unused.

    Features:
        US-BEZ-05, US-POW-04, F-20, ADR-13
    """
    report = await DBOS.run_step_async(
        {"retries_allowed": True},
        security.run_retention,
        _retention_deps(),
        scheduled_at,
    )
    DBOS.logger.info("retention deleted %s", report.model_dump())


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
    DBOS.apply_schedules(
        [
            {
                "schedule_name": security.RETENTION_SCHEDULE_NAME,
                "workflow_fn": retention_workflow,
                "schedule": security.RETENTION_CRON,
            }
        ]
    )
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    DBOS.logger.info("meritum-worker ready (env=%s)", env())
    stop.wait()
    DBOS.destroy()


def migrate(argv: list[str] | None = None) -> None:
    """Run meritum-core migrations before a deploy (``meritum-worker-migrate``).

    Always migrates the env's app schema named by ``MERITUM_DATABASE_URL``; with
    ``--corpus`` (deploys from main only) also the shared ``corpus`` schema.

    Args:
        argv: command-line arguments; ``sys.argv[1:]`` when None.

    Features:
        US-WDR-01, US-KOR-02, F-30, F-12, ADR-04, ADR-32
    """
    parser = argparse.ArgumentParser(prog="meritum-worker-migrate")
    parser.add_argument("--corpus", action="store_true", help="also migrate corpus")
    corpus = parser.parse_args(argv).corpus
    url = DatabaseSettings(provider=DatabaseProvider.POSTGRES).url
    if url is None:  # the settings validator already refuses this
        sys.exit("MERITUM_DATABASE_URL is required")
    steps = [(f"app_{env()}", apply_migrations)]
    if corpus:
        steps.append(("corpus", apply_corpus_migrations))
    for name, apply in steps:
        try:
            applied = apply(url.get_secret_value())
        except (psycopg.Error, RuntimeError) as exc:
            # one line: the deploy turns the last output line into its ::error
            sys.exit(f"migration {name} failed: {' '.join(str(exc).split())}")
        sys.stdout.write(f"{name}: {', '.join(applied) or 'up to date'}\n")


if __name__ == "__main__":
    main()
