"""Steps for features/corpus.feature, on a fake EUvsDisinfo MCP server."""

import asyncio
from datetime import UTC, datetime

from behave import given, then, when
from behave.runner import Context
from meritum_core.shared.embeddings import EmbeddingsSettings, build_embeddings

from meritum_worker import corpus
from meritum_worker.corpus.fakes import FakeEuvsDisinfoServer

TOKEN = "test-token"  # ruff: ignore[hardcoded-password-string]  # the fake server's token, not a secret


@given("ważny token EUvsDisinfo")
def valid_token(context: Context) -> None:
    context.env = {"EUVSDISINFO_MCP_API_KEY": TOKEN}
    context.server = FakeEuvsDisinfoServer(TOKEN)
    context.store = corpus.build_euvsdisinfo_copy()


@given("w źródle {cases:d} przypadków i {articles:d} artykułów")
def source_has(context: Context, cases: int, articles: int) -> None:
    context.server.seed(cases=cases, articles=articles)
    context.seeded = {"case": cases, "article": articles}


@given("kopia z poprzedniego przebiegu")
def previous_copy(context: Context) -> None:
    context.server.seed(cases=30, articles=10)
    run_sync(context)
    context.server.calls.clear()


@given("w źródle {new:d} nowych wpisów, {changed:d} zmienione i {gone:d} usunięty")
def source_changes(context: Context, new: int, changed: int, gone: int) -> None:
    context.server.add_cases(new)
    context.server.change_cases(changed)
    context.server.remove_cases(gone)


@when("workflow synchronizacji EUvsDisinfo kończy przebieg")
@when("workflow synchronizacji kończy przebieg")
def sync_finishes(context: Context) -> None:
    run_sync(context)


def run_sync(context: Context) -> None:
    context.report = asyncio.run(
        corpus.run_euvsdisinfo_sync(
            context.env,
            context.store,
            build_embeddings(EmbeddingsSettings()),
            now=datetime.now(UTC),
            http_client=context.server.client(),
        )
    )


@then("lokalna kopia ma wszystkie artykuły i przypadki pobrane stronami po 100")
def copy_is_complete(context: Context) -> None:
    entries = asyncio.run(context.store.entries())
    for kind, seeded in context.seeded.items():
        assert len([e for e in entries if e.entry.kind == kind]) == seeded
    assert context.server.calls == [
        ("cases", 100, 0),
        ("cases", 100, 100),
        ("cases", 100, 200),
        ("articles", 100, 0),
        ("articles", 100, 100),
    ]


@then("opisy przypadków i teksty fact mają embeddingi wielojęzyczne")
def entries_have_embeddings(context: Context) -> None:
    for stored in asyncio.run(context.store.entries()):
        assert any(stored.description_vector), stored.entry.key
        if stored.entry.kind == "case":
            assert stored.fact_vector is not None
            assert any(stored.fact_vector), stored.entry.key


@then(
    "{added:d} wpisów jest dodanych, {updated:d} zaktualizowane,"
    " a {deleted:d} oznaczony jako usunięty"
)
def diff_is_applied(context: Context, added: int, updated: int, deleted: int) -> None:
    assert (context.report.added, context.report.updated) == (added, updated)
    assert context.report.deleted == deleted
    entries = asyncio.run(context.store.entries())
    assert len([e for e in entries if e.deleted_at is not None]) == deleted


@given("brak tokenu EUvsDisinfo")
def no_token(context: Context) -> None:
    valid_token(context)
    context.env = {}


@then('raport wskazuje brak "{name}" bez zapytań do serwera MCP')
def report_names_missing(context: Context, name: str) -> None:
    assert context.report.missing_env == [name]
    assert corpus.missing_env(context.env) == [name]
    assert context.server.calls == []
