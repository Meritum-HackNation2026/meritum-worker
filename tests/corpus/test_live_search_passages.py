import asyncio
from typing import override

from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.injection import InjectionScan
from meritum_core.security.pii import NullPiiGate

from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import (
    MAX_PAGE_TEXT_CHARS,
    FakeWebSearch,
    LiveSearchPorts,
    search_live,
)
from meritum_worker.security import CleanInjectionDetector

RODZINA = "https://www.gov.pl/web/rodzina/minimalne-wynagrodzenie-za-prace"
DECISIVE = "Minimalne wynagrodzenie za pracę od 1 stycznia 2026 r. wynosi 4806 zł."
QUERY = "Płaca minimalna w 2026 roku wynosi 4806 zł"
MENU = "\n\n".join(
    ["Ta strona używa plików cookies. Akceptuję."]
    + [f"Menu Strona główna Aktualności Kontakt Mapa serwisu {i}" for i in range(120)]
)


class _RecordingDetector(CleanInjectionDetector):
    def __init__(self) -> None:
        self.scanned: list[str] = []

    @override
    async def scan(self, text: str) -> InjectionScan:
        self.scanned.append(text)
        return await super().scan(text)


def _found(text: str, detector: _RecordingDetector) -> str:
    candidate = WebSearchCandidate(
        url=RODZINA, domain="www.gov.pl/web/rodzina", publisher_id="mrpips"
    )
    page = FetchedPage(url=RODZINA, content_type="text/html", untrusted_text=text)
    ports = LiveSearchPorts(
        web_search=FakeWebSearch((candidate,)),
        pages=FakePageFetcher(page),
        injection=detector,
        pii=NullPiiGate(),
        catalog=load_catalog(),
    )
    (document,) = asyncio.run(search_live((QUERY,), ports)).documents
    return document.text


def test_sentence_after_the_menu_reaches_the_evidence() -> None:
    assert len(MENU) > MAX_PAGE_TEXT_CHARS
    detector = _RecordingDetector()
    text = _found(f"{MENU}\n\n{DECISIVE}\n\nStopka: Ministerstwo Rodziny", detector)
    assert DECISIVE in text
    assert len(text) <= MAX_PAGE_TEXT_CHARS
    # The scanned text is the evidence text: quotes stay verbatim.
    assert detector.scanned == [text]


def test_kept_passages_stay_in_page_order() -> None:
    lead = "Płaca minimalna rośnie co roku."
    text = _found(f"{lead}\n\n{MENU}\n\n{DECISIVE}", _RecordingDetector())
    assert text.index(lead) < text.index(DECISIVE)


def test_short_page_is_kept_whole() -> None:
    short = f"Menu\n\n{DECISIVE}"
    assert _found(short, _RecordingDetector()) == short
