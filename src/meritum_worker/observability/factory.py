"""Builds the ports of an evaluation run and the probes of the readiness check.

Features:
    US-OBS-04, US-OBS-05, US-OBS-07, F-27, ADR-28, US-WDR-08, US-BEZ-03, F-30
"""

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

from httpx2 import AsyncClient
from meritum_core.observability import build_app_repositories
from meritum_core.shared.blobs import (
    BlobProvider,
    BlobSettings,
    BlobStore,
    build_blob_store,
)
from meritum_core.shared.database import DatabaseProvider, DatabaseSettings
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker import corpus
from meritum_worker.checks import CheckDeps
from meritum_worker.checks.factory import build_check_deps
from meritum_worker.corpus.adapters import GoogleFactCheck
from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_ENV_PREFIX,
    FACT_CHECK_LANGUAGE,
)
from meritum_worker.observability.adapters import (
    ApiChecks,
    BlobCaseSets,
    CassetteCorpus,
    CassetteInjection,
    CassetteLlm,
    CassettePages,
    CassettePii,
    CassetteReranker,
    CassetteWebSearch,
    PostgresEvalRuns,
)
from meritum_worker.observability.cassette import Cassette
from meritum_worker.observability.constants import (
    EUVSDISINFO_PROBE,
    FACT_CHECK_PROBE,
    FACT_CHECK_PROBE_QUERY,
)
from meritum_worker.observability.eval_run import EvalRunDeps
from meritum_worker.observability.fakes import InMemoryEvalRuns
from meritum_worker.observability.models import GoldenCase
from meritum_worker.observability.ports import EvalCaseSets, EvalRunRepository
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


def build_api_checks(base_url: str, *, fresh: bool = False) -> ApiChecks:
    """Checks through a deployed API, e.g. dev with its real providers.

    Args:
        base_url: The API's origin.
        fresh: Make the API's result cache miss with an invisible tag.

    Returns:
        The adapter whose ``check`` runs one case; close it with ``aclose``.

    Features:
        US-OBS-04, US-OBS-05, F-27, ADR-28
    """
    return ApiChecks(base_url, fresh=fresh)


def build_case_sets(golden: Path, blobs: BlobStore) -> EvalCaseSets:
    """The golden set from disk and staff uploads from the blob store.

    Args:
        golden: The golden set's JSON file.
        blobs: Where the backend stored uploaded case files.

    Returns:
        The case-set port of the `eval_run` workflow.

    Features:
        US-OBS-06, US-POW-05, F-28, ADR-31
    """
    return BlobCaseSets(golden, blobs)


def build_eval_run_deps(
    settings: LlmSettings,
    database: DatabaseSettings,
    corpus_version: str,
    golden: Path,
    blobs: BlobStore | None = None,
) -> EvalRunDeps:
    """Ports of the `eval_run` workflow: the model, the app database and blobs.

    Args:
        settings: The model to evaluate, usually ``LlmSettings()``.
        database: Where runs and notifications are stored; PostgreSQL on dev and
            prd, in memory by default.
        corpus_version: The snapshot every check of the run searches.
        golden: The golden set's JSON file.
        blobs: Where staff uploads are stored; ``MERITUM_BLOB_*`` when None.

    Returns:
        The workflow's ports.

    Features:
        US-OBS-06, F-28, ADR-28, ADR-31
    """
    runs: EvalRunRepository = InMemoryEvalRuns()
    if database.provider is DatabaseProvider.POSTGRES and database.url is not None:
        runs = PostgresEvalRuns(database.url.get_secret_value())
    store = blobs or build_blob_store(BlobSettings(provider=BlobProvider.MEMORY))
    return EvalRunDeps(
        runs=runs,
        case_sets=build_case_sets(golden, store),
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

    The Fact Check API is probed with one search when ``MERITUM_FACT_CHECK_PROVIDER``
    is ``google``; web search and transcription get probes with their ports
    (later); the model is checked by its variables only, since
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

    probes: dict[str, Probe] = {EUVSDISINFO_PROBE: euvsdisinfo}
    prefix = FACT_CHECK_ENV_PREFIX
    if env.get(f"{prefix}PROVIDER", "").lower() == corpus.FactCheckProvider.GOOGLE:

        async def fact_check() -> bool:
            # An empty key raises FactCheckUnavailableError: degraded, not missing env.
            port = GoogleFactCheck(env.get(f"{prefix}API_KEY", ""), http_client)
            await port.search(FACT_CHECK_PROBE_QUERY, language=FACT_CHECK_LANGUAGE)
            return True

        probes[FACT_CHECK_PROBE] = fact_check
    return probes


def _no_answers() -> LlmSettings:
    # Explicit None: the environment's stub fixtures must not reach this model.
    return LlmSettings(provider=LlmProvider.STUB, stub_fixtures=None)
