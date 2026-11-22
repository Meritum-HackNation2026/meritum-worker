"""Worker evidence rules use core#41 for age, validity and strength."""

from meritum_core.checks.contracts import CatalogEntry
from tests.evidence.samples import CLAIM_DATE, cite

from meritum_worker.evidence import judge, with_validity

OLD = "2025-01-10T00:00:00+01:00"
FRESH = "2026-11-10T00:00:00+01:00"
KPRM = CatalogEntry.model_validate(
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
)
CATALOG = {"gov.pl": KPRM}


def test_stale_article_does_not_outweigh_fresh_support_at_claim_date() -> None:
    citations = [
        cite("supports", "kprm", "primary", domain="gov.pl", published_at=OLD),
        cite("supports", "demagog", published_at=FRESH, page="b"),
    ]
    result = judge(citations, catalog=CATALOG, claim_date=CLAIM_DATE)
    assert result.strength is not None
    assert result.strength.premises.newest_source_age_hours == 11 * 24


def test_catalog_max_age_hours_reaches_compute_strength() -> None:
    citations = [cite("supports", "kprm", "primary", domain="gov.pl")]
    result = judge(citations, catalog=CATALOG, claim_date=CLAIM_DATE)
    assert result.strength is not None
    assert result.strength.premises.max_age_hours == 48


def test_older_supporting_evidence_superseded_by_newer_official_one() -> None:
    old = cite("supports", "kprm", "primary", domain="gov.pl", published_at=OLD)
    newer = cite(
        "refutes", "kprm", "primary", domain="gov.pl", published_at=FRESH, page="b"
    )
    dated = with_validity([old, newer], CATALOG, claim_date=CLAIM_DATE)
    assert [c.validity for c in dated] == ["superseded", "expires"]
    result = judge(dated, catalog=CATALOG, claim_date=CLAIM_DATE)
    assert (result.verdict, result.technique) == ("false", "outdated")
    assert result.strength is not None
    assert result.strength.premises.independent_sources == 1


def test_expired_support_does_not_conflict_with_a_fresh_refutation() -> None:
    citations = [
        cite("supports", "kprm", "primary", domain="gov.pl", published_at=OLD),
        cite("refutes", "demagog", published_at=FRESH, page="b"),
    ]
    result = judge(citations, catalog=CATALOG, claim_date=CLAIM_DATE)
    assert result.verdict == "false"


def test_expired_evidence_on_both_sides_still_conflicts() -> None:
    citations = [
        cite("supports", "kprm", "primary", domain="gov.pl", published_at=OLD),
        cite("refutes", "demagog", published_at=OLD, page="b"),
    ]
    result = judge(citations, catalog=CATALOG, claim_date=CLAIM_DATE)
    assert result.verdict == "insufficient_evidence"
