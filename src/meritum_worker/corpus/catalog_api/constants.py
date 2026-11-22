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

NBP_ATTEMPTS: Final = 3
"""Requests per NBP listing while it answers ``not_found``. The paths are the ones
in NBP's documentation (api.nbp.pl); one of NBP's servers answers every request
with IIS's 404 page, and its load balancer sends about one request in three there
(checked 2026-11-22, worker#220)."""

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

SEJM_ELI_PDF_URL: Final = "https://api.sejm.gov.pl/eli/acts/{eli}/text.pdf"
"""The act's text as published in the journal (``O``), in PDF."""

SEJM_ELI_FILE_URL: Final = "https://api.sejm.gov.pl/eli/acts/{eli}/text/{kind}/{name}"
"""One named text file of an act, such as the consolidated text ``U``."""

SEJM_IN_FORCE: Final = "IN_FORCE"
"""ELI ``inForce`` of an act in force."""

SEJM_CONSOLIDATED_TEXT: Final = "U"
"""``texts[].type`` of the Sejm's consolidated text (tekst ujednolicony), which
has every later amendment applied; preferred over the journal text."""

ELI_PATTERN: Final = r"^(DU|MP)/\d{4}/\d{1,5}$"
"""An ELI of Dziennik Ustaw or Monitor Polski, such as ``DU/1997/483``."""

LEGAL_ACTS_ENV_PREFIX: Final = "MERITUM_CORPUS_LEGAL_"
"""Prefix of the legal acts settings: ``MERITUM_CORPUS_LEGAL_ACTS`` is a JSON list."""

LEGAL_ACTS: Final = (
    "DU/1997/483",  # Konstytucja RP (art. 29, 96, 97)
    "DU/2025/714",  # PKW: wyniki wyborów Prezydenta RP 2025
    "DU/2024/1362",  # minimalne wynagrodzenie i stawka godzinowa w 2025 r.
    "DU/2026/592",  # PIT, tekst jednolity (art. 27)
    "DU/2025/1242",  # minimalne wynagrodzenie i stawka godzinowa w 2026 r.
    "DU/2026/1213",  # minimalne wynagrodzenie i stawka godzinowa w 2027 r.
    "DU/2023/1893",  # minimalne wynagrodzenie i stawka godzinowa w 2024 r.
    "DU/2024/1773",  # ustawa o minimalnym wynagrodzeniu, tekst jednolity
    "DU/2026/554",  # CIT, tekst jednolity
    "DU/2026/1263",  # VAT, tekst jednolity
    "DU/2026/622",  # Ordynacja podatkowa, tekst jednolity
    "DU/2026/1245",  # Kodeks pracy, tekst jednolity
    "DU/2025/1749",  # emerytury i renty z FUS, tekst jednolity
    "DU/2025/1048",  # zwiększenie wskaźnika waloryzacji emerytur i rent w 2026 r.
    "MP/2026/202",  # wskaźnik waloryzacji emerytur i rent w 2026 r.
    "DU/2026/1261",  # Kodeks wyborczy, tekst jednolity
    "DU/2026/508",  # pomoc państwa w wychowywaniu dzieci (800 plus), tekst jednolity
    "DU/2023/1565",  # ustawa z 7 lipca 2023 r. podnosząca 500 plus do 800 zł
)
"""Acts whose full text the ``api.sejm.gov.pl`` entry always stores, by ELI,
first those that settle claims of the golden set. A consolidated text (tekst
jednolity) has its own ELI, so the list names the newest one in force; the
search in ``SEJM_ELI_CONSOLIDATED_SEARCH_URL`` brings the rest."""

SEJM_ELI_CONSOLIDATED_SEARCH_URL: Final = (
    "https://api.sejm.gov.pl/eli/acts/search?publisher=DU&type=Obwieszczenie"
    "&title=jednolitego%20tekstu&inForce=1&sortBy=change&sortDir=desc&limit={limit}"
)
"""Consolidated texts (teksty jednolite) in force, most recently changed first."""

LEGAL_SEARCH_LIMIT: Final = 25
"""Consolidated texts from the search stored in full per run, besides
``LEGAL_ACTS``; about 830 are in force, so a run reads only the newest."""

ACT_PART_MAX_CHARS: Final = 60_000
"""Most characters of an act's text in one document, header aside (about 15
thousand tokens), so the injection classifier reads each part whole."""

ACT_PART_URL: Final = "{url}#czesc-{number}"
"""URL of the second and later parts of a long act; the first keeps the act's."""

ACT_TEXT_UNAVAILABLE: Final = "act_text_unavailable"
"""Failure reason of an act whose ELI entry offers no text file."""

ACT_TEXT_EMPTY: Final = "act_text_empty"
"""Failure reason of an act whose PDF has no text layer (a scan)."""

PDF_CONTENT_TYPE: Final = "application/pdf"
"""Media type of an act's PDF text."""

PDF_MAX_BYTES: Final = 20 * 1024 * 1024
"""Largest PDF read; a bigger one answers 413 (``http_error``). The texts in
``LEGAL_ACTS`` are at most 5 MB."""

PDF_TOO_LARGE_STATUS: Final = 413
"""Status the PDF transport answers for a PDF over ``PDF_MAX_BYTES``."""

PDF_PAGE_BREAK: Final = "\f"
"""Separator of PDF pages in the text the transport hands on."""

PDF_SOFT_HYPHEN: Final = "\x02"
"""What PDFium puts for a hyphen that splits a word at a line end."""

ACT_PAGE_HEADER: Final = (
    r"^(©?Kancelaria Sejmu\s+s\.\s*\d+/\d+"
    r"|\d{4}-\d{2}-\d{2}"
    r"|(Dziennik Ustaw|Monitor Polski)\s*[\u2013-]\s*\d+\s*[\u2013-]\s*Poz\.\s*\d+)$"
)
"""A running head of an act's PDF page: the Sejm's page counter and date, or the
journal's page and position; dropped from the top of each page."""

ACT_UNIT_START: Final = r"^(Art\.\s*\d+[a-z]*\.|§\s*\d+[a-z]*\.|Rozdział\s|DZIAŁ\s)"
"""A line that opens an article, a paragraph, a chapter or a part of an act;
it starts a new passage paragraph."""
