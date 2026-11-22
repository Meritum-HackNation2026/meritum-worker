"""Cassettes: providers' answers recorded once, replayed without keys or network.

A cassette holds full page texts, so it never leaves the team: the public
bundle carries only their checksums (ADR-27).

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-27, ADR-28
"""

from enum import StrEnum
from pathlib import Path

from meritum_core.corpus import Passage
from meritum_core.corpus.fetching import FetchedPage, FetchFailureReason
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.injection import InjectionSpan
from meritum_core.security.pii import MaskedText
from meritum_core.shared.llm import LlmUsage
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue

from meritum_worker.observability.constants import NO_CORPUS_VERSION


class EvalMode(StrEnum):
    """How an evaluation run reaches the model and page providers.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    LIVE = "live"
    """Call the providers; nothing is recorded."""
    RECORD = "record"
    """Call the providers and record every answer in the cassette."""
    REPLAY = "replay"
    """Answer from the cassette only: no keys, no network."""


class LlmTake(BaseModel):
    """One recorded model call: the answer with its usage, or the failure.

    Attributes:
        output: The validated answer as JSON; None when the call failed.
        usage: Provider, model and tokens of the call; None when it failed.
        error: The provider failure's message; None when the call answered.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    output: JsonValue = None
    usage: LlmUsage | None = None
    error: str | None = None


class PageTake(BaseModel):
    """One recorded page fetch: the page, or why it failed, and when.

    Attributes:
        page: The fetched page with its full text; None when the fetch failed.
        reason: Why the fetch failed; None when it succeeded.
        fetched_at: When the page was fetched.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-27, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    page: FetchedPage | None = None
    reason: FetchFailureReason | None = None
    fetched_at: AwareDatetime


class PiiTake(BaseModel):
    """One recorded answer of the masking gate; never the original text.

    Attributes:
        masked: The masked text; None when the gate failed.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-13, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    masked: MaskedText | None = None


class SearchTake(BaseModel):
    """One recorded web search: the catalogue candidates, or the failure type.

    Attributes:
        candidates: The candidates in the provider's order.
        failure: Name of the ``WebSearchError`` raised; None when it answered.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    candidates: tuple[WebSearchCandidate, ...] = ()
    failure: str | None = None


class ScanTake(BaseModel):
    """One recorded injection scan: the spans found; never the scanned text.

    Attributes:
        spans: Detected instructions; None when the classifier failed.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-23, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    spans: tuple[InjectionSpan, ...] | None = None


class CorpusTake(BaseModel):
    """One recorded corpus search: the passages, or the failure type.

    Attributes:
        passages: The passages found, best first.
        failure: Name of the corpus or embeddings error; None when it answered.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-19, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    passages: tuple[Passage, ...] = ()
    failure: str | None = None


class RerankTake(BaseModel):
    """One recorded reranking: passage ids with relevance, best first.

    Attributes:
        ranked: ``(passage_id, relevance)`` pairs; None when the provider failed.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    model_config = ConfigDict(frozen=True)

    ranked: tuple[tuple[str, float], ...] | None = None


class Cassette(BaseModel):
    """Every recorded answer of one run, by request key, in call order.

    Attributes:
        corpus_version: The snapshot the run was pinned to.
        llm: Model calls by prompt and output type.
        pages: Page fetches by URL and purpose.
        pii: Masking gate answers by a hash of the text.
        web_search: Web searches by limit and masked query.
        injection: Injection scans by a hash of the text.
        corpus: Corpus searches by query, date, snapshot and limit.
        rerank: Rerankings by claim, passage ids and limit.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    corpus_version: str = NO_CORPUS_VERSION
    llm: dict[str, list[LlmTake | None]] = Field(default_factory=dict)
    pages: dict[str, list[PageTake | None]] = Field(default_factory=dict)
    pii: dict[str, list[PiiTake | None]] = Field(default_factory=dict)
    web_search: dict[str, list[SearchTake | None]] = Field(default_factory=dict)
    injection: dict[str, list[ScanTake | None]] = Field(default_factory=dict)
    corpus: dict[str, list[CorpusTake | None]] = Field(default_factory=dict)
    rerank: dict[str, list[RerankTake | None]] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> Cassette:
        """Read a cassette file.

        Args:
            path: The file ``save`` wrote.

        Returns:
            The cassette.

        Features:
            US-OBS-07, US-OBS-04, F-27
        """
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> None:
        """Write the cassette as JSON, creating its folder.

        Args:
            path: Where to write it.

        Features:
            US-OBS-07, US-OBS-04, F-27
        """
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.model_dump_json(indent=2) + "\n", encoding="utf-8")
