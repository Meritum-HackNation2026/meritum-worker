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
