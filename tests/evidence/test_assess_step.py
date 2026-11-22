import asyncio
from datetime import UTC, datetime

from meritum_core.checks import CheckRequest
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmProvider, LlmSettings, build_llm
from tests.evidence.samples import CLAIM_DATE, cite

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.checks.steps import assess_evidence
from meritum_worker.evidence import judge, with_validity

CATALOG = (
    CatalogEntry.model_validate(
        {
            "domain": "gov.pl",
            "publisher": "Kancelaria Prezesa Rady Ministrów",
            "publisher_id": "kprm",
            "kind": "instytucja",
            "tier": "primary",
            "license": "public domain",
            "ingest": "rss",
            "validity": "expires",
            "max_age_hours": 48,
            "qualified_because": "Oficjalny kanał rządowy z komunikatami i danymi.",
        }
    ),
)


def test_assess_evidence_dates_claims_and_judge_uses_catalog_threshold() -> None:
    job = CheckInput(
        request=CheckRequest(channel="web", text="test"),
        received_at=datetime(2026, 11, 21, 12, 0, tzinfo=UTC),
        session_id="session-1",
    )
    fact = ExtractedClaim(
        claim="Kwota minimalna wynosi 4806 zł.",
        kind="fact",
        explanation="Twierdzenie o kwocie, które da się sprawdzić.",
        claim_date=CLAIM_DATE,
        claim_date_source="text",
    )
    old = cite(
        "supports",
        "kprm",
        "primary",
        domain="gov.pl",
        published_at="2025-01-10T00:00:00+01:00",
    )
    fresh = cite(
        "supports", "demagog", published_at="2026-11-10T00:00:00+01:00", page="b"
    )
    state = CheckState(
        check_id="check-1",
        job=job,
        claims=[fact],
    )
    web = web_ports()
    deps = CheckDeps(
        llm=build_llm(LlmSettings(provider=LlmProvider.STUB, stub_fixtures=None)),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        catalog=CATALOG,
        web_search=web["web_search"],
        injection=web["injection"],
        **audio_ports(),
        **corpus_ports(),
    )
    out = asyncio.run(assess_evidence(state, deps))
    catalog = {"gov.pl": CATALOG[0]}
    assert out.claims[0].claim_date == CLAIM_DATE
    dated = with_validity([old, fresh], catalog, claim_date=CLAIM_DATE)
    result = judge(dated, catalog=catalog, claim_date=CLAIM_DATE)
    assert result.strength is not None
    assert result.strength.premises.newest_source_age_hours == 11 * 24
