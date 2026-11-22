"""Catalogue documents, their passages and corpus snapshots as the worker writes them.

Features:
    US-KOR-02, US-KOR-03, US-KOR-05, F-10, F-12, F-13, ADR-19
"""

from datetime import date

from meritum_core.checks.contracts import SourceVia
from meritum_core.shared.embeddings import Vector
from pydantic import AwareDatetime, BaseModel, ConfigDict


class DocumentMeta(BaseModel):
    """What the corpus keeps about a fetched page besides its text.

    Retention (worker#77) clears the full text 90 days after ``fetched_at`` and
    keeps this metadata.

    Attributes:
        source_id: Stable id of the page, shared by its passages.
        url: The URL the page was fetched from.
        domain: Its catalogue domain.
        publisher_id: Publisher id from the catalogue entry.
        license: Licence from the catalogue entry.
        published_on: Publication date, None when unknown.
        fetched_at: Last fetch; a refetch restarts the retention period.
        checksum: sha256 of the full text.
        via: How the page came in: ``rss`` from an RSS or Atom feed,
            ``web_search`` from live search, ``corpus`` for every other way.

    Features:
        US-KOR-02, US-KOR-03, US-KOR-05, F-10, F-12, F-13
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    url: str
    domain: str
    publisher_id: str
    license: str
    published_on: date | None = None
    fetched_at: AwareDatetime
    checksum: str
    via: SourceVia = "corpus"


class Document(DocumentMeta):
    """A fetched page with its full text, for the system only (search, re-chunking).

    Attributes:
        full_text: The page's main text (untrusted data); users see passages only.

    Features:
        US-KOR-05, F-12
    """

    full_text: str


class DocumentPassage(BaseModel):
    """One embedded passage of a document, stored in ``corpus.passages``.

    Attributes:
        passage_id: Unique per document text and fetch, so old snapshots keep theirs.
        text: At most ``CHUNK_MAX_CHARS`` characters of the document.
        embedding: Multilingual embedding of the text.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """

    model_config = ConfigDict(frozen=True)

    passage_id: str
    text: str
    embedding: Vector


class ManifestEntry(BaseModel):
    """One document as a snapshot saw it.

    Attributes:
        source_id: The document.
        checksum: sha256 of its text at snapshot time.
        fetched_at: Its last fetch at snapshot time.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    checksum: str
    fetched_at: AwareDatetime


class CorpusSnapshot(BaseModel):
    """A ``corpus_version``: what checks pinned to it search, so they replay.

    Attributes:
        version: The scheduled time, e.g. ``2026-11-20T10:00Z``.
        taken_at: When the store took it; passages added later stay out.
        manifest: Every live document, ordered by source id.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12, ADR-19
    """

    model_config = ConfigDict(frozen=True)

    version: str
    taken_at: AwareDatetime
    manifest: tuple[ManifestEntry, ...]


class IngestFailure(BaseModel):
    """A page the run could not add; the run goes on.

    Attributes:
        domain: Catalogue domain.
        url: The page.
        reason: A ``FetchFailureReason`` code, ``tdm_reserved``, ``empty_text``
            or ``feed_unreadable``.
        at: When the run that failed started; None outside a run.

    Features:
        US-KOR-02, US-KOR-03, US-KOR-05, F-10, F-12, F-13
    """

    model_config = ConfigDict(frozen=True)

    domain: str
    url: str
    reason: str
    at: AwareDatetime | None = None


class DiscoveredPage(BaseModel):
    """A page an entry's discovery found, with the date its feed gives.

    Attributes:
        url: Absolute http(s) URL of the page.
        published_on: Publication date from the feed or sitemap, None if unknown.
        via: ``rss`` when an RSS or Atom feed listed it, else ``corpus``.

    Features:
        US-KOR-03, F-13
    """

    model_config = ConfigDict(frozen=True)

    url: str
    published_on: date | None = None
    via: SourceVia = "corpus"


class IngestReport(BaseModel):
    """What one ingestion run changed, kept as the workflow's output.

    Attributes:
        added: New documents.
        updated: Documents whose text changed (new passages, old ones retired).
        unchanged: Refetched documents with the same text (only ``fetched_at`` moves).
        failures: Pages that failed, with the reason.

    Features:
        US-KOR-02, US-KOR-05, F-10, F-12
    """

    model_config = ConfigDict(frozen=True)

    added: int = 0
    updated: int = 0
    unchanged: int = 0
    failures: tuple[IngestFailure, ...] = ()

    def __add__(self, other: IngestReport) -> IngestReport:
        """Sum two reports, e.g. of two catalogue entries.

        Args:
            other: The other report.

        Returns:
            The counts summed and the failures joined.
        """
        return IngestReport(
            added=self.added + other.added,
            updated=self.updated + other.updated,
            unchanged=self.unchanged + other.unchanged,
            failures=self.failures + other.failures,
        )


class LegalActs(BaseModel):
    """Legal acts the ``api.sejm.gov.pl`` entry reads with their full text.

    Attributes:
        acts: ELIs always read (``DU/1997/483``).
        search_limit: Consolidated texts in force read from the ELI search.

    Features:
        US-KOR-02, US-ZRD-05, F-10, F-12
    """

    model_config = ConfigDict(frozen=True)

    acts: tuple[str, ...] = ()
    search_limit: int = 0
