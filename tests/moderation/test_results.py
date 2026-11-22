"""DbosCheckResults reads the checks and the rechecks DBOS keeps; DBOS is faked."""

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from dbos import DBOS
from meritum_core.checks import CheckResult

from meritum_worker.moderation.adapters import DbosCheckResults

ASKED = datetime(2026, 11, 20, 10, 0, tzinfo=UTC)


def _run(workflow_id: str, name: str, verdict: str) -> SimpleNamespace:
    result = CheckResult.model_validate(
        {
            "check_id": workflow_id,
            "status": "done",
            "corpus_version": "2026-11-20T10:00Z",
            "limitations": ["Sprawdzono tylko indeks ocen."],
            "limitation_codes": ["fact_check_unavailable"],
            "ai_marker": {
                "ai_generated": True,
                "provider": "recorded",
                "model": "recorded-1",
                "generated_at": ASKED.isoformat(),
            },
            "claims": [
                {
                    "claim": f"twierdzenie z {name}",
                    "claim_date": "2026-11-20",
                    "claim_date_source": "today",
                    "verdict": verdict,
                    "explanation": "Żadne źródło tego nie rozstrzyga.",
                    "unresolved": "Nie wiadomo, czy to prawda.",
                }
            ],
        }
    )
    return SimpleNamespace(
        workflow_id=workflow_id,
        name=name,
        output={"result": result.model_dump(mode="json")},
    )


RUNS = [
    _run("chk_1", "check", "insufficient_evidence"),
    _run("re_1", "recheck_claim", "insufficient_evidence"),
    _run("idx_1", "corpus_ingest", "insufficient_evidence"),
]


pytestmark = pytest.mark.usefixtures("dbos")


@pytest.fixture
def dbos(monkeypatch: pytest.MonkeyPatch) -> None:
    async def listed(  # ruff: ignore[unused-async]  # replaces an async DBOS call
        *,
        name: str | list[str],
        workflow_ids: list[str] | None = None,
        **_query: object,
    ) -> list[SimpleNamespace]:
        names = [name] if isinstance(name, str) else name
        return [
            r
            for r in RUNS
            if r.name in names
            and (workflow_ids is None or r.workflow_id in workflow_ids)
        ]

    monkeypatch.setattr(DBOS, "list_workflows_async", listed)


def test_a_recheck_claim_is_found_for_the_moderators() -> None:
    claim = asyncio.run(DbosCheckResults().claim("re_1", 0))
    assert claim == "twierdzenie z recheck_claim"


def test_unanswered_rechecks_join_the_history_of_unanswered_claims() -> None:
    found = asyncio.run(DbosCheckResults().unanswered_since(ASKED))
    assert {p.check_id for p in found} == {"chk_1", "re_1"}
