"""Catalogue entries read from public JSON APIs: listings, parsers and ingestion.

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from .acts import act_body, act_parts
from .ingest import ingest_api_entry
from .listings import ApiListing, api_listings, parse_listing
from .records import ApiRecord, InvalidApiResponseError
from .settings import LegalActsSettings

__all__ = [
    "ApiListing",
    "ApiRecord",
    "InvalidApiResponseError",
    "LegalActsSettings",
    "act_body",
    "act_parts",
    "api_listings",
    "ingest_api_entry",
    "parse_listing",
]
