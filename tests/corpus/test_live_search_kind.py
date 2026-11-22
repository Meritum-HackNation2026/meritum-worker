import asyncio
from datetime import date
from urllib.parse import urlsplit

from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.pii import NullPiiGate

from meritum_worker.checks import FakePageFetcher
from meritum_worker.corpus import FakeWebSearch, LiveSearchPorts, search_live
from meritum_worker.security import CleanInjectionDetector

SEJM = "kancelaria-sejmu"
TRANSCRIPT = (
    "https://api.sejm.gov.pl/sejm/term10/proceedings/45/2026-11-20/transcripts/157"
)


def test_sejm_transcript_is_a_transcript_not_a_legal_act() -> None:
    candidate = WebSearchCandidate(
        url=TRANSCRIPT, domain=urlsplit(TRANSCRIPT).netloc, publisher_id=SEJM
    )
    page = FetchedPage(
        url=TRANSCRIPT,
        content_type="text/html",
        untrusted_text="Poseł mówił o budżecie na 2027 rok.",
        published_at=date(2026, 11, 20),
    )
    ports = LiveSearchPorts(
        web_search=FakeWebSearch((candidate,)),
        pages=FakePageFetcher(page),
        injection=CleanInjectionDetector(),
        pii=NullPiiGate(),
        catalog=load_catalog(),
    )
    (document,) = asyncio.run(search_live(("budżet 2027",), ports)).documents
    assert document.source.kind == "transcript"
