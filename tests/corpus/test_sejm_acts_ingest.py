import asyncio
import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.catalog_api import (
    api_listings,
)
from meritum_worker.corpus.documents import DocumentMeta
from meritum_worker.corpus.fakes import FakeCatalogSite, FakePublicApi
from meritum_worker.security import CleanInjectionDetector

NOW = datetime(2026, 11, 20, 9, 30, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "api"
ACTS = "https://api.sejm.gov.pl/eli/acts"
CONSTITUTION = f"{ACTS}/DU/1997/483"
CONSTITUTION_PDF = f"{CONSTITUTION}/text/U/D19970483Lj.pdf"
MINIMUM_WAGE = f"{ACTS}/DU/2025/1242"
ARTICLE_29 = "Art. 29. Stolicą Rzeczypospolitej Polskiej jest Warszawa."


def sejm() -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": "api.sejm.gov.pl",
            "publisher": "Kancelaria Sejmu",
            "publisher_id": "kancelaria-sejmu",
            "kind": "akt_prawny",
            "tier": "primary",
            "license": "materiał urzędowy (akty normatywne)",
            "ingest": "api",
            "qualified_because": "Oficjalne API ELI.",
        }
    )


def recorded(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def api_with_acts() -> FakePublicApi:
    api = FakePublicApi()
    api.answer(f"{ACTS}/DU/2026", recorded("sejm-eli-du.json"))
    api.answer(CONSTITUTION, recorded("sejm-eli-du-1997-483.json"))
    api.answer(
        CONSTITUTION_PDF,
        (FIXTURES / "sejm-konstytucja-tekst-u.pdf").read_bytes(),
        content_type="application/pdf",
    )
    api.answer(MINIMUM_WAGE, recorded("sejm-eli-du-2025-1242.json"))
    api.answer(
        f"{MINIMUM_WAGE}/text.pdf",
        (FIXTURES / "sejm-du-2025-1242.pdf").read_bytes(),
        content_type="application/pdf",
    )
    return api


def run(
    api: FakePublicApi, *acts: str
) -> tuple[corpus.IngestReport, MemoryCorpusWriter]:
    store = MemoryCorpusWriter()
    site = FakeCatalogSite(pages_per_domain=1)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=CleanInjectionDetector(),
        api_fetcher=api.fetcher(),
        legal=corpus.LegalActs(acts=acts),
    )
    report = asyncio.run(corpus.ingest_catalog([sejm()], deps, now=NOW))
    return report, store


def stored(store: MemoryCorpusWriter, url: str) -> tuple[DocumentMeta, str] | None:
    for meta in asyncio.run(store.documents()):
        if meta.url == url:
            return meta, asyncio.run(store.full_text(meta.source_id)) or ""
    return None


def test_constitution_is_stored_with_its_full_text() -> None:
    report, store = run(api_with_acts(), "DU/1997/483")
    assert report.failures == ()
    found = stored(store, CONSTITUTION)
    assert found is not None
    meta, text = found
    assert ARTICLE_29 in text
    assert meta.published_on == date(1997, 4, 2)
    assert any(ARTICLE_29 in p.text for p in store.passages.values())


def test_minimum_wage_regulation_keeps_its_amounts() -> None:
    _, store = run(api_with_acts(), "DU/2025/1242")
    found = stored(store, MINIMUM_WAGE)
    assert found is not None
    assert "w wysokości 4806 zł." in found[1]
    assert "minimalną stawkę godzinową w wysokości 31,40 zł." in found[1]


def test_act_without_text_keeps_its_title_and_reports_why() -> None:
    api = api_with_acts()
    answer = json.loads(recorded("sejm-eli-du-2025-1242.json"))
    answer |= {"textPDF": False, "textHTML": False, "texts": []}
    api.answer(MINIMUM_WAGE, json.dumps(answer))
    report, store = run(api, "DU/2025/1242")
    (failure,) = report.failures
    assert (failure.url, failure.reason) == (MINIMUM_WAGE, "act_text_unavailable")
    found = stored(store, MINIMUM_WAGE)
    assert found is not None
    assert "minimalnego wynagrodzenia" in found[1]


def test_failed_text_download_stores_nothing_new_for_the_act() -> None:
    api = api_with_acts()
    api.answer(CONSTITUTION_PDF, "", status=503, content_type="text/plain")
    report, store = run(api, "DU/1997/483")
    assert [(f.url, f.reason) for f in report.failures] == [
        (CONSTITUTION_PDF, "http_error")
    ]
    assert stored(store, CONSTITUTION) is None


def test_pdf_answer_reaches_untrusted_text_as_pages() -> None:
    page = asyncio.run(
        api_with_acts().fetcher().fetch(CONSTITUTION_PDF, purpose=FetchPurpose.SOURCE)
    )
    first, second = page.untrusted_text.split("\f")
    assert "KONSTYTUCJA" in first
    assert "Stolicą Rzeczypospolitej Polskiej jest Warszawa." in second


def test_broken_pdf_is_unsupported_content() -> None:
    api = FakePublicApi()
    api.answer(CONSTITUTION_PDF, b"%PDF-1.7 broken", content_type="application/pdf")
    with pytest.raises(PageFetchError, match="unsupported_content"):
        asyncio.run(api.fetcher().fetch(CONSTITUTION_PDF, purpose=FetchPurpose.SOURCE))


def test_act_listed_by_eli_and_by_the_search_is_read_once() -> None:
    api = api_with_acts()
    search = api_listings(sejm(), NOW, search_limit=1)[-2].url
    answer = json.loads(recorded("sejm-eli-search-tj.json"))
    answer["items"] = [json.loads(recorded("sejm-eli-du-1997-483.json"))]
    api.answer(search, json.dumps(answer))
    store = MemoryCorpusWriter()
    site = FakeCatalogSite(pages_per_domain=1)
    deps = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=CleanInjectionDetector(),
        api_fetcher=api.fetcher(),
        legal=corpus.LegalActs(acts=("DU/1997/483",), search_limit=1),
    )
    report = asyncio.run(corpus.ingest_catalog([sejm()], deps, now=NOW))
    assert report.failures == ()
    assert api.requested.count(CONSTITUTION_PDF) == 1


def test_act_of_this_year_read_in_full_keeps_its_full_text() -> None:
    api = api_with_acts()
    year = {"items": [json.loads(recorded("sejm-eli-du-2025-1242.json"))]}
    api.answer(f"{ACTS}/DU/2026", json.dumps(year))
    report, store = run(api, "DU/2025/1242")
    assert report.failures == ()
    found = stored(store, MINIMUM_WAGE)
    assert found is not None
    assert "w wysokości 4806 zł." in found[1]
