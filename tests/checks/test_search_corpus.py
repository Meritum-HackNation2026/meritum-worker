import asyncio
import dataclasses
from collections.abc import Callable
from datetime import UTC, date, datetime

from meritum_core.corpus import CorpusSearchPort
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank.fakes import FakeReranker
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    ExtractedClaim,
    FakeCorpusSearch,
    corpus_ports,
)
from meritum_worker.checks.constants import MAX_PARALLEL_CLAIMS
from meritum_worker.checks.steps import search_corpus

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
