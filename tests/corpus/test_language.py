import asyncio
from pathlib import Path

import pytest
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.injection import NullInjectionGate, build_injection_detector
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm

from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import (
    FakeWebSearch,
    LiveSearchPorts,
    detect_language,
    search_live,
)

URL = "https://www.gov.pl/web/rcb/ostrzezenie"
FIXTURES = Path(__file__).resolve().parents[2] / "features" / "fixtures"


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Rząd przyjął uchwałę o płacy minimalnej.", "pl"),
        ("Rada Ministrow przyjela uchwale w sprawie budzetu i ustawy", "pl"),
        ("The Commission adopted the regulation on state aid.", "en"),
        ("", "pl"),
    ],
)
def test_detect_language(text: str, language: str) -> None:
    assert detect_language(text) == language


def test_live_search_page_gets_its_language() -> None:
    catalog = load_catalog()
    candidate = WebSearchCandidate(
        url=URL, domain="www.gov.pl/web/rcb", publisher_id="rcb"
    )
    llm = build_llm(
        LlmSettings(
            provider=LlmProvider.STUB, stub_fixtures=FIXTURES / "llm_stub_rcb.json"
        )
    )

    def languages(text: str) -> list[str]:
        ports = LiveSearchPorts(
            web_search=FakeWebSearch((candidate,)),
            pages=FakePageFetcher(
                FetchedPage(url=URL, content_type="text/html", untrusted_text=text)
            ),
            injection=build_injection_detector(llm=llm, gate=NullInjectionGate()),
            pii=NullPiiGate(),
            catalog=catalog,
        )
        found = asyncio.run(search_live(["q"], ports))
        return [d.source.language for d in found.documents]

    assert languages("RCB ostrzega przed burzami na Mazowszu.") == ["pl"]
    assert languages("The Commission adopted the regulation on 5 January.") == ["en"]
