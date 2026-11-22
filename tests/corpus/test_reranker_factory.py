"""Reranker settings and factory: MERITUM_RERANKER picks it, null gate by default."""

import asyncio
from datetime import UTC, date, datetime

import httpx2
import pytest
from meritum_core.corpus.models import Passage
from meritum_core.corpus.rerank import NullReranker, RerankerPort
from pydantic import ValidationError

from meritum_worker.corpus import RerankerProvider, RerankerSettings, build_reranker

_PASSAGE = Passage(
    passage_id="p0",
    source_id="src-0",
    text="Art. 96. 1. Sejm składa się z 460 posłów.",
    published_on=date(2026, 11, 1),
    fetched_at=datetime(2026, 11, 21, tzinfo=UTC),
    score=1.0,
)


def test_no_configuration_builds_the_null_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MERITUM_RERANKER", raising=False)
    assert isinstance(build_reranker(RerankerSettings()), NullReranker)
    assert isinstance(build_reranker(), NullReranker)


def test_provider_comes_from_meritum_reranker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERITUM_RERANKER", "vertex")
    monkeypatch.setenv("MERITUM_RERANKER_PROJECT", "meritum-dev")
    monkeypatch.setenv("MERITUM_RERANKER_LOCATION", "eu")
    settings = RerankerSettings()
    assert settings.provider is RerankerProvider.VERTEX
    assert settings.location == "eu"
    reranker = build_reranker(settings)
    assert isinstance(reranker, RerankerPort)
    assert not isinstance(reranker, NullReranker)


def test_workers_ai_token_is_not_shown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MERITUM_RERANKER", "workers_ai")
    monkeypatch.setenv("MERITUM_RERANKER_ACCOUNT_ID", "acc123")
    monkeypatch.setenv("MERITUM_RERANKER_API_TOKEN", "cf-token")
    settings = RerankerSettings()
    assert settings.provider is RerankerProvider.WORKERS_AI
    assert "cf-token" not in repr(settings)


@pytest.mark.parametrize(
    ("provider", "missing"),
    [
        (RerankerProvider.VERTEX, "MERITUM_RERANKER_PROJECT"),
        (RerankerProvider.WORKERS_AI, "MERITUM_RERANKER_API_TOKEN"),
        (RerankerProvider.OPENROUTER, "MERITUM_RERANKER_API_TOKEN"),
    ],
)
def test_provider_without_its_settings_is_rejected(
    monkeypatch: pytest.MonkeyPatch, provider: RerankerProvider, missing: str
) -> None:
    for name in ("PROJECT", "ACCOUNT_ID", "API_TOKEN"):
        monkeypatch.delenv(f"MERITUM_RERANKER_{name}", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValidationError, match=missing):
        RerankerSettings(provider=provider, account_id="a")


def test_openrouter_model_id_may_hold_a_dot() -> None:
    settings = RerankerSettings.model_validate(
        {"provider": "openrouter", "api_token": "k", "model": "cohere/rerank-v3.5"}
    )
    assert settings.model == "cohere/rerank-v3.5"
    with pytest.raises(ValidationError, match="model"):
        RerankerSettings.model_validate(
            {"provider": "openrouter", "api_token": "k", "model": "a b"}
        )


def test_unknown_provider_is_rejected() -> None:
    with pytest.raises(ValidationError):
        RerankerSettings(provider="cohere")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("project", "p/../../other"),
        ("account_id", "acc?x=1"),
        ("location", "eu.evil.example"),
        ("model", "@cf/../x"),
        ("model", "@cf/baai/bge-reranker-base\n"),
    ],
)
def test_setting_that_would_change_the_url_is_rejected(field: str, value: str) -> None:
    with pytest.raises(ValidationError, match=field):
        RerankerSettings.model_validate(
            {"provider": "vertex", "project": "p", field: value}
        )


def _openrouter_sent(settings: RerankerSettings) -> list[httpx2.Request]:
    sent: list[httpx2.Request] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return httpx2.Response(200, json={"model": "m", "results": []})

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    reranker = build_reranker(settings, http_client=client)
    asyncio.run(reranker.rerank("Sejm ma 460 posłów.", [_PASSAGE], limit=1))
    return sent


def test_openrouter_without_its_own_token_uses_the_model_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # worker#248: the deploy passes only OPENROUTER_API_KEY; dev had no reranker.
    monkeypatch.setenv("MERITUM_RERANKER", "openrouter")
    monkeypatch.delenv("MERITUM_RERANKER_API_TOKEN", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-model-key")
    settings = RerankerSettings()
    assert "or-model-key" not in repr(settings)
    [request] = _openrouter_sent(settings)
    assert request.headers["Authorization"] == "Bearer or-model-key"


def test_openrouter_own_token_wins_over_the_model_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MERITUM_RERANKER", "openrouter")
    monkeypatch.setenv("MERITUM_RERANKER_API_TOKEN", "or-reranker-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "or-model-key")
    [request] = _openrouter_sent(RerankerSettings())
    assert request.headers["Authorization"] == "Bearer or-reranker-key"
