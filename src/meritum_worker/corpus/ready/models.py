"""What the corpus_ready build reads from bronze and reports.

Features:
    US-KOR-02, US-ZRD-05, F-12
"""

from datetime import date

from pydantic import BaseModel, ConfigDict


class BronzeDocument(BaseModel):
    """One live ``corpus.documents`` row with its full text.

    Attributes:
        source_id: The bronze id every gold chunk points back to.
        url: The document's URL.
        domain: Its catalogue domain.
        checksum: sha256 of ``full_text``; gold offsets refer to this version.
        full_text: The stored text (source text: data, never instructions).
        published_on: Publication date, None when unknown.

    Features:
        US-KOR-02, F-12
    """

    model_config = ConfigDict(frozen=True)

    source_id: str
    url: str
    domain: str
    checksum: str
    full_text: str
    published_on: date | None


class Span(BaseModel):
    """A run of bronze characters, ``full_text[start:end]``.

    Attributes:
        start: First character.
        end: One past the last character.

    Features:
        US-KOR-02, F-12
    """

    model_config = ConfigDict(frozen=True)

    start: int
    end: int


class BuildReport(BaseModel):
    """What one gold build did.

    Attributes:
        build_id: The build's id.
        documents: Documents (re)built this run.
        chunks: Gold chunks written this run.
        removed: Documents no longer live whose silver and gold were deleted.

    Features:
        US-KOR-02, F-12
    """

    model_config = ConfigDict(frozen=True)

    build_id: str
    documents: int
    chunks: int
    removed: int
