"""Constants of the catalogue ingestion that ``constants.py`` has no room for.

Features:
    US-KOR-02, US-KOR-05, F-10, F-12, ADR-32
"""

from typing import Final

INJECTION_UNAVAILABLE: Final = "injection_unavailable"
"""Failure reason of a page the injection detector could not scan (its provider
failed); the page is not stored unscanned and the next one follows."""

ENTRY_URLS: Final = {
    "stat.gov.pl": "https://stat.gov.pl/sygnalne/komunikaty-i-obwieszczenia/",
}
"""Entry page of a static catalogue domain whose own address holds no text, from
the catalogue section of core's README. stat.gov.pl redirects to a login page on
new.stat.gov.pl (``login_wall``, worker#220)."""

PRESSCORNER_DETAIL: Final = (
    r"^https://ec\.europa\.eu/commission/presscorner/detail/"
    r"(?P<language>[a-z]{2})/(?P<reference>[a-z]+_\d{2}_\d+)$"
)
"""A Press Corner document page (``detail/en/ip_26_2532``). The page is a JavaScript
application with no text in its HTML (``javascript_required``, worker#220)."""

PRESSCORNER_API: Final = (
    "https://ec.europa.eu/commission/presscorner/api/documents"
    "?reference={reference}&language={language}"
)
"""The JSON API the Press Corner page reads its document from; the reference is
upper case with slashes (``IP/26/2532``). ec.europa.eu's robots.txt allows it."""

INGEST_SKIPPED: Final = {
    "ulc.gov.pl": (
        "Imperva Incapsula odsyła robotom stronę ze skryptem zamiast treści"
        " (javascript_required). Cytujemy tylko z wyszukiwania na żywo."
    ),
    "www.sar.gov.pl": (
        "Imperva Incapsula odsyła robotom stronę ze skryptem zamiast treści"
        " (javascript_required). Cytujemy tylko z wyszukiwania na żywo."
    ),
    "eur-lex.europa.eu": (
        "Antybot AWS blokuje automaty. Akty prawa UE cytujemy z wyszukiwania"
        " na żywo; pobieranie przez Cellar/SPARQL to osobne zgłoszenie."
    ),
    "odyseusz.gov.pl": (
        "Strona wymaga JavaScriptu (javascript_required), a ta sama treść jest"
        " na www.gov.pl/web/dyplomacja, którą pobieramy."
    ),
}
"""Catalogue entries the ingestion skips, with the reason, decided in worker#220.
The RCB and RSO entries skipped in worker#239 are read through their API
(``catalog_api.rso``, worker#279).

Unlike core's ``excluded``, which also bars an entry from live search, these stay
citable from live search; only the scheduled ingestion leaves them out. They move
to the catalogue (``ingest: live``) with the next core pin."""

SKIPPED_PAGES: Final = {
    "pkw.gov.pl": r"/(?:wyniki-glosowania|wyniki-wyborow|wizualizacja-wynikow)/?$",
}
"""Pages of an entry's feed the ingestion skips, as a pattern of the URL path, per
catalogue domain. PKW's election results pages are a JavaScript application: in
the HTML there is only the site menu, about 200 characters. Results are cited from
PKW's announcement in Dziennik Ustaw (e.g. Dz.U. 2025 poz. 714), which comes in
with the full texts of ELI acts; PKW's news and resolutions stay (worker#220)."""
