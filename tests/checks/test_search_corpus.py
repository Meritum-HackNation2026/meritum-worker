import asyncio
import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from meritum_core.corpus import CorpusSearchPort, Passage
from meritum_core.corpus.rerank.fakes import FakeReranker
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakeCorpusSearch,
    corpus_ports,
)
from meritum_worker.checks.settings import ResearchSettings
from meritum_worker.checks.steps import search_corpus, search_web
from meritum_worker.corpus import MAX_PARALLEL_CLAIMS, FakeWebSearch

type MakeDeps = Callable[..., CheckDeps]

PASSAGES = tuple(
    Passage(
        passage_id=f"p{i}",
        source_id=f"src-{i}",
        text=f"Fragment {i}.",
        published_on=date(2026, 11, 1),
        fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
        score=1 - i / 100,
    )
    for i in range(3)
)


def _fact(text: str) -> ExtractedClaim:
    return ExtractedClaim(
        claim=text,
        kind="fact",
        explanation="Twierdzenie o liczbie, które da się sprawdzić.",
        claim_date=date(2026, 1, 5),
        claim_date_source="today",
    )


def _with_facts(state: CheckState, count: int) -> CheckState:
    facts = [_fact(f"Twierdzenie numer {i} o płacy") for i in range(count)]
    return state.model_copy(update={"claims": facts})


class _BrokenReranker:
    async def rerank(  # ruff: ignore[no-self-use]  # same signature as the port
        self, claim: str, passages: list[Passage], *, limit: int = 5
    ) -> list[object]:
        msg = f"reranker down for {len(passages)} passages, limit {limit}, {claim}"
        raise ProviderUnavailableError(msg)


def test_search_corpus_keeps_reranked_passages_per_fact(
    state: CheckState, make_deps: MakeDeps
) -> None:
    corpus = FakeCorpusSearch(PASSAGES)
    reranker = FakeReranker({"p2": 0.9})
    deps = dataclasses.replace(
        make_deps(),
        corpus=corpus,
        reranker=reranker,
        corpus_version="2026-11-21T10:00Z",
    )
    out = asyncio.run(search_corpus(state, deps))
    claim = state.claims[0].claim
    assert out.passages[claim][0].passage.passage_id == "p2"
    assert out.corpus_version == "2026-11-21T10:00Z"
    assert out.retrieval_errors == []
    assert corpus.queries == [(claim, date(2026, 1, 5))]


def test_search_corpus_keeps_search_order_when_reranker_fails(
    state: CheckState, make_deps: MakeDeps
) -> None:
    ports = corpus_ports(PASSAGES, version="v1")
    deps = dataclasses.replace(make_deps(), **{**ports, "reranker": _BrokenReranker()})
    out = asyncio.run(search_corpus(state, deps))
    kept = out.passages[state.claims[0].claim]
    assert [p.passage.passage_id for p in kept] == ["p0", "p1", "p2"]
    assert out.retrieval_errors == ["search_corpus: reranker_unavailable"]


def test_search_corpus_researches_at_most_three_claims_at_once(
    state: CheckState, make_deps: MakeDeps
) -> None:
    corpus = FakeCorpusSearch(PASSAGES)
    deps = dataclasses.replace(make_deps(), corpus=corpus, corpus_version="v1")
    out = asyncio.run(search_corpus(_with_facts(state, 4), deps))
    assert len(out.passages) == 4
    assert corpus.most_at_once == MAX_PARALLEL_CLAIMS == 3


def test_search_corpus_is_skipped_without_a_pinned_snapshot(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(search_corpus(state, make_deps()))
    assert out.skipped_steps == ["search_corpus"]
    assert out.passages == {}


def test_search_corpus_is_skipped_without_facts(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = dataclasses.replace(make_deps(), **corpus_ports(PASSAGES, version="v1"))
    out = asyncio.run(search_corpus(state.model_copy(update={"claims": []}), deps))
    assert out.skipped_steps == ["search_corpus"]


def test_fake_corpus_search_is_a_corpus_search_port() -> None:
    assert isinstance(FakeCorpusSearch(PASSAGES), CorpusSearchPort)


def test_search_corpus_masks_the_claim_before_it_is_embedded(
    state: CheckState, make_deps: MakeDeps
) -> None:
    corpus = FakeCorpusSearch(PASSAGES)
    deps = dataclasses.replace(make_deps(), corpus=corpus, corpus_version="v1")
    fact = _fact("Pod numerem 600 700 800 płaca minimalna wynosi 4806 zł")
    asyncio.run(search_corpus(state.model_copy(update={"claims": [fact]}), deps))
    ((query, _),) = corpus.queries
    assert "600 700 800" not in query


def test_research_settings_pin_the_snapshot_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert ResearchSettings().corpus_version == "none"
    monkeypatch.setenv("MERITUM_CORPUS_VERSION", "2026-11-21T10:00Z")
    assert ResearchSettings().corpus_version == "2026-11-21T10:00Z"


def test_search_web_researches_at_most_three_claims_at_once(
    state: CheckState, make_deps: MakeDeps
) -> None:
    web = FakeWebSearch()
    deps = dataclasses.replace(make_deps(), web_search=web)
    asyncio.run(search_web(_with_facts(state, 5), deps))
    assert len(web.queries) == 5
    assert web.most_at_once == MAX_PARALLEL_CLAIMS


def _bilingual(text: str, english: str) -> ExtractedClaim:
    return _fact(text).model_copy(update={"claim_en": english})


def test_search_corpus_searches_the_polish_and_the_english_query(
    state: CheckState, make_deps: MakeDeps
) -> None:
    corpus = FakeCorpusSearch(PASSAGES)
    deps = dataclasses.replace(make_deps(), corpus=corpus, corpus_version="v1")
    fact = _bilingual("Płaca minimalna wynosi 4806 zł", "The minimum wage is 4806 PLN")
    out = asyncio.run(search_corpus(state.model_copy(update={"claims": [fact]}), deps))
    assert [q for q, _ in corpus.queries] == [fact.claim, fact.claim_en]
    # The same passages from both queries are kept once, under the Polish claim.
    assert [p.passage.passage_id for p in out.passages[fact.claim]] == [
        "p0",
        "p1",
        "p2",
    ]


def test_search_web_sends_the_polish_and_the_english_query(
    state: CheckState, make_deps: MakeDeps
) -> None:
    web = FakeWebSearch()
    deps = dataclasses.replace(make_deps(), web_search=web)
    fact = _bilingual("Płaca minimalna wynosi 4806 zł", "The minimum wage is 4806 PLN")
    out = asyncio.run(search_web(state.model_copy(update={"claims": [fact]}), deps))
    assert sorted(web.queries) == sorted(fact.queries)
    assert out.web_search_calls == 2


def test_search_web_sends_the_models_keyword_queries_not_the_claim_text(
    state: CheckState, make_deps: MakeDeps
) -> None:
    web = FakeWebSearch()
    deps = dataclasses.replace(make_deps(), web_search=web)
    fact = _fact("Kwota wolna od podatku od 2026 wynosi 60 000 zł").model_copy(
        update={
            "search_queries": [
                "kwota wolna od podatku 2026",
                "tax-free allowance Poland 2026",
            ]
        }
    )
    asyncio.run(search_web(state.model_copy(update={"claims": [fact]}), deps))
    assert web.queries == [
        "kwota wolna od podatku 2026",
        "tax-free allowance Poland 2026",
    ]


def test_search_web_falls_back_to_the_claim_when_the_model_gave_no_queries(
    state: CheckState, make_deps: MakeDeps
) -> None:
    web = FakeWebSearch()
    deps = dataclasses.replace(make_deps(), web_search=web)
    fact = _fact("Warszawa jest stolicą Polski")
    asyncio.run(search_web(state.model_copy(update={"claims": [fact]}), deps))
    assert web.queries == [fact.claim]
