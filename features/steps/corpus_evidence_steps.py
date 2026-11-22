"""Steps of features/evidence.feature: a corpus passage as evidence (worker#162).

Recorded model answers (RecordedLlm), the fake corpus documents, the real
catalogue; no database, no network.
"""

import asyncio
import dataclasses
from datetime import UTC, date, datetime

from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus import Passage, RankedPassage
from meritum_core.corpus.catalog import load_catalog
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.checks.steps import assess_evidence, verify_citations, write_answer
from meritum_worker.corpus import DocumentMeta
from meritum_worker.evidence import ClaimExplanation, RecordedLlm, StanceJudgement

CLAIM = "RCB odwołało 4 stycznia 2026 r. ostrzeżenie przed burzami dla Mazowsza"
PASSAGE_TEXT = (
    "RCB podtrzymuje ostrzeżenie przed burzami dla Mazowsza wydane 4 stycznia 2026 r."
)
FRAGMENT = "RCB podtrzymuje ostrzeżenie przed burzami dla Mazowsza"
SOURCE_ID = "doc-0123456789abcdef01234567"
URL = "https://www.gov.pl/web/rcb/ostrzezenie-burze-mazowsze"
DOMAIN = "www.gov.pl/web/rcb"
FETCHED_AT = datetime(2026, 1, 4, 18, 0, tzinfo=UTC)


@given("w migawce korpusu fragment komunikatu RCB, który przeczy twierdzeniu")
def snapshot_passage(context: Context) -> None:
    passage = Passage(
        passage_id=f"{SOURCE_ID}:abc:1",
        source_id=SOURCE_ID,
        text=PASSAGE_TEXT,
        published_on=date(2026, 1, 4),
        fetched_at=FETCHED_AT,
    )
    meta = DocumentMeta(
        source_id=SOURCE_ID,
        url=URL,
        domain=DOMAIN,
        publisher_id="rcb",
        license="public",
        published_on=date(2026, 1, 4),
        fetched_at=FETCHED_AT,
        checksum="0" * 64,
    )
    fact = ExtractedClaim(
        claim=CLAIM,
        kind="fact",
        explanation="Twierdzenie o komunikacie instytucji.",
        claim_date=date(2026, 1, 4),
        claim_date_source="text",
    )
    job = CheckInput(
        request=CheckRequest(channel="web", text=CLAIM),
        received_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
        session_id="session-behave-1",
    )
    # What search_corpus leaves for assess_evidence: reranked passages per fact.
    context.state = CheckState(
        check_id="check-behave-1",
        job=job,
        claims=[fact],
        corpus_version="2026-01-05T10:00Z",
        passages={CLAIM: [RankedPassage(passage=passage, relevance=0.9)]},
    )
    stance = StanceJudgement.model_validate(
        {"relevant": True, "fragment": FRAGMENT, "stance": "refutes"}
    )
    written = ClaimExplanation(
        explanation="RCB podtrzymuje ostrzeżenie.",
        unresolved="Bez komunikatu RCB nie da się tego rozstrzygnąć.",
    )
    draft = AnswerDraft(claims=[written], limitations=["Sprawdzono tylko korpus."])
    context.llm = RecordedLlm({PASSAGE_TEXT: stance}, draft)
    context.corpus_documents = [meta]


@when("system ocenia dowody z korpusu i pisze odpowiedź")
def assess_corpus_evidence(context: Context) -> None:
    ports = dataclasses.replace(
        CheckDeps(
            llm=context.llm,
            records=InMemoryCheckRecordRepository(),
            pages=FakePageFetcher(),
            pii=NullPiiGate(),
            **audio_ports(),
            **web_ports(),
            **corpus_ports(documents=context.corpus_documents, version="v1"),
        ),
        catalog=load_catalog(),
    )
    state = context.state
    for step in (assess_evidence, verify_citations, write_answer):
        state = asyncio.run(step(state, ports))
    context.state = state
    assert state.result is not None
    assert state.result.status == "done", state.result.message
    context.claim = state.result.claims[0]


@then('werdykt to "{verdict}" z cytatem z tego fragmentu')
def verdict_with_passage(context: Context, verdict: str) -> None:
    claim = context.claim
    assert claim.verdict == verdict, (claim.verdict, claim.unresolved)
    assert [(c.source.id, c.fragment, c.stance) for c in claim.citations] == [
        (SOURCE_ID, FRAGMENT, "refutes")
    ]


@then("cytat ma wydawcę i domenę z katalogu")
def publisher_from_catalog(context: Context) -> None:
    source = context.claim.citations[0].source
    assert (source.publisher_id, source.domain, str(source.url)) == ("rcb", DOMAIN, URL)
    assert source.publisher == "Rządowe Centrum Bezpieczeństwa"
    assert (source.tier, source.via) == ("primary", "corpus")
