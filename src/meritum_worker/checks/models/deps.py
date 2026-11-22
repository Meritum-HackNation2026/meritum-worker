"""The ports the `check` steps call.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, F-07, F-22
"""

from dataclasses import dataclass, field

from meritum_core.checks import CheckRecordRepository
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.checks.transcription import TranscriptionPort
from meritum_core.corpus import CorpusSearchPort, RerankerPort
from meritum_core.corpus.fetching import PageFetcherPort
from meritum_core.corpus.web_search import WebSearchPort
from meritum_core.notifications import NotificationRepository
from meritum_core.security.injection import InjectionDetectorPort
from meritum_core.security.pii import PiiGatePort
from meritum_core.shared.blobs import BlobStore
from meritum_core.shared.llm import LlmPort

from meritum_worker.corpus import FactCheckPort, FakeFactCheck, LivePagesPort
from meritum_worker.evidence import SanctionsList
from meritum_worker.moderation import ModerationDeps


@dataclass(frozen=True, slots=True)
class CheckDeps:
    """Ports the steps call; built once by `checks.factory`.

    Attributes:
        llm: the language model, from the core LLM factory.
        records: where the CheckRecord is saved.
        pages: the SSRF-safe page fetcher, from the core fetching factory.
        pii: the personal-data masking gate for pages, transcripts and web queries.
        blobs: the store holding uploaded recordings (ADR-31).
        transcriber: transcription over the same store (ADR-30).
        notifications: the inbox the end of a long check is announced in.
        web_search: live web search, limited to catalogue domains.
        injection: the detector pages found by web search are scanned with.
        catalog: the loaded source catalogue.
        corpus: hybrid search of the corpus snapshots, called in process (ADR-32).
        reranker: the gate passages pass before stance assessment (ADR-35).
        corpus_version: the snapshot checks search; NO_CORPUS_VERSION skips it.
        moderation: the ports of moderator cases; None skips the cases step.
        web_search_provider: the web search provider, the key of WEB_SEARCH_PRICES.
        fact_check: Google Fact Check Tools API, or the stub that finds nothing.
        live_pages: takes pages past quarantine into the corpus for the next
            snapshot; None where the worker may not write ``corpus``.
        sanctions: the local copy of the EU sanctions list; empty finds nothing.

    Features:
        US-SPR-01, US-SPR-02, US-SPR-04, US-SPR-07, US-SPR-11, US-OBS-01, US-OBS-07,
        US-POW-01, US-KOR-04, US-ZRD-07, F-06, F-08, F-09, F-12, F-13, F-22, F-34
    """

    llm: LlmPort
    records: CheckRecordRepository
    pages: PageFetcherPort
    pii: PiiGatePort
    blobs: BlobStore
    transcriber: TranscriptionPort
    notifications: NotificationRepository
    web_search: WebSearchPort
    injection: InjectionDetectorPort
    catalog: tuple[CatalogEntry, ...]
    corpus: CorpusSearchPort
    reranker: RerankerPort
    corpus_version: str
    moderation: ModerationDeps | None = None
    web_search_provider: str = "stub"
    fact_check: FactCheckPort = field(default_factory=FakeFactCheck)
    live_pages: LivePagesPort | None = None
    sanctions: SanctionsList = field(default_factory=SanctionsList)
