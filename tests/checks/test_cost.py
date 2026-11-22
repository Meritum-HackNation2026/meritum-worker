import asyncio
from dataclasses import replace

import pytest
from meritum_core.checks.contracts import ModelUsage

from meritum_worker.checks import CheckState
from meritum_worker.checks.constants import NEWS_SEARCH_PRICE, WEB_SEARCH_PRICES
from meritum_worker.checks.steps import cost

from .conftest import MakeDeps

_LLM = ModelUsage(
    provider="vertex_ai",
    model="gemini-2.5-flash",
    region="europe-central2",
    input_tokens=12_000,
    output_tokens=1_500,
    cost_usd=0.0074,
)


def test_cost_adds_the_web_searches_priced_from_the_constants(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = replace(make_deps(), web_search_provider="vertex_search")
    spent = state.model_copy(update={"models": [_LLM], "web_search_calls": 2})
    out = asyncio.run(cost(spent, deps))
    price = WEB_SEARCH_PRICES["vertex_search"]
    assert out.models[0] == _LLM
    search = out.models[1]
    assert (search.provider, search.model, search.region) == (
        "vertex_search",
        price.model,
        price.region,
    )
    assert (search.input_tokens, search.output_tokens) == (0, 0)
    assert search.cost_usd == pytest.approx(2 * price.cost_usd)
    assert out.web_search_calls == 2


def test_cost_adds_nothing_without_web_searches(
    state: CheckState, make_deps: MakeDeps
) -> None:
    spent = state.model_copy(update={"models": [_LLM]})
    out = asyncio.run(cost(spent, make_deps()))
    assert out.models == [_LLM]


def test_cost_of_the_stub_search_is_zero(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(
        cost(state.model_copy(update={"web_search_calls": 3}), make_deps())
    )
    assert [m.cost_usd for m in out.models] == [0.0]


def test_a_media_search_is_priced_as_an_openrouter_exa_request(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = replace(
        make_deps(),
        web_search_provider="vertex_search",
        news_search_price=NEWS_SEARCH_PRICE,
    )
    spent = state.model_copy(update={"web_search_calls": 3, "news_search_calls": 1})
    catalogue, media = asyncio.run(cost(spent, deps)).models
    assert catalogue.cost_usd == pytest.approx(2 * 0.0015)
    assert (media.provider, media.model) == ("openrouter", "web-search-exa")
    assert media.cost_usd == pytest.approx(0.007)
