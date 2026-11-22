"""Which API requests each catalogue entry makes, and parsing one answer.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial

from meritum_core.checks.contracts import CatalogEntry

from meritum_worker.corpus.catalog_api import parsers
from meritum_worker.corpus.catalog_api.constants import (
    BDL_SUBJECTS_URL,
    DANE_DATASETS_URL,
    EUROSTAT_DATA_URL,
    EUROSTAT_QUERIES,
    MAX_RECORDS_PER_LISTING,
    NBP_GOLD_URL,
    NBP_TABLES_URL,
    SEJM_ELI_ACTS_URL,
)
from meritum_worker.corpus.catalog_api.records import ApiRecord, InvalidApiResponseError

type Parser = Callable[[str], list[ApiRecord]]


@dataclass(frozen=True)
class ApiListing:
    """One API request of an entry and the parser of its answer.

    Attributes:
        url: The request, fetched like a page (SSRF guard, robots.txt).
        parse: Turns the raw JSON answer into records.

    Features:
        US-KOR-02, F-10, F-12, ADR-32
    """

    url: str
    parse: Parser


def api_listings(entry: CatalogEntry, now: datetime) -> list[ApiListing]:
    """Return the requests of one ``ingest: api`` entry.

    Args:
        entry: A catalogue entry.
        now: When the run starts; the Sejm listing reads its year.

    Returns:
        The requests; empty for an API with no parser yet.

    Features:
        US-KOR-02, F-10, F-12, ADR-32
    """
    eurostat = [
        ApiListing(url, partial(parsers.eurostat_series, url))
        for url in (f"{EUROSTAT_DATA_URL}{query}" for query in EUROSTAT_QUERIES)
    ]
    listings = {
        "api.sejm.gov.pl": [
            ApiListing(SEJM_ELI_ACTS_URL.format(year=now.year), parsers.sejm_acts)
        ],
        "api.nbp.pl": [
            ApiListing(NBP_TABLES_URL, parsers.nbp_tables),
            ApiListing(NBP_GOLD_URL, parsers.nbp_gold),
        ],
        "dane.gov.pl": [ApiListing(DANE_DATASETS_URL, parsers.dane_datasets)],
        "bdl.stat.gov.pl": [ApiListing(BDL_SUBJECTS_URL, parsers.bdl_subjects)],
        "ec.europa.eu/eurostat": eurostat,
    }
    return listings.get(entry.domain, [])


def parse_listing(listing: ApiListing, text: str) -> list[ApiRecord]:
    """Parse one API answer into records with text.

    Args:
        listing: The request the answer belongs to.
        text: The raw JSON, untrusted.

    Returns:
        At most ``MAX_RECORDS_PER_LISTING`` records, those without text dropped.

    Raises:
        InvalidApiResponseError: The answer is not JSON of the expected shape.

    Features:
        US-KOR-02, F-10, F-12, ADR-12
    """
    try:
        records = listing.parse(text)
    except (KeyError, IndexError, ValueError) as error:  # ValidationError included
        raise InvalidApiResponseError(listing.url) from error
    return [r for r in records if r.text.strip()][:MAX_RECORDS_PER_LISTING]
