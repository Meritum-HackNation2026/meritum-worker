import asyncio
import dataclasses
from datetime import UTC, date, datetime

from meritum_core.checks import CheckRequest
from meritum_core.checks.contracts import Source
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus import Passage, RankedPassage
from meritum_core.corpus.catalog import load_catalog
from meritum_core.evidence import SourceDocument
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate

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
from meritum_worker.corpus import DocumentMeta
from meritum_worker.evidence import RecordedLlm, StanceJudgement

CLAIM = "RCB odwołało ostrzeżenie przed burzami dla Mazowsza"
URL = "https://www.gov.pl/web/rcb/burze"
FETCHED_AT = datetime(2026, 1, 4, 18, 0, tzinfo=UTC)
PAGE = "Pełny komunikat: RCB podtrzymuje ostrzeżenie przed burzami dla Mazowsza."
PASSAGE = "RCB podtrzymuje ostrzeżenie przed burzami dla Mazowsza."


def _state(evidence: list[SourceDocument]) -> CheckState:
    fact = ExtractedClaim(
        claim=CLAIM,
        kind="fact",
        explanation="Twierdzenie o komunikacie instytucji.",
        claim_date=date(2026, 1, 4),
        claim_date_source="text",
    )
    passage = Passage(
        passage_id="doc-rcb:abc:1",
        source_id="doc-rcb",
        text=PASSAGE,
        published_on=date(2026, 1, 4),
        fetched_at=FETCHED_AT,
    )
    job = CheckInput(
        request=CheckRequest(channel="web", text=CLAIM),
        received_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        session_id="session-1",
    )
    return CheckState(
        check_id="check-1",
        job=job,
        claims=[fact],
        evidence=evidence,
        passages={CLAIM: [RankedPassage(passage=passage, relevance=0.9)]},
    )


def _deps(llm: RecordedLlm) -> CheckDeps:
    meta = DocumentMeta(
        source_id="doc-rcb",
        url=URL,
        domain="www.gov.pl/web/rcb",
        publisher_id="rcb",
        license="public",
        fetched_at=FETCHED_AT,
        checksum="0" * 64,
    )
    return dataclasses.replace(
        CheckDeps(
            llm=llm,
            records=InMemoryCheckRecordRepository(),
            pages=FakePageFetcher(),
            pii=NullPiiGate(),
            **audio_ports(),
            **web_ports(),
            **corpus_ports(documents=[meta], version="v1"),
        ),
        catalog=load_catalog(),
    )


def _stance(fragment: str) -> StanceJudgement:
    return StanceJudgement.model_validate(
        {"relevant": True, "fragment": fragment, "stance": "refutes"}
    )


def test_corpus_passage_is_assessed_and_joins_the_evidence() -> None:
    llm = RecordedLlm({PASSAGE: _stance(PASSAGE)})

    state = asyncio.run(assess_evidence(_state([]), _deps(llm)))

    assert [d.source.id for d in state.evidence] == ["doc-rcb"]
    assert [(a.fact, a.draft.source_id) for a in state.assessed] == [(0, "doc-rcb")]


def test_page_live_search_already_fetched_is_assessed_once_from_its_full_text() -> None:
    source = Source(
        id="web-rcb",
        title=URL,
        publisher="Rządowe Centrum Bezpieczeństwa",
        publisher_id="rcb",
        url=URL,
        domain="www.gov.pl/web/rcb",
        kind="instytucja",
        tier="primary",
        fetched_at=FETCHED_AT,
        via="web_search",
    )
    page = SourceDocument(source=source, text=PAGE)
    llm = RecordedLlm({PAGE: _stance(PASSAGE)})

    state = asyncio.run(assess_evidence(_state([page]), _deps(llm)))

    assert [d.source.id for d in state.evidence] == ["web-rcb"]
    assert [a.draft.source_id for a in state.assessed] == ["web-rcb"]
    assert len(llm.prompts) == 1
