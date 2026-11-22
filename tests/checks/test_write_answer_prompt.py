import asyncio
from collections.abc import Callable
from dataclasses import replace

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.answers import AnswerDraft
from meritum_worker.checks.steps import write_answer
from meritum_worker.evidence import ClaimExplanation, RecordedLlm

type MakeDeps = Callable[..., CheckDeps]


def test_write_answer_keeps_the_verdict_out_of_the_scanned_data(
    state: CheckState, make_deps: MakeDeps
) -> None:
    # The injection shield scans data and cut "verdict: ..." as a command (worker#221).
    draft = AnswerDraft(
        claims=[
            ClaimExplanation(
                explanation="Nie znaleziono źródła.",
                unresolved="Nie ustalono kwoty; rozstrzygnie ją rozporządzenie.",
            )
        ],
        limitations=["Sprawdzenie nie dotarło do rozporządzenia."],
    )
    llm = RecordedLlm({}, draft)
    out = asyncio.run(write_answer(state, replace(make_deps(), llm=llm)))
    assert out.result is not None
    assert out.result.status == "done"
    [prompt] = llm.prompts
    assert prompt.data == (state.question, "Płaca minimalna wynosi 4806 zł")
    assert prompt.instructions.endswith("1. Brak wystarczających dowodów.")
