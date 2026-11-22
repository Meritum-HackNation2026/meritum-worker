import asyncio
from collections.abc import Mapping
from pathlib import Path

import httpx2
import pytest
from meritum_core.corpus.catalog import load_catalog
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.embeddings import EmbeddingsPort, EmbeddingsUnavailableError

from meritum_worker.checks.constants import STEP_TIMEOUTS
from meritum_worker.corpus import (
    FactCheckAnswer,
    FactCheckPort,
    FactCheckSearch,
    FactCheckUnavailableError,
    FakeEmbeddings,
    search_fact_checks,
)
from meritum_worker.corpus.adapters import GoogleFactCheck
from meritum_worker.corpus.fact_check_constants import (
    FACT_CHECK_PARALLEL_QUERIES,
    FACT_CHECK_QUERIES_PER_CHECK,
    FACT_CHECK_TIMEOUT_SECONDS,
)

FIXTURES = Path(__file__).resolve().parents[2] / "features" / "fixtures"
CLAIM = "Tylko we Wrocławiu seniorzy po 65. roku życia jeżdżą komunikacją za darmo"
PHRASES = ["Wrocław darmowa komunikacja seniorzy", "65-latkowie komunikacja za darmo"]
DEMAGOG = (
    "Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli"
    " komunikacją miejską za darmo"
)
KRAKOW = "W Krakowie seniorzy po 70. roku życia jeżdżą komunikacją miejską za darmo"
VECTORS = {
    CLAIM: (1.0, 0.0, 0.0),
    DEMAGOG: (0.9, 0.43589, 0.0),  # cosine 0.9: the same claim, other words
    KRAKOW: (0.7, 0.0, 0.71414),  # cosine 0.7: related, another city
}


def _recorded(
    replies: Mapping[str, str], status: Mapping[str, int] | None = None
) -> tuple[GoogleFactCheck, list[str]]:
    asked: list[str] = []

    def reply(request: httpx2.Request) -> httpx2.Response:
        query = request.url.params["query"]
        asked.append(query)
        code = (status or {}).get(query, 200)
        fixture = replies.get(query, "fact_check_empty.json")
        return httpx2.Response(code, content=(FIXTURES / fixture).read_bytes())

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    return GoogleFactCheck("k-recorded", client), asked


def _search(
    port: FactCheckPort, embeddings: EmbeddingsPort | None = None
) -> FactCheckSearch:
    return asyncio.run(
        search_fact_checks(
            [CLAIM],
            port,
            NullPiiGate(),
            load_catalog(),
            phrases=[PHRASES],
            embeddings=embeddings or FakeEmbeddings(VECTORS),
        )
    )


def test_a_phrase_finds_the_demagog_rating_the_full_claim_misses() -> None:
    port, asked = _recorded({PHRASES[0]: "fact_check_demagog_wroclaw.json"})
    found = _search(port)
    assert sorted(asked) == sorted([CLAIM, *PHRASES])
    [finding] = found.findings
    assert (finding.found.publisher_id, finding.found.rating) == ("demagog", "Fałsz")
    assert finding.claim_reviewed == DEMAGOG
    assert finding.similar


def test_the_same_review_from_several_queries_is_kept_once() -> None:
    port, _ = _recorded(
        dict.fromkeys([CLAIM, *PHRASES], "fact_check_demagog_wroclaw.json")
    )
    found = _search(port)
    assert len(found.findings) == 1


def test_a_review_below_the_threshold_is_context_not_a_candidate() -> None:
    port, _ = _recorded({PHRASES[1]: "fact_check_demagog_krakow.json"})
    [finding] = _search(port).findings
    assert finding.claim_reviewed == KRAKOW
    assert not finding.similar


def test_an_unrelated_review_is_dropped() -> None:
    port, _ = _recorded({PHRASES[1]: "fact_check_demagog_krakow.json"})
    far = {**VECTORS, KRAKOW: (0.1, 0.0, 0.99499)}
    assert _search(port, FakeEmbeddings(far)).findings == []


def test_without_embeddings_every_review_goes_on_to_the_comparison() -> None:
    port, _ = _recorded({PHRASES[1]: "fact_check_demagog_krakow.json"})
    down = FakeEmbeddings(VECTORS, failure=EmbeddingsUnavailableError("down"))
    [finding] = _search(port, down).findings
    assert finding.similar


def test_a_failed_query_does_not_stop_the_others() -> None:
    port, _ = _recorded(
        {PHRASES[0]: "fact_check_demagog_wroclaw.json"}, status={CLAIM: 429}
    )
    assert len(_search(port).findings) == 1


def test_every_query_failed_is_unavailable() -> None:
    port, _ = _recorded({}, status=dict.fromkeys([CLAIM, *PHRASES], 503))
    with pytest.raises(FactCheckUnavailableError):
        _search(port)


class _SlowApi:
    def __init__(self) -> None:
        self.running = 0
        self.most = 0

    async def search(self, query: str, *, language: str) -> FactCheckAnswer:
        del query, language
        self.running += 1
        self.most = max(self.most, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1
        return FactCheckAnswer()


def test_the_queries_go_in_parallel() -> None:
    api = _SlowApi()
    _search(api)
    assert api.most == 1 + len(PHRASES)


def test_the_query_budget_fits_the_step_timeout() -> None:
    rounds = -(-FACT_CHECK_QUERIES_PER_CHECK // FACT_CHECK_PARALLEL_QUERIES)
    budget = STEP_TIMEOUTS["search_fact_checks"].total_seconds()
    assert rounds * FACT_CHECK_TIMEOUT_SECONDS < budget


def test_the_query_limit_holds_for_many_facts() -> None:
    port, asked = _recorded({})
    facts = [f"{CLAIM} numer {i}" for i in range(10)]
    asyncio.run(
        search_fact_checks(
            facts,
            port,
            NullPiiGate(),
            load_catalog(),
            phrases=[PHRASES] * 10,
            embeddings=FakeEmbeddings(VECTORS),
        )
    )
    assert len(asked) == FACT_CHECK_QUERIES_PER_CHECK
    assert set(facts) <= set(asked)  # every full claim before any phrase
