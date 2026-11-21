"""Steps for features/rerank.feature: Vertex AI and OpenRouter on a fake ranking API."""

import asyncio
import json
from datetime import UTC, date, datetime

import httpx2
from behave import given, then, when
from behave.runner import Context
from google.oauth2.credentials import Credentials
from meritum_core.corpus.models import Passage

from meritum_worker import corpus

CLAIM = "Woda z wodociągów w Krakowie nie nadaje się do picia"


def _ranking_api(request: httpx2.Request) -> httpx2.Response:
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
