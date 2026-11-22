"""The last-resort search in major media, when no source settled the fact."""

import asyncio
import dataclasses

import pytest
from meritum_core.checks.contracts import Stance
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage, FetchPurpose
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.evidence import CitationDraft
from tests.checks.conftest import MakeDeps

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.news import news_catalog
from meritum_worker.checks.steps import search_news
from meritum_worker.corpus import FakeWebSearch
from meritum_worker.evidence import AssessedCitation, RecordedLlm, StanceJudgement

URL = "https://tg24.sky.it/cronaca/2026/11/18/sciopero-20-novembre-2026"
TEXT = "Sciopero generale proclamato per il 20 novembre 2026."


class _Pages:
    async def fetch(  # ruff: ignore[no-self-use]  # same signature as the port
        self, url: str, *, purpose: FetchPurpose
    ) -> FetchedPage:
        del purpose
        return FetchedPage(url=url, content_type="text/html", untrusted_text=TEXT)


def _deps(make_deps: MakeDeps) -> tuple[CheckDeps, FakeWebSearch]:
    news = FakeWebSearch(
        (WebSearchCandidate(url=URL, domain="tg24.sky.it", publisher_id="sky-tg24"),)
    )
    stance = StanceJudgement.model_validate(
        {"relevant": True, "fragment": TEXT, "stance": "supports"}
    )
    deps = dataclasses.replace(
        make_deps(),
        llm=RecordedLlm({TEXT: stance}),
        news_search=news,
        pages=_Pages(),
        catalog=(*load_catalog(), *news_catalog()),
    )
    return deps, news


def _assessed(stance: Stance) -> AssessedCitation:
    draft = CitationDraft(source_id="doc-gov", fragment="Fragment.", stance=stance)
    return AssessedCitation(fact=0, draft=draft)


def test_a_fact_no_source_settled_gets_one_media_search_and_the_page_is_assessed(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps, news = _deps(make_deps)
    # The corpus gave a passage, but it only adds context (worker#275).
    unsettled = state.model_copy(update={"assessed": [_assessed("context")]})
    out = asyncio.run(search_news(unsettled, deps))
    (document,) = out.evidence
    assert (document.source.publisher, document.source.kind, document.source.tier) == (
        "Sky TG24",
        "media",
        "secondary",
    )
    _, cited = out.assessed
    assert (cited.fact, cited.draft.source_id, cited.draft.stance) == (
        0,
        document.source.id,
        "supports",
    )
    assert cited.draft.fragment in document.text
    assert len(news.queries) == 1
    assert out.web_search_calls == state.web_search_calls + 1
    assert out.news_search_calls == 1
    assert len(out.models) == len(state.models) + 1


@pytest.mark.parametrize("stance", ["supports", "refutes"])
def test_media_are_not_asked_when_a_source_settled_the_fact(
    stance: Stance, state: CheckState, make_deps: MakeDeps
) -> None:
    deps, news = _deps(make_deps)
    settled = state.model_copy(update={"assessed": [_assessed(stance)]})
    assert asyncio.run(search_news(settled, deps)) == settled
    assert news.queries == []


def test_the_list_holds_the_agreed_outlets_as_secondary_media() -> None:
    entries = news_catalog()
    assert len(entries) == 21
    assert {(e.kind, e.tier, e.ingest) for e in entries} == {
        ("media", "secondary", "live")
    }
