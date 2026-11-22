"""write_answer asks the model again when an answer breaks the contract (worker#194)."""

import asyncio
import logging

import pytest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import LlmResult, Prompt
from pydantic import BaseModel
from tests.llm_fakes import USAGE, NoTools

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.checks.prompts import ANSWER_INSTRUCTIONS
from meritum_worker.checks.steps import write_answer
from meritum_worker.evidence import ClaimExplanation

ANSWER_TEXT = "Tekst odpowiedzi modelu, który nie może trafić do logu."
GOOD = AnswerDraft(
    claims=[
        ClaimExplanation(
            explanation="Nie znaleziono źródła, które to potwierdza albo obala.",
            unresolved="Nie ustalono kwoty; rozstrzygnie ją rozporządzenie.",
        )
    ],
    limitations=["Znaleziono tylko jedno źródło."],
)
TWO_FOR_ONE = AnswerDraft(
    claims=[ClaimExplanation(explanation=ANSWER_TEXT)] * 2, limitations=[]
)


class _Answers(NoTools):
    """Answers each call with the next draft."""

    def __init__(self, *drafts: AnswerDraft) -> None:
        self.drafts = list(drafts)

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        del prompt
        answer = output.model_validate(self.drafts.pop(0).model_dump())
        return LlmResult[T](output=answer, usage=USAGE)


def _deps(*drafts: AnswerDraft) -> CheckDeps:
    return CheckDeps(
        llm=_Answers(*drafts),
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
        **corpus_ports(),
    )


def test_a_broken_answer_is_asked_again_and_the_second_one_is_used(
    state: CheckState,
) -> None:
    out = asyncio.run(write_answer(state, _deps(TWO_FOR_ONE, GOOD)))
    assert out.result is not None
    assert out.result.status == "done"
    assert len(out.models) == 2


def test_two_broken_answers_end_as_technical_failure_with_the_rule_logged(
    state: CheckState, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    out = asyncio.run(write_answer(state, _deps(TWO_FOR_ONE, TWO_FOR_ONE)))
    assert out.result is not None
    assert out.result.status == "technical_failure"
    assert len(out.models) == 2
    assert "2 explanations for 1 facts" in caplog.text
    assert ANSWER_TEXT not in caplog.text


def test_an_answer_without_limitations_is_asked_again(state: CheckState) -> None:
    # Dev, 2026-11-22: "no limitation at all is fine" in the prompt, while a done
    # CheckResult must state its limitations, ended 7 of 64 checks as failures.
    bare = GOOD.model_copy(update={"limitations": []})
    out = asyncio.run(write_answer(state, _deps(bare, GOOD)))
    assert out.result is not None
    assert out.result.limitations == ["Znaleziono tylko jedno źródło."]


def test_answer_prompt_requires_a_limitation() -> None:
    assert "At least one limitation is required" in ANSWER_INSTRUCTIONS
    assert "no limitation at all is fine" not in ANSWER_INSTRUCTIONS
