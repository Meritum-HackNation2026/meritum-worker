"""Steps of the phrase-query fact-check scenarios in features/corpus.feature.

The Fact Check Tools API is recorded per query behind the real adapter, the
embeddings are a table; no network.
"""

import asyncio
import time
from datetime import date
from pathlib import Path

import httpx2
from behave import given, then
from behave.runner import Context
from pydantic import SecretStr

from meritum_worker.checks import ExtractedClaim, FakePageFetcher
from meritum_worker.checks.constants import STEP_TIMEOUTS
from meritum_worker.checks.factory import build_fact_check
from meritum_worker.corpus import (
    FactCheckAnswer,
    FactCheckPort,
    FactCheckProvider,
    FactCheckSettings,
    FakeEmbeddings,
)
from meritum_worker.evidence.constants import REVIEW_MATCH_INSTRUCTIONS

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
PHRASES = [
    "Wrocław darmowa komunikacja seniorzy",
    "65-latkowie komunikacja za darmo",
    "Wrocław seniorzy 65 lat",
]
KRAKOW = "W Krakowie seniorzy po 70. roku życia jeżdżą komunikacją miejską za darmo"
REVIEWED = (
    "Wrocław był jedynym miastem w Polsce, w którym 65-latkowie jeździli"
    " komunikacją miejską za darmo"
)


def _fact(claim: str, phrases: list[str]) -> ExtractedClaim:
    return ExtractedClaim(
        claim=claim,
        kind="fact",
        explanation="Twierdzenie o przepisach, które da się sprawdzić.",
        fact_check_phrases=phrases,
        claim_date=date(2024, 3, 1),
        claim_date_source="text",
    )


def _recorded(replies: dict[str, str]) -> FactCheckPort:
    def reply(request: httpx2.Request) -> httpx2.Response:
        fixture = replies.get(request.url.params["query"], "fact_check_empty.json")
        return httpx2.Response(200, content=(FIXTURES / fixture).read_bytes())

    client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
    settings = FactCheckSettings(
        provider=FactCheckProvider.GOOGLE, api_key=SecretStr("k-recorded")
    )
    return build_fact_check(settings, client)


def _setup(
    context: Context, claim: str, phrases: list[str], api: FactCheckPort
) -> None:
    context.api = api
    context.pages = FakePageFetcher()
    context.same_claim = True
    context.fact = _fact(claim, phrases)
    context.stances = {}
    context.embeddings = FakeEmbeddings(
        {
            claim: (1.0, 0.0, 0.0),
            REVIEWED: (0.9, 0.43589, 0.0),  # a paraphrase: cosine 0.9
            KRAKOW: (0.7, 0.0, 0.71414),  # another city: cosine 0.7
        }
    )


@given('twierdzenie "{claim}" z frazami kluczowymi')
def claim_with_phrases(context: Context, claim: str) -> None:
    _setup(context, claim, PHRASES[:2], _recorded({}))


@given('Demagog ocenił twierdzenie "{reviewed}" jako "{rating}"')
def demagog_rated_other_words(context: Context, reviewed: str, rating: str) -> None:
    assert (reviewed, rating) == (REVIEWED, "Fałsz")  # the recorded reply
    context.api = _recorded({PHRASES[0]: "fact_check_demagog_wroclaw.json"})


@given("API zwraca ClaimReview o darmowej komunikacji dla seniorów w innym mieście")
def another_city(context: Context) -> None:
    context.api = _recorded({PHRASES[1]: "fact_check_demagog_krakow.json"})


class _SlowApi:
    def __init__(self) -> None:
        self.running = 0
        self.most = 0

    async def search(self, query: str, *, language: str) -> FactCheckAnswer:
        del query, language
        self.running += 1
        self.most = max(self.most, self.running)
        await asyncio.sleep(0.05)
        self.running -= 1
        return FactCheckAnswer()


@given('twierdzenie "{claim}" z trzema frazami kluczowymi')
def claim_with_three_phrases(context: Context, claim: str) -> None:
    _setup(context, claim, PHRASES, _SlowApi())
    context.started = time.monotonic()


@then('wyniki zawierają ClaimReview Demagogu z textualRating "{rating}"')
def demagog_found(context: Context, rating: str) -> None:
    [premise] = context.claim.claim_review_premises
    assert (premise.publisher, premise.rating) == ("Stowarzyszenie Demagog", rating)
    assert context.claim.verdict == "false"


@then("podobieństwo jest poniżej progu, a ocena zostaje kontekstem z linkiem")
def other_city_is_context(context: Context) -> None:
    assert context.claim.claim_review_premises == []
    [review] = context.claim.claim_reviews
    assert "krakow" in str(review.url)
    asked = [p.instructions for p in context.deps.llm.prompts]
    assert REVIEW_MATCH_INSTRUCTIONS not in asked  # the model never compared it


@then(
    'zapytania idą równolegle, a krok "{code}" mieści się w limicie czasu kroku'
    " z constants.py"
)
def queries_in_parallel(context: Context, code: str) -> None:
    assert context.api.most == 1 + len(PHRASES)
    assert time.monotonic() - context.started < STEP_TIMEOUTS[code].total_seconds()
