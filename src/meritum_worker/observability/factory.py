"""Builds the ports of an evaluation run and the probes of the readiness check.

Features:
    US-OBS-04, US-OBS-05, US-OBS-07, F-27, ADR-28, US-WDR-08, US-BEZ-03, F-30
"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from httpx2 import AsyncClient
from meritum_core.observability import build_app_repositories
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker import corpus
from meritum_worker.checks import CheckDeps
from meritum_worker.checks.factory import build_check_deps
from meritum_worker.observability.adapters import (
    CassetteCorpus,
    CassetteInjection,
    CassetteLlm,
    CassettePages,
    CassettePii,
    CassetteReranker,
    CassetteWebSearch,
    FileCaseSets,
    PostgresEvalRuns,
)
from meritum_worker.observability.cassette import Cassette
from meritum_worker.observability.constants import EUVSDISINFO_PROBE
from meritum_worker.observability.eval_run import EvalRunDeps
from meritum_worker.observability.fakes import InMemoryEvalRuns
from meritum_worker.observability.models import GoldenCase
from meritum_worker.observability.ports import EvalRunRepository
from meritum_worker.observability.readiness import Probe
from meritum_worker.observability.runner import DepsFor


def build_eval_deps(
    settings: LlmSettings,
    corpus_version: str | None = None,
    recorder: Cassette | None = None,
) -> DepsFor:
    """Ports on the model from ``MERITUM_LLM_*`` and in-memory records.

    Records stay in memory, so a run never writes to the app database. A case
    with ``fault: llm`` gets a stub model without answers, which fails like
    an unavailable provider.

    Args:
        settings: The model to evaluate.
        corpus_version: The snapshot every check searches; None keeps the one
            from ``MERITUM_RESEARCH_*`` settings.
        recorder: The cassette every model answer, fetched page and the
            pinned snapshot are recorded in; None records nothing.

    Returns:
        The ports per case.

    Features:
        US-OBS-04, US-OBS-05, US-OBS-07, F-27, ADR-28
    """
    deps = _base(settings)
    if corpus_version is not None:
        deps = replace(deps, corpus_version=corpus_version)
    if recorder is not None:
        recorder.corpus_version = deps.corpus_version
        deps = _on_cassette(deps, recorder, record=True)
    return _with_faults(deps)


def build_replay_deps(cassette: Cassette) -> DepsFor:
    """Ports that answer from ``cassette`` only: no provider keys, no network.

    Args:
        cassette: A cassette ``build_eval_deps`` recorded; its snapshot is pinned.

    Returns:
        The ports per case.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """
    return _with_faults(_on_cassette(_base(_no_answers()), cassette, record=False))


def _base(settings: LlmSettings) -> CheckDeps:
    # An evaluation opens no moderator cases: it reads no DBOS history either.
    deps = build_check_deps(
        settings, DatabaseSettings(provider=DatabaseProvider.MEMORY)
    )
    return replace(deps, moderation=None)


def _on_cassette(deps: CheckDeps, cassette: Cassette, *, record: bool) -> CheckDeps:
    return replace(
        deps,
        llm=CassetteLlm(cassette, deps.llm if record else None),
        pages=CassettePages(cassette, deps.pages if record else None),
        pii=CassettePii(cassette, deps.pii if record else None),
        web_search=CassetteWebSearch(cassette, deps.web_search if record else None),
        injection=CassetteInjection(cassette, deps.injection if record else None),
        corpus=CassetteCorpus(cassette, deps.corpus if record else None),
        reranker=CassetteReranker(cassette, deps.reranker if record else None),
        corpus_version=cassette.corpus_version,
    )


def build_eval_run_deps(
    settings: LlmSettings,
    database: DatabaseSettings,
    corpus_version: str,
    golden: Path,
    uploads: Path,
) -> EvalRunDeps:
    """Ports of the `eval_run` workflow: the model, the app database and the files.

    Args:
        settings: The model to evaluate, usually ``LlmSettings()``.
        database: Where runs and notifications are stored; PostgreSQL on dev and
            prd, in memory by default.
        corpus_version: The snapshot every check of the run searches.
        golden: The golden set's JSON file.
        uploads: The directory of uploaded case files.

    Returns:
        The workflow's ports.

    Features:
        US-OBS-06, F-28, ADR-28
    """
    runs: EvalRunRepository = InMemoryEvalRuns()
    if database.provider is DatabaseProvider.POSTGRES and database.url is not None:
        runs = PostgresEvalRuns(database.url.get_secret_value())
    return EvalRunDeps(
        runs=runs,
        case_sets=FileCaseSets(golden, uploads),
        deps_for=build_eval_deps(settings, corpus_version),
        notifications=build_app_repositories(database).notifications,
    )


def _with_faults(deps: CheckDeps) -> DepsFor:
    broken = replace(deps, llm=build_llm(_no_answers()))

    def deps_for(case: GoldenCase) -> CheckDeps:
        return broken if case.fault == "llm" else deps

    return deps_for


def build_readiness_probes(
    env: Mapping[str, str], http_client: AsyncClient
) -> dict[str, Probe]:
    """Probes of the optional providers; a free call each.

    Fact Check API, web search and transcription get probes with their ports
    (worker#43 and later); the model is checked by its variables only, since
    every call to it is paid.

    Args:
        env: The worker's environment, usually ``os.environ``.
        http_client: HTTP client of the probes; the caller closes it.

    Returns:
        Provider name to probe; without a token the EUvsDisinfo probe fails,
        so the optional provider is reported unavailable.

    Features:
        US-WDR-08, US-BEZ-03, F-30
    """

    async def euvsdisinfo() -> bool:
        # Without the token this raises MissingTokenError: unavailable, not missing env.
        client = corpus.build_euvsdisinfo_client(env, http_client)
        await client.cases(limit=1, offset=0)
        return True

    return {EUVSDISINFO_PROBE: euvsdisinfo}


def _no_answers() -> LlmSettings:
    # Explicit None: the environment's stub fixtures must not reach this model.
    return LlmSettings(provider=LlmProvider.STUB, stub_fixtures=None)
