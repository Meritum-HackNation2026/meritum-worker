"""Citation builders for worker evidence tests."""

from datetime import UTC, date, datetime

from meritum_core.checks.contracts import (
    Citation,
    Source,
    SourceTier,
    Stance,
    Validity,
)

CLAIM_DATE = date(2026, 11, 21)
FETCHED_AT = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)


def cite(  # ruff: ignore[too-many-arguments]
    stance: Stance,
    publisher_id: str,
    tier: SourceTier = "secondary",
    *,
    domain: str | None = None,
    published_at: str = "2026-11-10T00:00:00+01:00",
    validity: Validity = "expires",
    page: str = "a",
) -> Citation:
    """One citation for ``publisher_id`` with the given stance."""
    host = domain or publisher_id
    source = Source(
        id=f"{publisher_id}-{page}",
        title=f"Tytuł {page}",
        publisher=publisher_id.upper(),
        publisher_id=publisher_id,
        url=f"https://{host}.example.pl/{page}",
        domain=host,
        kind="instytucja",
        tier=tier,
        published_at=datetime.fromisoformat(published_at),
        fetched_at=FETCHED_AT,
    )
    return Citation(
        source=source,
        fragment=f"Fragment strony {page} wydawcy {publisher_id} (testowy).",
        stance=stance,
        validity=validity,
    )
