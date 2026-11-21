"""EUvsDisinfo items as the MCP server returns them and as the local copy keeps them.

Features:
    US-KOR-08, F-11
"""

from datetime import datetime
from typing import Literal

from meritum_core.checks.contracts import Source
from meritum_core.shared.embeddings import Vector
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class EuvsCase(BaseModel):
    """One disinformation case from the ``cases`` tool.

    Attributes:
        id: Case id in EUvsDisinfo.
        title: Case title.
        claim: The disinformation as summarised by EUvsDisinfo (source text: data).
        fact: The disproof ("fact") text.
        date: Case date as a Unix timestamp.
        links: Links to the disinformation (``linksToDisinformation``).
        url: Case page on euvsdisinfo.eu.

    Features:
        US-KOR-08, F-11
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    title: str
    claim: str
    fact: str
    date: int
    links: list[str] = Field(default=[], alias="linksToDisinformation")
    url: str

    # The server sends numeric ids; keys are strings.
    @classmethod
    def from_json(cls, item: dict[str, object]) -> EuvsCase:
        """Validate one item, accepting a numeric id.

        Args:
            item: One element of the tool result.

        Returns:
            The case.

        Features:
            US-KOR-08, F-11
        """
        return cls.model_validate({**item, "id": str(item.get("id"))})


class EuvsArticle(BaseModel):
    """One analytical article from the ``articles`` tool.

    Attributes:
        id: Article id in EUvsDisinfo.
        title: Article title.
        content: Article text, HTML already stripped by the server.
        date_gmt: Publication time (``dateGmt``).
        url: Article page on euvsdisinfo.eu.

    Features:
        US-KOR-08, F-11
    """

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    title: str
    content: str
    date_gmt: datetime | None = Field(default=None, alias="dateGmt")
    url: str

    @classmethod
    def from_json(cls, item: dict[str, object]) -> EuvsArticle:
        """Validate one item, accepting a numeric id.

        Args:
            item: One element of the tool result.

        Returns:
            The article.

        Features:
            US-KOR-08, F-11
        """
        return cls.model_validate({**item, "id": str(item.get("id"))})


class Entry(BaseModel):
    """A case or an article in the shape the local copy compares and stores.

    Attributes:
        key: ``case:<id>`` or ``article:<id>``, unique in the copy.
        kind: Case or article.
        title: Title.
        url: Page on euvsdisinfo.eu.
        published_at: Case date or article publication time.
        description: Case summary or article text; embedded for search.
        fact: The case's fact text; None for articles.
        domains: Domains the case links to as disinformation.

    Features:
        US-KOR-08, F-11
    """

    model_config = ConfigDict(frozen=True)

    key: str
    kind: Literal["case", "article"]
    title: str
    url: str
    published_at: AwareDatetime | None
    description: str
    fact: str | None = None
    domains: tuple[str, ...] = ()


class StoredEntry(BaseModel):
    """An entry in the local copy with its embeddings and its fact source.

    Attributes:
        entry: The entry as last fetched.
        description_vector: Multilingual embedding of the description.
        fact_vector: Embedding of the fact text; None for articles.
        source: The fact text as a citable source (``via = mcp``).
        deleted_at: When the entry vanished from EUvsDisinfo; None while live.

    Features:
        US-KOR-08, F-11
    """

    model_config = ConfigDict(frozen=True)

    entry: Entry
    description_vector: Vector
    fact_vector: Vector | None = None
    source: Source | None = None
    deleted_at: AwareDatetime | None = None


class SyncReport(BaseModel):
    """What one sync changed in the local copy.

    Attributes:
        added: New entries.
        updated: Entries whose content changed.
        deleted: Entries marked deleted in this run.

    Features:
        US-KOR-08, F-11
    """

    model_config = ConfigDict(frozen=True)

    added: int = 0
    updated: int = 0
    deleted: int = 0
