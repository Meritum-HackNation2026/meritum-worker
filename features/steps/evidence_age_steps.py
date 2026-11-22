from behave import given, then, when
from behave.runner import Context
from meritum_core.checks.contracts import CatalogEntry
from tests.evidence.samples import CLAIM_DATE, cite

from meritum_worker.evidence import judge, with_validity

OLD = "2025-01-10T00:00:00+01:00"
FRESH = "2026-11-10T00:00:00+01:00"
WHY_GOV = "Oficjalny kanał rządowy z komunikatami i danymi."
CATALOG = {
    "gov.pl": CatalogEntry.model_validate(
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
            "qualified_because": WHY_GOV,
        }
    )
}


@given("twierdzenie z datą i dwa dowody, stary z expires i świeży")
def claim_with_old_and_fresh_support(context: Context) -> None:
    context.claim_date = CLAIM_DATE
    context.citations = [
        cite("supports", "kprm", "primary", domain="gov.pl", published_at=OLD),
        cite("supports", "demagog", published_at=FRESH, page="b"),
    ]


@when("worker liczy siłę dowodów i werdykt")
def worker_judges_strength(context: Context) -> None:
    dated = with_validity(context.citations, CATALOG, claim_date=context.claim_date)
    context.judgement = judge(dated, catalog=CATALOG, claim_date=context.claim_date)


@then("wiek i ważność dowodów liczone są od daty twierdzenia funkcjami z core#41")
def premises_use_claim_date_and_catalog(context: Context) -> None:
    strength = context.judgement.strength
    assert strength is not None
    assert strength.premises.newest_source_age_hours == 11 * 24
