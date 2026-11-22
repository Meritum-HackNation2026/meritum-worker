"""Addresses and limits of the public APIs in the source catalogue (``ingest: api``).

Features:
    US-KOR-02, F-10, F-12, ADR-32
"""

from typing import Final

API_METHOD: Final = "api"
"""Catalogue ``ingest`` value of an entry read from a public JSON API."""

API_RECORD_CONTENT_TYPE: Final = "application/json"
"""``content_type`` of a document made from one API record."""

JSON_MEDIA_SUFFIX: Final = "+json"
"""Suffix of JSON media types such as ``application/vnd.api+json`` (dane.gov.pl)."""

JSON_RELABELLED_TYPE: Final = "text/plain"
"""What a JSON answer is labelled for core's fetcher, which reads plain text."""

JSON_DEFAULT_CHARSET: Final = "charset=utf-8"
"""Charset of a JSON answer that names none (RFC 8259)."""

MAX_RECORDS_PER_LISTING: Final = 2000
"""Most records kept from one API answer; a year of Dziennik Ustaw is about 1600."""

INVALID_API_RESPONSE: Final = "invalid_api_response"
"""Failure reason of an API answer that is not the JSON its parser expects."""

API_NOT_SUPPORTED: Final = "api_not_supported"
"""Failure reason of an API entry with no parser, or a run without the API fetcher."""

SEJM_ELI_ACTS_URL: Final = "https://api.sejm.gov.pl/eli/acts/DU/{year}"
"""ELI API of the Sejm: every act of Dziennik Ustaw published in one year."""

SEJM_ELI_ACT_URL: Final = "https://api.sejm.gov.pl/eli/acts/{eli}"
"""One act in the ELI API, by its ELI (``DU/2026/1530``)."""

NBP_TABLES_URL: Final = (
    "https://api.nbp.pl/api/exchangerates/tables/A/last/10/?format=json"
)
"""The last ten tables A of NBP's average exchange rates."""

NBP_TABLE_URL: Final = "https://api.nbp.pl/api/exchangerates/tables/A/{day}/"
"""Table A of one day."""

NBP_GOLD_URL: Final = "https://api.nbp.pl/api/cenyzlota/last/30/?format=json"
"""NBP's gold prices of the last 30 publications."""

NBP_GOLD_DAY_URL: Final = "https://api.nbp.pl/api/cenyzlota/{day}/"
"""NBP's gold price of one day."""

DANE_DATASETS_URL: Final = (
    "https://api.dane.gov.pl/1.4/datasets?page=1&per_page=100&sort=-modified"
)
"""The 100 most recently changed datasets of dane.gov.pl (JSON:API)."""

DANE_DATASET_URL: Final = "https://dane.gov.pl/pl/dataset/{id},{slug}"
"""Page of one dataset on dane.gov.pl."""

BDL_SUBJECTS_URL: Final = (
    "https://bdl.stat.gov.pl/api/v1/subjects?format=json&lang=pl&page-size=100"
)
"""Top-level subject areas of GUS's Bank Danych Lokalnych."""

BDL_SUBJECT_URL: Final = "https://bdl.stat.gov.pl/api/v1/subjects/{id}"
"""One subject area of Bank Danych Lokalnych."""

EUROSTAT_DATA_URL: Final = (
    "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/"
)
"""Eurostat's dissemination API; a dataset code and filters follow (JSON-stat 2.0)."""

EUROSTAT_QUERIES: Final = (
    "prc_hicp_manr?format=JSON&lang=EN&geo=PL&coicop=CP00&lastTimePeriod=12",
    (
        "une_rt_m?format=JSON&lang=EN&geo=PL&s_adj=SA&age=TOTAL&sex=T&unit=PC_ACT"
        "&lastTimePeriod=12"
    ),
)
"""Polish HICP inflation and unemployment, the last 12 months; every dimension but
time is filtered to one value, so the parser reads one series."""

EUROSTAT_TIME: Final = "time"
"""JSON-stat dimension of the periods."""

EUROSTAT_GEO: Final = "geo"
"""JSON-stat dimension of the country."""

HTML_TAG: Final = r"<[^>]+>"
"""An HTML tag in a dataset description; dropped from the text."""
