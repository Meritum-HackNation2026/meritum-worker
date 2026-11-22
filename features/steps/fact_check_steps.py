"""Steps of the fact-check scenarios in features/corpus.feature.

The check runs inline on recorded model answers and recorded Fact Check Tools API
replies behind the real adapter; no network, no database.
"""

import asyncio
import dataclasses
from datetime import UTC, date, datetime
from pathlib import Path

import httpx2
from behave import given, then, when
from behave.runner import Context
from meritum_core.checks import CheckRequest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.corpus.catalog import load_catalog
from meritum_core.corpus.fetching import FetchedPage
from meritum_core.jobs.contracts import CheckInput
from meritum_core.security.pii import NullPiiGate
from pydantic import SecretStr

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    ClaimExtraction,
    ExtractedClaim,
    FakePageFetcher,
    InlineCheckRuntime,
    audio_ports,
    corpus_ports,
    run_check,
    web_ports,
)
from meritum_worker.checks.factory import build_fact_check
from meritum_worker.corpus import (
    FactCheckPort,
    FactCheckProvider,
    FactCheckSettings,
)
from meritum_worker.evidence import (
    ClaimExplanation,
    RecordedLlm,
    ReviewMatch,
    StanceJudgement,
)

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
CLAIM = "PAP usunęła depeszę o wypowiedzi posła przed wyborami 15 października 2023"
ARTICLE = "PAP nie usunęła depeszy o wypowiedzi posła przed wyborami w październiku."
ARTICLE_URL = "https://fakenews.pl/art"
FACT = ExtractedClaim(
    claim=CLAIM,
    kind="fact",
    explanation="Twierdzenie o zdarzeniu, które da się sprawdzić.",
    claim_date=date(2023, 10, 15),
    claim_date_source="text",
)
EXPLAINED = ClaimExplanation(
    explanation="Ocena fact-checkera prowadzi do tego werdyktu.",
    unresolved="Brak innych źródeł rozstrzygających twierdzenie.",
)


def _api(status: int, fixture: str | None) -> FactCheckPort:
    body = b"" if fixture is None else (FIXTURES / fixture).read_bytes()
    reply = httpx2.Response(
        status, content=body, headers={"Cache-Control": "max-age=3600"}
    )
    client = httpx2.AsyncClient(transport=httpx2.MockTransport(lambda _: reply))
    settings = FactCheckSettings(
        provider=FactCheckProvider.GOOGLE, api_key=SecretStr("k-recorded")
    )
    return build_fact_check(settings, client)


def _setup(
    context: Context, api: FactCheckPort, pages: FakePageFetcher | None = None
) -> None:
    context.same_claim = True
    context.api = api
    context.pages = pages or FakePageFetcher()
    context.stances = {}


@given('pytanie o depeszę PAP i API Fact Check z oceną Demagogu "Fałsz"')
def demagog_rating(context: Context) -> None:
    _setup(context, _api(200, "fact_check_demagog.json"))


@given("pytanie o depeszę PAP i API Fact Check bez żadnej oceny")
def no_rating(context: Context) -> None:
    _setup(context, _api(200, "fact_check_empty.json"))


@given("pytanie o depeszę PAP i API Fact Check zwraca błąd dostępu")
def api_denied(context: Context) -> None:
    _setup(context, _api(403, None))


@given("pytanie o depeszę PAP i ClaimReview wskazuje artykuł z fakenews.pl")
def catalogue_article(context: Context) -> None:
    page = FetchedPage(
        url=ARTICLE_URL, content_type="text/html", untrusted_text=ARTICLE
    )
    _setup(context, _api(200, "fact_check_fakenews.json"), FakePageFetcher(page))
    context.stances = {
        ARTICLE: StanceJudgement(relevant=True, fragment=ARTICLE, stance="refutes")
    }


@given("model uznaje, że oceniane twierdzenie jest inne niż nasze")
def other_claim(context: Context) -> None:
    context.same_claim = False


@when("system bada twierdzenie z oceną fact-checkera")
def check_runs(context: Context) -> None:
    llm = RecordedLlm(
        context.stances,
        ClaimExtraction(out_of_scope=False, claims=[getattr(context, "fact", FACT)]),
        ReviewMatch(same_claim=context.same_claim),
        AnswerDraft(claims=[EXPLAINED], limitations=["Sprawdzono indeks ocen."]),
    )
    context.deps = CheckDeps(
        llm=llm,
        records=InMemoryCheckRecordRepository(),
        pages=context.pages,
        pii=NullPiiGate(),
        **audio_ports(),
        **corpus_ports(),
        **web_ports(),
    )
    context.deps = dataclasses.replace(
        context.deps,
        catalog=load_catalog(),
        fact_check=context.api,
        embeddings=getattr(context, "embeddings", None),
    )
    job = CheckInput(
        request=CheckRequest(channel="web", text=getattr(context, "fact", FACT).claim),
        session_id="session-behave-fc",
        received_at=datetime(2026, 1, 5, 12, 0, tzinfo=UTC),
    )
    context.runtime = InlineCheckRuntime()
    output = asyncio.run(
        run_check(
            job.model_dump(mode="json"), "check-fc-1", context.deps, context.runtime
        )
    )
    context.result = output.result
    context.claim = output.result.claims[0]


def _step_state(context: Context, code: str) -> str:
    last = context.runtime.published[-1]
    return next(s.status for s in last.steps if s.code == code)


@then(
    'werdykt to "false" z przesłanką: Demagog, "Fałsz", tytuł, data i link,'
    " bez fragmentu strony"
)
def premise_of_demagog(context: Context) -> None:
    claim = context.claim
    assert claim.verdict == "false"
    [premise] = claim.claim_review_premises
    assert (premise.publisher, premise.rating) == ("Stowarzyszenie Demagog", "Fałsz")
    assert premise.title
    assert premise.reviewed_at
    assert str(premise.url)
    assert claim.citations == []


@then("żaden artykuł Demagogu nie jest pobierany")
def demagog_not_fetched(context: Context) -> None:
    assert context.pages.calls == []


@then(
    "ocena Demagogu jest tylko kontekstem z linkiem,"
    ' a werdykt to "insufficient_evidence"'
)
def demagog_is_context(context: Context) -> None:
    claim = context.claim
    assert claim.verdict == "insufficient_evidence"
    assert claim.claim_review_premises == []
    [review] = claim.claim_reviews
    assert str(review.url).startswith("https://demagog.org.pl/")


@then('krok "{code}" ma stan "{status}" i nie ma ograniczenia "fact_check_unavailable"')
def step_done_without_limitation(context: Context, code: str, status: str) -> None:
    assert _step_state(context, code) == status
    assert "fact_check_unavailable" not in context.result.limitation_codes


@then('sprawdzenie kończy się bez tej przesłanki, a wynik ma kod ograniczenia "{code}"')
def check_without_premise(context: Context, code: str) -> None:
    assert context.result.status == "done"
    assert context.claim.claim_review_premises == []
    assert code in context.result.limitation_codes


@then('krok "{code}" ma stan "{status}"')
def step_has_state(context: Context, code: str, status: str) -> None:
    assert _step_state(context, code) == status


@then("żaden komunikat nie mówi, że takiego artykułu nie ma")
def never_says_it_does_not_exist(context: Context) -> None:
    texts = [*context.result.limitations, context.claim.explanation]
    assert any("nie znaczy" in text for text in texts)
    assert not any("takiego artykułu nie ma" in text for text in texts)


@then("fragment z artykułu jest cytatem po weryfikacji dosłownej")
def article_is_cited(context: Context) -> None:
    [citation] = context.claim.citations
    assert citation.source.domain == "fakenews.pl"
    assert citation.fragment in ARTICLE
    assert [url for url, _ in context.pages.calls] == [ARTICLE_URL]
