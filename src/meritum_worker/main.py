"""Entry points: the worker (DBOS, queues, workflows) and its deploy migrations."""

import argparse
import asyncio
import os
import signal
import sys
import threading
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

import httpx2
import psycopg
from dbos import DBOS, DBOSConfig, StepOptions, WorkflowSerializationFormat
from meritum_core.checks.contracts import CatalogEntry, EvalRun
from meritum_core.corpus import CorpusSettings
from meritum_core.corpus.catalog import load_catalog
from meritum_core.jobs.constants import READINESS_KEY
from meritum_core.jobs.contracts import (
    APPLICATION_NAME,
    ARCHIVE_PAGE,
    CHECK,
    DEFAULT_QUEUE,
    DELETE_SUBJECT,
    ESCALATE_CLAIM,
    EVAL_RUN,
    PING,
    READINESS,
)
from meritum_core.shared.blobs import BlobSettings
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.database.adapters import apply_migrations
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings
from meritum_core.shared.llm import LlmSettings, build_llm

from meritum_worker import (
    checks,
    corpus,
    evidence,
    jobs,
    moderation,
    observability,
    security,
)
from meritum_worker.checks.factory import build_check_deps, build_check_runtime
from meritum_worker.corpus.adapters import apply_corpus_migrations, build_archive_deps


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
    blobs = BlobSettings() if security.BLOB_PROVIDER_ENV in os.environ else None
    return build_check_deps(LlmSettings(), DatabaseSettings(), blobs)


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


async def _escalate(payload: dict[str, Any]) -> dict[str, Any]:
    deps = check_deps().moderation
    if deps is None:  # build_check_deps always sets it
        msg = "moderation ports are not configured"
        raise RuntimeError(msg)
    output = await moderation.run_escalate_claim(payload, deps)
    return output.model_dump(mode="json")


@DBOS.workflow(
    name=ESCALATE_CLAIM.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def escalate_claim_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Hand one claim of a finished check to the moderators (ESCALATE_CLAIM).

    The backend waits for this workflow and announces the case it returns.

    Args:
        payload: the `EscalateClaimInput` JSON object.

    Returns:
        The `EscalateClaimOutput` JSON object.

    Features:
        US-MOD-03, US-MOD-06, F-24, ADR-03, ADR-22
    """
    return await DBOS.run_step_async({"retries_allowed": True}, _escalate, payload)


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


@DBOS.workflow(
    name=evidence.SANCTIONS_WORKFLOW,
    serialization_type=WorkflowSerializationFormat.PORTABLE,
)
def sanctions_refresh_workflow() -> int:
    """Refresh the local EU sanctions list copy; started by hand or a schedule.

    Returns:
        How many entries the new copy holds; 0 and nothing written when
        ``MERITUM_SANCTIONS_LIST_URL`` or ``MERITUM_SANCTIONS_LIST_PATH`` is unset.

    Features:
        US-ZRD-07, F-34
    """
    return sanctions_refresh_step()


@DBOS.step(retries_allowed=True)
def sanctions_refresh_step() -> int:
    """Download the list and replace the copy; an invalid download writes nothing.

    Returns:
        How many entries the copy holds.

    Features:
        US-ZRD-07, F-34
    """
    url = os.environ.get("MERITUM_SANCTIONS_LIST_URL", "")
    path = os.environ.get("MERITUM_SANCTIONS_LIST_PATH", "")
    if not url or not path:
        DBOS.logger.warning("sanctions refresh skipped: URL or PATH unset")
        return 0

    async def download() -> bytes:
        async with httpx2.AsyncClient(follow_redirects=True) as http:
            reply = await http.get(url)
            reply.raise_for_status()
            return reply.content

    return asyncio.run(evidence.refresh_sanctions(download, Path(path)))


@DBOS.workflow(
    name=corpus.IMPORT_WORKFLOW,
    serialization_type=WorkflowSerializationFormat.PORTABLE,
)
def organiser_import_workflow(path: str) -> dict[str, Any]:
    """Import one organiser's file (incidents or source list); started by hand.

    Args:
        path: The JSON or CSV file on the worker's disk.

    Returns:
        The ``ImportReport`` JSON; only ``disabled`` where ingestion is off.

    Features:
        US-KOR-02, US-ZRD-08, F-10, F-11, ADR-32
    """
    return organiser_import_step(path)


@DBOS.step(retries_allowed=True)
def organiser_import_step(path: str) -> dict[str, Any]:
    """Run ``corpus.import_organiser_file`` as one step; a rerun is idempotent.

    Args:
        path: The JSON or CSV file on the worker's disk.

    Returns:
        The ``ImportReport`` JSON.

    Features:
        US-KOR-02, F-10, F-11
    """
    report = asyncio.run(
        corpus.import_organiser_file(
            Path(path),
            corpus.build_organiser_file(),
            _euvs_copy(),
            build_embeddings(EmbeddingsSettings()),
            env=os.environ,
        )
    )
    if report.disabled:
        DBOS.logger.warning("organiser import off: corpus is not writable here")
    for record in report.skipped:
        DBOS.logger.warning(
            "organiser record %s skipped: %s (%s)",
            record.id,
            record.reason,
            record.detail,
        )
    return report.model_dump(mode="json")


async def readiness_report() -> dict[str, Any]:
    """Check this process's variables and providers (`observability.check_readiness`).

    Returns:
        The `ReadinessReport` JSON object; never raises for a missing key.

    Features:
        US-WDR-08, US-BEZ-03, F-30
    """
    async with httpx2.AsyncClient() as http:
        probes = observability.build_readiness_probes(os.environ, http)
        report = await observability.check_readiness(
            os.environ, probes, datetime.now(UTC)
        )
    return report.model_dump(mode="json")


@DBOS.workflow(
    name=READINESS.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def readiness_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Report missing variables and providers; also the READINESS_KEY event.

    Args:
        payload: the `ReadinessInput` JSON object.

    Returns:
        The `ReadinessReport` JSON object.

    Features:
        US-WDR-08, US-BEZ-03, F-30, ADR-03
    """
    READINESS.input.model_validate(payload)
    report = await DBOS.run_step_async({"retries_allowed": False}, readiness_report)
    await DBOS.run_step_async({"retries_allowed": True}, _announce_service, report)
    await DBOS.set_event_async(
        READINESS_KEY,
        report,
        serialization_type=WorkflowSerializationFormat.PORTABLE,
    )
    return report


async def _announce_service(report: dict[str, Any]) -> None:
    deps = check_deps()
    if deps.moderation is not None:
        await checks.notify_service_state(
            READINESS.output.model_validate(report),
            deps.moderation,
            deps.notifications,
            datetime.now(UTC),
        )


async def _announce_answers() -> int:
    deps = check_deps()
    if deps.moderation is None:
        return 0
    return await checks.notify_case_answers(
        deps.moderation, deps.notifications, datetime.now(UTC)
    )


@DBOS.workflow(name=moderation.ANSWER_NOTICE_WORKFLOW)
async def case_answers_workflow(_scheduled_at: datetime, _context: object) -> None:
    """Tell the askers of answered cases; started by the ANSWER_NOTICE_CRON schedule.

    Args:
        _scheduled_at: the schedule's time, unused.
        _context: the schedule's context, unused.

    Features:
        US-POW-04, F-26
    """
    sent = await DBOS.run_step_async({"retries_allowed": True}, _announce_answers)
    DBOS.logger.info("moderator_answer notifications saved: %s", sent)


def _eval_run_deps(corpus_version: str) -> observability.EvalRunDeps:
    root = Path.cwd()
    return observability.build_eval_run_deps(
        LlmSettings(),
        DatabaseSettings(),
        corpus_version,
        root / observability.DEFAULT_CASES_FILE,
    )


@DBOS.workflow(
    name=EVAL_RUN.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def eval_run_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Run the golden set or a staff file and store the EvalRun (EVAL_RUN).

    Starting, checking the cases and finishing are three steps, so a recovered
    run does not check the cases again once they are done.

    Args:
        payload: the `EvalRunInput` JSON object.

    Returns:
        The `EvalRunOutput` JSON object; the staff user gets eval_run_done.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-03
    """
    job = EVAL_RUN.input.model_validate(payload)
    deps = _eval_run_deps(job.corpus_version)

    async def start() -> str:
        return (await observability.start_eval_run(payload, deps)).model_dump_json()

    async def evaluate(running: str) -> str:
        run = EvalRun.model_validate_json(running)
        return (
            await observability.evaluate_eval_run(
                run, deps, dataset_blob_id=job.dataset_blob_id
            )
        ).model_dump_json()

    async def finish(done: str) -> dict[str, Any]:
        run = EvalRun.model_validate_json(done)
        output = await observability.finish_eval_run(run, deps)
        return output.model_dump(mode="json")

    running = await DBOS.run_step_async(
        {"name": "start", "retries_allowed": True}, start
    )
    done = await DBOS.run_step_async({"name": "evaluate"}, evaluate, running)
    return await DBOS.run_step_async(
        {"name": "finish", "retries_allowed": True}, finish, done
    )


@cache
def _archive_deps() -> corpus.ArchiveDeps:
    blobs = BlobSettings() if security.BLOB_PROVIDER_ENV in os.environ else None
    return build_archive_deps(DatabaseSettings(), blobs)


async def _archive(payload: dict[str, Any]) -> dict[str, Any]:
    return await corpus.run_archive_page(
        payload, _archive_deps(), now=datetime.now(UTC)
    )


@DBOS.workflow(
    name=ARCHIVE_PAGE.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def archive_page_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Archive one public page for the citizen who asked (ARCHIVE_PAGE).

    The backend enqueues it with ``archive_id`` as the workflow id and polls it.

    Args:
        payload: the ``ArchivePageInput`` JSON object.

    Returns:
        The ``ArchivePageOutput`` JSON object: the copy or the refusal.

    Features:
        US-KOR-07, F-38, ADR-03
    """
    return await DBOS.run_step_async({"retries_allowed": True}, _archive, payload)


def _retention_deps() -> security.RetentionDeps:
    blobs = BlobSettings() if security.BLOB_PROVIDER_ENV in os.environ else None
    documents = CorpusSettings() if corpus.ingestion_enabled(os.environ) else None
    return security.build_retention_deps(DatabaseSettings(), blobs, corpus=documents)


async def _erase(payload: dict[str, object]) -> int:
    return (await security.erase_subject(payload, _retention_deps())).deleted


@DBOS.workflow(
    name=DELETE_SUBJECT.name, serialization_type=WorkflowSerializationFormat.PORTABLE
)
async def delete_subject_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Erase one person (DELETE_SUBJECT); steps keep what they read out of history.

    A cancelled check stops at its next step, so a step saving its record may
    still finish after the first pass; the second pass, after ERASURE_SETTLE,
    deletes that record.

    Args:
        payload: the `DeleteSubjectInput` JSON object.

    Returns:
        The `DeleteSubjectOutput` JSON object.

    Features:
        US-BEZ-05, F-20, ADR-03
    """
    deleted = await DBOS.run_step_async({"retries_allowed": True}, _erase, payload)
    await DBOS.sleep_async(security.ERASURE_SETTLE.total_seconds())
    deleted += await DBOS.run_step_async({"retries_allowed": True}, _erase, payload)
    return DELETE_SUBJECT.output(deleted=deleted).model_dump()


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


async def _remove_for_publisher(payload: dict[str, Any]) -> dict[str, Any]:
    request = corpus.PublisherRemovalRequest.model_validate(payload)
    store = corpus.build_corpus_retention(CorpusSettings())
    removal = await security.remove_publisher_document(
        store, request, datetime.now(UTC)
    )
    if security.removal_is_late(removal):
        DBOS.logger.warning("publisher removal done after the 7-day deadline")
    return removal.model_dump(mode="json")


@DBOS.workflow(
    name=security.PUBLISHER_REMOVAL_WORKFLOW,
    serialization_type=WorkflowSerializationFormat.PORTABLE,
)
async def publisher_removal_workflow(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove a page on its publisher's request (within 7 days) and log it.

    An operator starts it with the ``PublisherRemovalRequest`` JSON object.

    Args:
        payload: the ``PublisherRemovalRequest`` JSON object.

    Returns:
        The ``PublisherRemoval`` ledger row as JSON.

    Features:
        US-KOR-05, F-10, ADR-13
    """
    return await DBOS.run_step_async(
        {"retries_allowed": True}, _remove_for_publisher, payload
    )


@cache
def _ingest_deps() -> corpus.IngestDeps:
    injection = security.build_detector(
        build_llm(LlmSettings()), security.InjectionGateSettings()
    )
    return corpus.build_ingest_deps(
        CorpusSettings(), build_embeddings(EmbeddingsSettings()), injection
    )


async def _plan(now: datetime) -> list[str]:
    if not corpus.ingestion_enabled(os.environ):
        return []
    due = await corpus.due_entries(load_catalog(), _ingest_deps().store, now=now)
    return [entry.model_dump_json() for entry in due]


async def _ingest(entry: CatalogEntry, now: datetime) -> str:
    report = await corpus.ingest_pages(entry, _ingest_deps(), now=now)
    return report.model_dump_json()  # failed pages with reasons: the run's record


@DBOS.workflow(name=corpus.INGEST_WORKFLOW)
async def corpus_ingest_workflow(scheduled: datetime, _context: object) -> None:
    """Ingest the due catalogue entries, one retried step per entry.

    The plan is a step too, so a recovered run fetches the same entries, and a
    retried entry fetches all of its pages again (unchanged ones cost nothing).

    Args:
        scheduled: When the schedule fired; every document's ``fetched_at``.
        _context: The schedule's context (unused).

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
    """
    for data in await DBOS.run_step_async({"name": corpus.PLAN_STEP}, _plan, scheduled):
        entry = CatalogEntry.model_validate_json(data)
        name = f"{corpus.INGEST_STEP_PREFIX}{entry.domain}"
        await DBOS.run_step_async(
            {"name": name, "retries_allowed": True}, _ingest, entry, scheduled
        )


async def _snapshot(scheduled: datetime) -> str:
    snapshot = await corpus.take_snapshot(_ingest_deps().store, scheduled=scheduled)
    return f"{snapshot.version} ({len(snapshot.manifest)} documents)"


@DBOS.workflow(name=corpus.SNAPSHOT_WORKFLOW)
async def corpus_snapshot_workflow(scheduled: datetime, _context: object) -> None:
    """Take the hourly ``corpus_version`` named after ``scheduled`` (ADR-19).

    Args:
        scheduled: When the schedule fired: 10:00 UTC gives ``2026-11-20T10:00Z``.
        _context: The schedule's context (unused).

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19, ADR-21
    """
    if corpus.ingestion_enabled(os.environ):
        options: StepOptions = {"name": corpus.SNAPSHOT_STEP, "retries_allowed": True}
        await DBOS.run_step_async(options, _snapshot, scheduled)


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
    DBOS.apply_schedules(
        [
            {
                "schedule_name": moderation.ANSWER_NOTICE_WORKFLOW,
                "workflow_fn": case_answers_workflow,
                "schedule": moderation.ANSWER_NOTICE_CRON,
            }
        ]
    )
    report = asyncio.run(readiness_report())
    observability.log_readiness(READINESS.output.model_validate(report), DBOS.logger)
    if corpus.ingestion_enabled(os.environ):
        DBOS.apply_schedules(
            [
                {
                    "schedule_name": corpus.INGEST_WORKFLOW,
                    "workflow_fn": corpus_ingest_workflow,
                    "schedule": corpus.INGEST_SCHEDULE,
                },
                {
                    "schedule_name": corpus.SNAPSHOT_WORKFLOW,
                    "workflow_fn": corpus_snapshot_workflow,
                    "schedule": corpus.SNAPSHOT_SCHEDULE,
                },
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
