"""One record of a public API, stored as one corpus document.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from dataclasses import dataclass
from datetime import date

from meritum_core.corpus.fetching import FetchedPage

from meritum_worker.corpus.catalog_api.constants import API_RECORD_CONTENT_TYPE


class InvalidApiResponseError(ValueError):
    """An API answered something other than the JSON its parser expects.

    Features:
        US-KOR-02, F-10, F-12
    """


@dataclass(frozen=True)
class ApiRecord:
    """One record (an act, a rate table, a dataset) as untrusted text.

    Attributes:
        url: The record's own address; the document's ``source_id`` hashes it.
        text: The record's facts in sentences, written from the API's fields.
        published_at: When the publisher released the record, if the API says.
        wants_text: The record is a legal act whose full text is fetched too.
        text_url: Where that full text is; None when the API offers none.

    Features:
        US-KOR-02, F-10, F-12, ADR-12
    """

    url: str
    text: str
    published_at: date | None = None
    wants_text: bool = False
    text_url: str | None = None

    def page(self) -> FetchedPage:
        """The record as a fetched page, the way ``store_page`` takes it.

        Returns:
            The page; its text stays untrusted data (ADR-12).
        """
        return FetchedPage(
            url=self.url,
            content_type=API_RECORD_CONTENT_TYPE,
            untrusted_text=self.text,
            published_at=self.published_at,
        )
