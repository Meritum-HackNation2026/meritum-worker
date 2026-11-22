"""Steps for the legal acts with full text scenarios of corpus.feature (worker#235)."""

import asyncio
import dataclasses
import json
import re
from pathlib import Path

from behave import given, then, when
from behave.runner import Context
from catalog_ingest_steps import entry, ingest, start

from meritum_worker import corpus
from meritum_worker.corpus.fakes import FakePublicApi

ACTS = "https://api.sejm.gov.pl/eli/acts"
CONSTITUTION = f"{ACTS}/DU/1997/483"
RECORDED = Path(__file__).parents[2] / "tests" / "corpus" / "fixtures" / "api"


def _start(context: Context, api: FakePublicApi) -> None:
    api.answer(f"{ACTS}/DU/2026", '{"items": []}')
    start(context, [entry("api.sejm.gov.pl", ingest="api")])
    context.deps = dataclasses.replace(
        context.deps,
        api_fetcher=api.fetcher(),
        legal=corpus.LegalActs(acts=("DU/1997/483",)),
    )


@given("wpis katalogu api.sejm.gov.pl i akt, który ma tekst w ELI")
def act_with_text(context: Context) -> None:
    api = FakePublicApi()
    api.answer(
        CONSTITUTION, (RECORDED / "sejm-eli-du-1997-483.json").read_text("utf-8")
    )
    api.answer(
        f"{CONSTITUTION}/text/U/D19970483Lj.pdf",
        (RECORDED / "sejm-konstytucja-tekst-u.pdf").read_bytes(),
        content_type="application/pdf",
    )
    _start(context, api)


@given("akt, dla którego ELI nie udostępnia tekstu")
def act_without_text(context: Context) -> None:
    answer = json.loads((RECORDED / "sejm-eli-du-1997-483.json").read_text("utf-8"))
    answer |= {"textPDF": False, "textHTML": False, "texts": []}
    api = FakePublicApi()
    api.answer(CONSTITUTION, json.dumps(answer))
    _start(context, api)


@when("ingestia pobiera ten akt")
def act_is_ingested(context: Context) -> None:
    ingest(context)


def _constitution(context: Context) -> str:
    (meta,) = [
        d for d in asyncio.run(context.store.documents()) if d.url == CONSTITUTION
    ]
    return asyncio.run(context.store.full_text(meta.source_id)) or ""


@then("dokument w korpusie ma pełny tekst aktu, a nie sam tytuł")
def full_text_stored(context: Context) -> None:
    assert context.report.failures == ()
    text = _constitution(context)
    assert text.startswith("Konstytucja Rzeczypospolitej Polskiej z dnia 2 kwietnia")
    assert "Art. 29." in text


def _stems(text: str) -> set[str]:
    return {word[:5] for word in re.findall(r"\w{4,}", text.casefold())}


@then("fragment „{sentence}” da się znaleźć zapytaniem „{query}”")
def passage_found(context: Context, sentence: str, query: str) -> None:
    passages = [p.text for p in context.store.passages.values()]
    best = max(passages, key=lambda text: len(_stems(query) & _stems(text)))
    assert sentence in best


@then("dokument ma tytuł i metadane, a próba jest zapisana z powodem braku tekstu")
def title_kept(context: Context) -> None:
    (failure,) = context.report.failures
    assert (failure.url, failure.reason) == (CONSTITUTION, "act_text_unavailable")
    assert "ELI: DU/1997/483, Dz.U. 1997 nr 78 poz. 483" in _constitution(context)
