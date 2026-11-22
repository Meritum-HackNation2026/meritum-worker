"""Shared setup of the incident tests: one EUvsDisinfo case and keyed embeddings."""

from datetime import UTC, date, datetime

from meritum_core.checks import CheckRequest
from meritum_core.jobs.contracts import CheckInput

from meritum_worker.checks import CheckState, ExtractedClaim
from meritum_worker.corpus import Entry, StoredEntry
from meritum_worker.evidence import KeyedEmbeddings, document

CLAIM_PL = "Polscy żołnierze masowo dezerterują z granicy z Białorusią"
TITLE_EN = "Polish soldiers massively desert the Belarus border"
FACT = "There is no evidence of mass desertion from the Polish army."
CASE_URL = "https://euvsdisinfo.eu/report/polish-soldiers-desert"
ON_TOPIC = (1.0, 0.0, 0.0)
OFF_TOPIC = (0.0, 1.0, 0.0)
CASE_DAY = datetime(2026, 11, 3, tzinfo=UTC)
CASE_DATE = CASE_DAY.date()


def case(
    *, title: str = TITLE_EN, domains: tuple[str, ...] = (), deleted: bool = False
) -> StoredEntry:
    entry = Entry(
        key="case:1",
        kind="case",
        title=title,
        url=CASE_URL,
        published_at=CASE_DAY,
        description="Claims that Polish soldiers desert the border en masse.",
        fact=FACT,
        domains=domains,
    )
    source = document(
        "euvs-1", FACT, publisher_id="eeas-euvsdisinfo", tier="secondary"
    ).source
    return StoredEntry(
        entry=entry,
        description_vector=ON_TOPIC,
        source=source,
        deleted_at=CASE_DAY if deleted else None,
    )


def embeddings() -> KeyedEmbeddings:
    return KeyedEmbeddings({CLAIM_PL: ON_TOPIC, TITLE_EN: ON_TOPIC}, OFF_TOPIC)


def checked(url: str | None = None, on: date = CASE_DATE) -> CheckState:
    request = (
        CheckRequest(channel="web", url=url)
        if url is not None
        else CheckRequest(channel="web", text=CLAIM_PL)
    )
    job = CheckInput(
        request=request,
        received_at=datetime(2026, 11, 22, 12, 0, tzinfo=UTC),
        session_id="session-incidents",
    )
    fact = ExtractedClaim(
        claim=CLAIM_PL,
        kind="fact",
        explanation="Twierdzenie o faktach, które da się sprawdzić.",
        claim_date=on,
        claim_date_source="text",
    )
    return CheckState(check_id="check-incidents", job=job, claims=[fact])
