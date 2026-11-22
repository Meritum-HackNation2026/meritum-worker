import asyncio
from datetime import UTC, datetime

from meritum_core.checks.contracts import CatalogEntry
from meritum_core.security.injection import InjectionScan
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker import corpus
from meritum_worker.corpus.adapters import MemoryCorpusWriter
from meritum_worker.corpus.fakes import FakeCatalogSite

NOW = datetime(2026, 11, 22, 6, 0, tzinfo=UTC)


def entry(domain: str) -> CatalogEntry:
    return CatalogEntry.model_validate(
        {
            "domain": domain,
            "publisher": "Urząd",
            "publisher_id": "urzad",
            "kind": "instytucja",
            "tier": "primary",
            "license": "CC BY 4.0",
            "ingest": "static",
            "qualified_because": "Źródło z listy organizatora konkursu.",
        }
    )


class DownInjectionDetector:
    """The classifier's provider fails, as worker#195 saw on prd."""

    async def scan(self, text: str) -> InjectionScan:  # ruff: ignore[no-self-use]  # implements the port
        msg = f"classifier down for {len(text)} characters"
        raise ProviderUnavailableError(msg)


def test_page_the_injection_detector_cannot_scan_is_a_failure_and_the_run_goes_on() -> (
    None
):
    site, store = FakeCatalogSite(pages_per_domain=2), MemoryCorpusWriter()
    ports = corpus.IngestDeps(
        discovery=site,
        fetcher=site,
        embeddings=build_embeddings(EmbeddingsSettings()),
        store=store,
        injection=DownInjectionDetector(),
    )
    report = asyncio.run(
        corpus.ingest_catalog(
            [entry("urzad.gov.pl"), entry("drugi.gov.pl")], ports, now=NOW
        )
    )
    assert report.added == 0
    assert [(f.domain, f.reason) for f in report.failures] == [
        ("urzad.gov.pl", "injection_unavailable"),
        ("urzad.gov.pl", "injection_unavailable"),
        ("drugi.gov.pl", "injection_unavailable"),
        ("drugi.gov.pl", "injection_unavailable"),
    ]
