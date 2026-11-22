"""Steps for features/rerank.feature: Vertex AI and OpenRouter on a fake ranking API."""

import asyncio
import dataclasses
import json
from datetime import UTC, date, datetime

import httpx2
from behave import given, then, when
from behave.runner import Context
from check_support import RECEIVED_AT, deps
from google.oauth2.credentials import Credentials
from meritum_core.checks import CheckRequest
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank.fakes import FakeReranker
from meritum_core.jobs.contracts import CheckInput

from meritum_worker import corpus
from meritum_worker.checks import CheckState, ExtractedClaim, FakeCorpusSearch
from meritum_worker.checks.steps import search_corpus

CLAIM = "Woda z wodociągów w Krakowie nie nadaje się do picia"
_SENT: list[httpx2.Request] = []


def _ranking_api(request: httpx2.Request) -> httpx2.Response:
    _SENT.append(request)
    # Ranks the search order upside down: the last passage is the most relevant.
    sent = json.loads(request.content)
    if "documents" in sent:  # OpenRouter: index into the documents sent
        results = [
            {"index": i, "relevance_score": i / 100, "document": {"text": d}}
            for i, d in enumerate(sent["documents"])
        ]
        return httpx2.Response(200, json={"model": sent["model"], "results": results})
    records = sent["records"]
    scored = [{"id": r["id"], "score": int(r["id"]) / 100} for r in records]
    return httpx2.Response(200, json={"records": scored})


def _ranking_api_down(_request: httpx2.Request) -> httpx2.Response:
    return httpx2.Response(503, json={"error": {"code": 503}})


@given("MERITUM_RERANKER={provider} i twierdzenie z {count:d} fragmentami")
def provider_and_passages(context: Context, provider: str, count: int) -> None:
    context.reranker_settings = corpus.RerankerSettings.model_validate(
        {
            "MERITUM_RERANKER": provider,
            "project": "meritum-test",
            "api_token": "fake",
            "retries": 1,
        }
    )
    context.ranking_api = _ranking_api
    context.passages = [
        Passage(
            passage_id=f"p{i}",
            source_id=f"src-{i}",
            text=f"Fragment {i} o wodzie w Krakowie.",
            published_on=date(2026, 11, 1),
            fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
            score=(count - i) / 100,
        )
        for i in range(count)
    ]


def _passages(count: int) -> list[Passage]:
    return [
        Passage(
            passage_id=f"p{i}",
            source_id=f"src-{i}",
            text=f"Fragment {i} o wodzie w Krakowie.",
            published_on=date(2026, 11, 1),
            fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
            score=(count - i) / 100,
        )
        for i in range(count)
    ]


@given("MERITUM_RERANKER=openrouter bez własnego tokenu i z kluczem OPENROUTER_API_KEY")
def openrouter_with_the_model_key(context: Context) -> None:
    context.reranker_settings = corpus.RerankerSettings.model_validate(
        {
            "MERITUM_RERANKER": "openrouter",
            "OPENROUTER_API_KEY": "or-model",
            "retries": 1,
        }
    )
    context.ranking_api = _ranking_api
    context.passages = _passages(20)
    _SENT.clear()


@then("reranker wysyła klucz modelu w nagłówku Authorization")
def sends_the_model_key(context: Context) -> None:
    assert [r.headers["Authorization"] for r in _SENT] == ["Bearer or-model"]
    assert context.reranking.retrieval_errors == []


@given("migawkę korpusu z {count:d} fragmentami pasującymi do twierdzenia")
def snapshot_with_passages(context: Context, count: int) -> None:
    context.corpus = FakeCorpusSearch(_passages(count))
    context.fake_reranker = FakeReranker({"p29": 0.9, "p30": 1.0})


@when("krok search_corpus szuka dowodów dla twierdzenia")
def search_corpus_runs(context: Context) -> None:
    fact = ExtractedClaim(
        claim=CLAIM,
        kind="fact",
        explanation="Twierdzenie o jakości wody, które da się sprawdzić.",
        claim_date=RECEIVED_AT.date(),
        claim_date_source="today",
    )
    job = CheckInput(
        request=CheckRequest(channel="web", text=CLAIM),
        session_id="session-behave-1",
        received_at=RECEIVED_AT,
    )
    check_deps = dataclasses.replace(
        deps("claims_four_facts.json"),
        corpus=context.corpus,
        reranker=context.fake_reranker,
        corpus_version="v1",
    )
    state = CheckState(check_id="check-1", job=job, claims=[fact])
    context.found = asyncio.run(search_corpus(state, check_deps)).passages[CLAIM]


@then("każde zapytanie do korpusu prosi o {limit:d} fragmentów")
def every_query_asks_for(context: Context, limit: int) -> None:
    assert context.corpus.limits
    assert set(context.corpus.limits) == {limit}


@then("reranker zostawia {count:d} fragmentów")
def reranker_keeps(context: Context, count: int) -> None:
    # p29 is the 30th candidate: it is first only when 30 reached the reranker.
    assert context.found[0].passage.passage_id == "p29"
    assert len(context.found) == count


@given("dostawca rerankera nie odpowiada")
def provider_down(context: Context) -> None:
    context.ranking_api = _ranking_api_down


@when("krok badań woła reranker")
def research_step_reranks(context: Context) -> None:
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(context.ranking_api))
    token = Credentials(token="fake")  # ruff: ignore[hardcoded-password-func-arg]  # fake token, no network
    reranker = corpus.build_reranker(
        context.reranker_settings, credentials=token, http_client=client
    )
    context.reranking = asyncio.run(
        corpus.rerank_passages(reranker, CLAIM, context.passages)
    )


@then("dostaje fragmenty z oceną w kolejności trafności")
def ranked_by_relevance(context: Context) -> None:
    ranked = context.reranking.passages
    assert [r.passage.passage_id for r in ranked] == ["p19", "p18", "p17", "p16", "p15"]
    relevance = [r.relevance for r in ranked]
    assert relevance == sorted(relevance, reverse=True)
    assert context.reranking.retrieval_errors == []


@then(
    "dostaje fragmenty w kolejności z wyszukiwania, a błąd trafia do retrieval_errors"
)
def search_order_and_error(context: Context) -> None:
    ids = [r.passage.passage_id for r in context.reranking.passages]
    assert ids == ["p0", "p1", "p2", "p3", "p4"]
    assert context.reranking.retrieval_errors == ["search_corpus: reranker_unavailable"]
