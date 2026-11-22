import asyncio
from datetime import date
from pathlib import Path

import pytest
from meritum_core.corpus import CorpusProvider, CorpusSettings
from meritum_core.corpus.fetching import (
    FetchedPage,
    FetchFailureReason,
    FetchPurpose,
    PageFetchError,
)
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import PresscornerFetcher
from meritum_worker.security import CleanInjectionDetector

ANSWER = (Path(__file__).parent / "fixtures" / "api" / "presscorner-ip.json").read_text(
    encoding="utf-8"
)
DETAIL = "https://ec.europa.eu/commission/presscorner/detail/pl/ip_26_2532"
API = (
    "https://ec.europa.eu/commission/presscorner/api/documents"
    "?reference=IP/26/2532&language=pl"
)


class Recorder:
    """PageFetcherPort answering every URL with one text, recording the calls."""

    def __init__(self, text: str) -> None:
        self.text = text
        self.asked: list[tuple[str, FetchPurpose]] = []

    async def fetch(self, url: str, *, purpose: FetchPurpose) -> FetchedPage:
        self.asked.append((url, purpose))
        return FetchedPage(url=url, content_type="text/plain", untrusted_text=self.text)


def fetch(pages: Recorder, api: Recorder, url: str = DETAIL) -> FetchedPage:
    fetcher = PresscornerFetcher(pages, api)
    return asyncio.run(fetcher.fetch(url, purpose=FetchPurpose.SOURCE))


def test_press_corner_page_is_read_from_its_json_api_under_its_own_link() -> None:
    pages, api = Recorder("strona"), Recorder(ANSWER)
    page = fetch(pages, api)
    assert api.asked == [(API, FetchPurpose.SOURCE)]
    assert pages.asked == []
    assert page.url == DETAIL
    assert page.published_at == date(2026, 11, 21)
    assert page.untrusted_text == (
        "Komisja podpisuje umowę handlową\n\n"
        "Komisja Europejska podpisała dziś umowę & protokół. Cło spada o 5%."
    )
    assert "Rzecznik" not in page.untrusted_text


def test_other_pages_go_to_the_page_fetcher() -> None:
    pages, api = Recorder("tekst strony"), Recorder(ANSWER)
    url = "https://ec.europa.eu/commission/presscorner/home/pl"
    assert fetch(pages, api, url).untrusted_text == "tekst strony"
    assert api.asked == []


@pytest.mark.parametrize("answer", ["<html>", "[]", '{"docuLanguageResource": null}'])
def test_answer_that_is_not_a_press_document_is_unsupported_content(
    answer: str,
) -> None:
    with pytest.raises(PageFetchError) as raised:
        fetch(Recorder(""), Recorder(answer))
    assert raised.value.reason is FetchFailureReason.UNSUPPORTED_CONTENT


def test_ingestion_fetches_pages_through_the_press_corner_reader() -> None:
    deps = corpus.build_ingest_deps(
        CorpusSettings(provider=CorpusProvider.MEMORY),
        build_embeddings(EmbeddingsSettings()),
        CleanInjectionDetector(),
    )
    assert isinstance(deps.fetcher, PresscornerFetcher)
