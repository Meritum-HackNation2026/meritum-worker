"""Publisher removal requests and the ledger rows the corpus keeps of them.

Features:
    US-KOR-05, F-10, ADR-13
"""

from datetime import datetime
from typing import Annotated, Protocol

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator


class PublisherRemovalRequest(BaseModel):
    """A publisher's request to take one of its pages out of the corpus.

    Attributes:
        url: The page, as the corpus stores it.
        publisher_id: The publisher asking; only its own documents go.
        requested_at: When the request arrived; the 7-day deadline counts from it.

    Features:
        US-KOR-05, F-10
    """

    model_config = ConfigDict(frozen=True)

    url: str
    publisher_id: str
    requested_at: AwareDatetime

    @field_validator("url")
    @classmethod
    def _http_url(cls, url: str) -> str:
        if not url.startswith(("https://", "http://")):
            msg = "url must be an http(s) URL"
            raise ValueError(msg)
        return url


class PublisherRemoval(PublisherRemovalRequest):
    """One done publisher request, kept in the ledger ``corpus.publisher_removals``.

    Attributes:
        removed_at: When the documents, their text and passages were deleted.
        documents: How many documents went; 0 when the corpus had none of theirs.

    Features:
        US-KOR-05, F-10
    """

    removed_at: AwareDatetime
    documents: Annotated[int, Field(ge=0)]


class CorpusRetentionPort(Protocol):
    """Clears expired full texts and removes pages on their publisher's request.

    Features:
        US-KOR-05, F-10, ADR-13
    """

    async def full_text(self, source_id: str) -> str | None:
        """Return a live document's full text.

        Args:
            source_id: The document.

        Returns:
            The text, None when retention cleared it or there is no such document.
        """
        ...

    async def clear_full_texts(self, *, fetched_before: datetime, limit: int) -> int:
        """Clear the full text of documents last fetched before ``fetched_before``.

        Metadata, passages and snapshots stay; a later refetch stores the text again.

        Args:
            fetched_before: The retention cutoff.
            limit: The most documents cleared in one call.

        Returns:
            How many were cleared; 0 once none is left.
        """
        ...

    async def remove_for_publisher(
        self, request: PublisherRemovalRequest, removed_at: datetime
    ) -> PublisherRemoval:
        """Delete the publisher's documents at ``request.url`` and log the removal.

        The documents, their text and passages (retired ones included) go; the
        ledger row is written in the same transaction. Old snapshot manifests keep
        only the source id and checksum.

        Args:
            request: The publisher's request.
            removed_at: When the removal runs.

        Returns:
            The ledger row, with how many documents were deleted.
        """
        ...

    async def removals(self) -> list[PublisherRemoval]:
        """Return the ledger of publisher removals, oldest first.

        Returns:
            Every removal recorded.
        """
        ...
