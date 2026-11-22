"""Verdict-invariance setup: one supported claim, run to the answer."""

import asyncio
from datetime import UTC, datetime

from meritum_core.checks.contracts import IncidentMatch
from tests.evidence.support import CLAIM, deps, state_with

from meritum_worker.checks import AnswerDraft, CheckState
from meritum_worker.checks.steps import assess_evidence, verify_citations, write_answer
from meritum_worker.evidence import (
    ClaimExplanation,
    RecordedLlm,
    StanceJudgement,
    document,
)

SUPPORT = "Płaca minimalna od 1 stycznia wynosi 4806 zł brutto miesięcznie."


def incident(matched_on: str, basis: list[str]) -> IncidentMatch:
    return IncidentMatch.model_validate(
        {
            "database": "euvsdisinfo",
            "incident_id": "case:1",
            "matched_on": matched_on,
            "match_basis": basis,
            "title": "Minimum wage claim",
            "date": datetime(2026, 1, 1, tzinfo=UTC),
            "url": "https://euvsdisinfo.eu/report/minimum-wage",
            "similarity": 0.9,
        }
    )


MATCHES = (
    incident("content", ["title", "topic", "date"]),
    incident("domain", ["domain", "topic"]),
)


def supported() -> CheckState:
    return state_with(CLAIM, [document("gus-1", SUPPORT)])


def answered(state: CheckState, match: IncidentMatch | None = None) -> CheckState:
    if match is not None:
        state = state.model_copy(update={"incidents": {CLAIM: match}})
    stance = StanceJudgement.model_validate(
        {"relevant": True, "fragment": SUPPORT, "stance": "supports"}
    )
    written = ClaimExplanation(explanation="Komunikat GUS potwierdza tę kwotę.")
    draft = AnswerDraft(claims=[written], limitations=["Sprawdzono tylko korpus."])
    ports = deps(RecordedLlm({SUPPORT: stance}, draft))
    for step in (assess_evidence, verify_citations, write_answer):
        state = asyncio.run(step(state, ports))
    return state
