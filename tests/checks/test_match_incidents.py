"""The match_incidents step over the shared incident table, with keyed embeddings."""

import asyncio
import dataclasses
from collections.abc import Callable, Sequence

from meritum_core.shared.embeddings import EmbeddingsUnavailableError, Vector
from tests.checks.incident_support import (
    CASE_URL,
    CLAIM_PL,
    FACT,
    case,
    checked,
    embeddings,
)

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.steps import match_incidents
from meritum_worker.corpus import StoredEntry, build_euvsdisinfo_copy
from meritum_worker.evidence import INCIDENTS_UNAVAILABLE


class _Broken:
    @staticmethod
    async def embed_query(text: str) -> Vector:
        raise EmbeddingsUnavailableError(text)

    @staticmethod
    async def embed_documents(texts: Sequence[str]) -> list[Vector]:
        raise EmbeddingsUnavailableError(str(len(texts)))


def _run(
    deps: CheckDeps, state: CheckState, *entries: StoredEntry, broken: bool = False
) -> CheckState:
    copy = build_euvsdisinfo_copy()
    asyncio.run(copy.upsert(entries))
    ports = dataclasses.replace(
        deps, incidents=copy, embeddings=_Broken() if broken else embeddings()
    )
    return asyncio.run(match_incidents(state, ports))


def test_polish_claim_matches_an_english_case(
    make_deps: Callable[..., CheckDeps],
) -> None:
    after = _run(make_deps(), checked(), case())
    match = after.incidents[CLAIM_PL]
    assert (match.database, match.matched_on) == ("euvsdisinfo", "content")
    assert str(match.url) == CASE_URL
    assert match.title


def test_the_fact_text_joins_the_evidence_as_a_secondary_source(
    make_deps: Callable[..., CheckDeps],
) -> None:
    after = _run(make_deps(), checked(), case())
    [fact] = after.evidence
    assert fact.text == FACT
    assert fact.source.publisher_id == "eeas-euvsdisinfo"


def test_a_listed_domain_on_topic_warns_without_a_content_match(
    make_deps: Callable[..., CheckDeps],
) -> None:
    other = case(title="A different story", domains=("fake.example",))
    after = _run(make_deps(), checked("https://www.fake.example/a"), other)
    assert after.incidents[CLAIM_PL].matched_on == "domain"


def test_a_deleted_case_never_matches(make_deps: Callable[..., CheckDeps]) -> None:
    after = _run(make_deps(), checked(), case(deleted=True))
    assert after.incidents == {}
    assert after.evidence == []


def test_unavailable_embeddings_skip_matching_without_failing(
    make_deps: Callable[..., CheckDeps],
) -> None:
    after = _run(make_deps(), checked(), case(), broken=True)
    assert after.incidents == {}
    assert after.result is None
    assert INCIDENTS_UNAVAILABLE in after.retrieval_errors


def test_without_incident_ports_the_step_passes_on(
    make_deps: Callable[..., CheckDeps],
) -> None:
    state = checked()
    assert asyncio.run(match_incidents(state, make_deps())) == state
