"""RerankerPort contract for both provider adapters, on recorded replies."""

import asyncio
import json
from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx2
import pytest
from google.oauth2.credentials import Credentials
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import RerankerPort
from meritum_core.corpus.rerank.contract import reranker_contract_violations
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.corpus import RerankerProvider, RerankerSettings, build_reranker

# (fixture of the provider, recorded ranking, ranking naming an unknown passage)
PROVIDERS = [
    ("vertex", "vertex-ranking.json", "vertex-ranking-unknown-id.json"),
    ("workers_ai", "workers-ai-rerank.json", "workers-ai-rerank-unknown-id.json"),
    ("openrouter", "openrouter-rerank.json", "openrouter-rerank-unknown-id.json"),
]
type RerankerFactory = Callable[
    [list[tuple[int, str] | Exception]], tuple[RerankerPort, list[httpx2.Request]]
]
type Provider = tuple[RerankerFactory, str, str]

CLAIM = "Woda z wodociągów w Krakowie nie nadaje się do picia"


@pytest.fixture(params=PROVIDERS, ids=[p[0] for p in PROVIDERS])
def provider(request: pytest.FixtureRequest) -> Provider:
    name, ranking, unknown = request.param
    return request.getfixturevalue(name), ranking, unknown


def _passages(count: int = 5) -> list[Passage]:
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


def test_adapter_meets_the_core_contract(provider: Provider) -> None:
    build, ranking, _ = provider
    reranker, _ = build([(200, ranking)])
    assert isinstance(reranker, RerankerPort)
    assert asyncio.run(reranker_contract_violations(reranker)) == []


def test_passages_come_back_in_the_provider_order_cut_to_the_limit(
    provider: Provider,
) -> None:
    build, ranking, _ = provider
    reranker, sent = build([(200, ranking)])
    passages = _passages()
    ranked = asyncio.run(reranker.rerank(CLAIM, passages, limit=3))
    assert [r.passage.passage_id for r in ranked] == ["p2", "p0", "p4"]
    assert ranked[0].relevance > ranked[1].relevance > ranked[2].relevance
    assert len(sent) == 1


def test_no_passages_make_no_call(provider: Provider) -> None:
    build, ranking, _ = provider
    reranker, sent = build([(200, ranking)])
    assert asyncio.run(reranker.rerank(CLAIM, [], limit=3)) == []
    assert sent == []


def test_transient_error_is_retried(provider: Provider) -> None:
    build, ranking, _ = provider
    reranker, sent = build([(503, "malformed.json"), (200, ranking)])
    assert len(asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))) == 3
    assert len(sent) == 2


@pytest.mark.parametrize(
    ("reply", "calls"),
    [
        (httpx2.ConnectError("no reply"), 2),
        (httpx2.ReadTimeout("too slow"), 2),
        (httpx2.DecodingError("broken gzip"), 1),
        ((503, "malformed.json"), 2),
        ((403, "malformed.json"), 1),
        ((200, "malformed.json"), 1),
    ],
    ids=["no-reply", "timeout", "undecodable", "unavailable", "refused", "malformed"],
)
def test_failure_raises_provider_unavailable(
    provider: Provider, reply: tuple[int, str] | Exception, calls: int
) -> None:
    build, _, _ = provider
    reranker, sent = build([reply])
    with pytest.raises(ProviderUnavailableError) as raised:
        asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))
    assert CLAIM not in str(raised.value)
    assert len(sent) == calls


def test_ranking_of_an_unknown_passage_is_a_provider_failure(
    provider: Provider,
) -> None:
    build, _, unknown = provider
    reranker, _ = build([(200, unknown)])
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))


def test_vertex_request_names_project_location_model_and_top_n(
    vertex: RerankerFactory,
) -> None:
    reranker, sent = vertex([(200, "vertex-ranking.json")])
    asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))
    [request] = sent
    assert str(request.url) == (
        "https://discoveryengine.googleapis.com/v1/projects/meritum-test"
        "/locations/global/rankingConfigs/default_ranking_config:rank"
    )
    assert request.headers["Authorization"] == "Bearer recorded"
    assert request.headers["X-Goog-User-Project"] == "meritum-test"
    body = json.loads(request.content)
    assert body["query"] == CLAIM
    assert body["topN"] == 3
    assert body["model"] == "semantic-ranker-default-005"
    assert body["ignoreRecordDetailsInResponse"] is True
    assert body["records"][1] == {
        "id": "1",
        "content": "Fragment 1 o wodzie w Krakowie.",
    }


def test_workers_ai_request_names_account_model_and_top_k(
    workers_ai: RerankerFactory,
) -> None:
    reranker, sent = workers_ai([(200, "workers-ai-rerank.json")])
    asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))
    [request] = sent
    assert str(request.url) == (
        "https://api.cloudflare.com/client/v4/accounts/acc123"
        "/ai/run/@cf/baai/bge-reranker-base"
    )
    assert request.headers["Authorization"] == "Bearer cf-recorded"
    body = json.loads(request.content)
    assert body["query"] == CLAIM
    assert body["top_k"] == 3
    assert body["contexts"][1] == {"text": "Fragment 1 o wodzie w Krakowie."}


def test_openrouter_request_asks_for_zdr_and_no_data_collection(
    openrouter: RerankerFactory,
) -> None:
    reranker, sent = openrouter([(200, "openrouter-rerank.json")])
    asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))
    [request] = sent
    assert str(request.url) == "https://openrouter.ai/api/v1/rerank"
    assert request.headers["Authorization"] == "Bearer or-recorded"
    body = json.loads(request.content)
    assert body["model"] == "cohere/rerank-v3.5"
    assert body["query"] == CLAIM
    assert body["top_n"] == 3
    assert body["documents"][1] == "Fragment 1 o wodzie w Krakowie."
    assert body["provider"] == {"zdr": True, "data_collection": "deny"}


def test_openrouter_refusing_a_model_without_zdr_is_a_provider_failure(
    openrouter: RerankerFactory,
) -> None:
    reranker, sent = openrouter([(404, "openrouter-no-zdr.json")])
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(reranker.rerank(CLAIM, _passages(), limit=3))
    assert len(sent) == 1


def test_vertex_location_other_than_global_uses_its_regional_host() -> None:
    sent: list[httpx2.Request] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json={"records": [{"id": "0", "score": 0.5}]})

    settings = RerankerSettings(
        provider=RerankerProvider.VERTEX, project="meritum-test", location="eu"
    )
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    token = Credentials(token="recorded")  # ruff: ignore[hardcoded-password-func-arg]  # fake token, no network
    reranker = build_reranker(settings, credentials=token, http_client=client)
    asyncio.run(reranker.rerank(CLAIM, _passages(1), limit=1))
    assert str(sent[0].url).startswith(
        "https://eu-discoveryengine.googleapis.com/v1/projects/meritum-test/locations/eu/"
    )
