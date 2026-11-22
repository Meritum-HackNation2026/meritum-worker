import asyncio
from pathlib import Path

import httpx2
import pytest
from meritum_core.corpus.catalog import load_catalog
from meritum_core.security.pii import NullPiiGate

from meritum_worker.checks.factory import build_fact_check
from meritum_worker.corpus import (
    FactCheckAnswer,
    FactCheckProvider,
    FactCheckSettings,
    FactCheckUnavailableError,
    FakeFactCheck,
    search_fact_checks,
)
from meritum_worker.corpus.adapters import GoogleFactCheck

FIXTURES = Path(__file__).resolve().parents[2] / "features" / "fixtures"
CLAIM = "PAP usunęła depeszę o wypowiedzi posła przed wyborami"


def _google(
    status: int, fixture: str | None, key: str = "k-recorded"
) -> tuple[GoogleFactCheck, list[httpx2.Request]]:
    sent: list[httpx2.Request] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        body = (FIXTURES / fixture).read_bytes() if fixture is not None else b"oops"
        return httpx2.Response(
            status, content=body, headers={"Cache-Control": "public, max-age=600"}
        )

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    return GoogleFactCheck(key, client), sent


def test_the_api_reply_becomes_hits_with_the_cache_header() -> None:
    port, sent = _google(200, "fact_check_demagog.json")
    answer = asyncio.run(port.search(CLAIM, language="pl"))
    assert [h.rating for h in answer.hits] == ["Fałsz", "Fałsz"]
    assert answer.hits[0].site == "demagog.org.pl"
    assert answer.cache_control == "public, max-age=600"
    [request] = sent
    assert request.url.params["query"] == CLAIM
    assert "key" not in request.url.params  # the key travels in a header
    assert request.headers["X-Goog-Api-Key"] == "k-recorded"


def test_an_empty_reply_is_no_review_not_a_failure() -> None:
    port, _ = _google(200, "fact_check_empty.json")
    assert asyncio.run(port.search(CLAIM, language="pl")).hits == []


@pytest.mark.parametrize(
    ("status", "fixture", "key"),
    [
        (403, None, "k"),
        (429, None, "k"),
        (500, None, "k"),
        (200, None, "k"),
        (200, "fact_check_empty.json", ""),
    ],
)
def test_access_error_quota_bad_answer_or_no_key_is_unavailable(
    status: int, fixture: str | None, key: str
) -> None:
    port, sent = _google(status, fixture, key)
    with pytest.raises(FactCheckUnavailableError) as raised:
        asyncio.run(port.search(CLAIM, language="pl"))
    assert "k-recorded" not in str(raised.value)
    assert bool(sent) == bool(key)  # no key: nothing is sent


def test_only_publishers_of_the_catalogue_are_kept_and_demagog_is_never_fetched() -> (
    None
):
    port, _ = _google(200, "fact_check_demagog.json")
    found = asyncio.run(
        search_fact_checks([CLAIM], port, NullPiiGate(), load_catalog())
    )
    [finding] = found.findings
    assert finding.found.publisher_id == "demagog"
    assert finding.found.signatory_of == ["ifcn", "efcsn"]
    assert finding.found.rating == "Fałsz"
    assert finding.claim_reviewed.startswith("PAP usunęła")
    assert found.article_urls == []  # demagog.org.pl is excluded from fetching


def test_a_fact_check_on_a_catalogue_domain_may_be_fetched() -> None:
    hit = asyncio.run(
        _google(200, "fact_check_demagog.json")[0].search(CLAIM, language="pl")
    ).hits[0]
    moved = hit.model_copy(
        update={"url": "https://fakenews.pl/art", "site": "fakenews.pl"}
    )
    port = FakeFactCheck(FactCheckAnswer(hits=[moved]))
    found = asyncio.run(
        search_fact_checks([CLAIM], port, NullPiiGate(), load_catalog())
    )
    assert found.article_urls == ["https://fakenews.pl/art"]


def test_the_stub_provider_finds_no_review() -> None:
    port = build_fact_check(FactCheckSettings(provider=FactCheckProvider.STUB))
    assert asyncio.run(port.search(CLAIM, language="pl")).hits == []
