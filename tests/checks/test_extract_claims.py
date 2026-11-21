import asyncio
from datetime import date

from meritum_core.checks.contracts import ClaimResult
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.shared.llm import (
    LlmResult,
    LlmUsage,
    Prompt,
    ProviderUnavailableError,
)
from pydantic import BaseModel

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    ClaimExtraction,
    ExtractedClaim,
)
from meritum_worker.checks.steps import extract_claims, write_answer

USAGE = LlmUsage(
    provider="stub", model="stub", region="local", input_tokens=0, output_tokens=0
)


class _RecordingLlm:
    """Answers each output model from ``answers`` and keeps every prompt."""

    def __init__(self, *answers: BaseModel) -> None:
        self.answers = {type(answer).__name__: answer for answer in answers}
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.prompts.append(prompt)
        if output.__name__ not in self.answers:
            raise ProviderUnavailableError(output.__name__)
        answer = output.model_validate(self.answers[output.__name__].model_dump())
        return LlmResult[T](output=answer, usage=USAGE)


def _claim(text: str, kind: str = "fact", **date_fields: object) -> ExtractedClaim:
    return ExtractedClaim.model_validate(
        {
            "claim": text,
            "kind": kind,
            "explanation": "Wyjaśnienie rodzaju twierdzenia.",
            **date_fields,
        }
    )


def _extract(
    state: CheckState, *claims: ExtractedClaim, out_of_scope: bool = False
) -> tuple[CheckState, _RecordingLlm]:
    llm = _RecordingLlm(ClaimExtraction(out_of_scope=out_of_scope, claims=[*claims]))
    deps = CheckDeps(llm=llm, records=InMemoryCheckRecordRepository())
    return asyncio.run(
        extract_claims(state.model_copy(update={"claims": []}), deps)
    ), llm


def test_request_not_about_information_is_out_of_scope_with_message(
    state: CheckState,
) -> None:
    out, _ = _extract(state, out_of_scope=True)
    assert out.result is not None
    assert (out.result.status, out.result.claims) == ("out_of_scope", [])
    assert out.result.message == "status_hint.out_of_scope"
    assert len(out.models) == 1


def test_input_without_claims_needs_clarification(state: CheckState) -> None:
    out, _ = _extract(state)
    assert out.result is not None
    assert out.result.status == "needs_clarification"
    assert out.result.message == "status_hint.needs_clarification"


def test_only_opinion_is_still_a_claim_not_a_clarification(state: CheckState) -> None:
    out, _ = _extract(state, _claim("Rząd sobie nie radzi.", "opinion"))
    assert out.result is None
    assert [c.kind for c in out.claims] == ["opinion"]


def test_claim_without_date_in_text_is_dated_today(state: CheckState) -> None:
    out, _ = _extract(state, _claim("Bezrobocie wynosi 5,3%"))
    (claim,) = out.claims
    assert claim.claim_date == state.job.received_at.date()
    assert claim.claim_date_source == "today"


def test_claim_keeps_date_and_source_from_model(state: CheckState) -> None:
    published = _claim(
        "Bezrobocie wynosi 5,3%",
        claim_date="2025-05-03",
        claim_date_source="input_published_at",
    )
    out, _ = _extract(state, published)
    (claim,) = out.claims
    assert (claim.claim_date, claim.claim_date_source) == (
        date(2025, 5, 3),
        "input_published_at",
    )


def test_date_without_source_counts_as_from_text(state: CheckState) -> None:
    out, _ = _extract(state, _claim("W marcu 2025 bezrobocie", claim_date="2025-03-01"))
    assert out.claims[0].claim_date_source == "text"


def test_facts_take_the_five_places_before_opinions(state: CheckState) -> None:
    opinions = [_claim(f"Opinia numer {i}", "opinion") for i in range(5)]
    out, _ = _extract(state, *opinions, _claim("Fakt o liczbie 7"))
    assert out.claims[0].claim == "Fakt o liczbie 7"
    assert len(out.claims) == 5
    assert out.limitations == ["Opinia numer 4"]


def test_skipped_claim_note_fits_contract_limit(state: CheckState) -> None:
    long_claims = [_claim(f"{i} " + "x" * 490) for i in range(6)]
    out, _ = _extract(state, *long_claims)
    assert [len(note) for note in out.limitations] == [300]


def test_user_text_goes_to_the_model_only_as_data(state: CheckState) -> None:
    _, llm = _extract(state, _claim("Bezrobocie wynosi 5,3%"))
    (prompt,) = llm.prompts
    assert prompt.data == (state.question,)
    assert state.question not in prompt.instructions


def test_provider_failure_is_technical_failure(state: CheckState) -> None:
    deps = CheckDeps(llm=_RecordingLlm(), records=InMemoryCheckRecordRepository())
    out = asyncio.run(extract_claims(state, deps))
    assert out.result is not None
    assert out.result.status == "technical_failure"


def test_answer_with_other_count_than_facts_is_technical_failure(
    state: CheckState,
) -> None:
    llm = _RecordingLlm(AnswerDraft(claims=[], limitations=["Brak korpusu."]))
    deps = CheckDeps(llm=llm, records=InMemoryCheckRecordRepository())
    out = asyncio.run(write_answer(state, deps))
    assert out.result is not None
    assert out.result.status == "technical_failure"


def test_write_answer_keeps_a_result_set_by_extraction(state: CheckState) -> None:
    done, _ = _extract(state)
    llm = _RecordingLlm()
    deps = CheckDeps(llm=llm, records=InMemoryCheckRecordRepository())
    out = asyncio.run(write_answer(done, deps))
    assert out.result == done.result
    assert llm.prompts == []


def test_only_opinions_are_done_with_model_limitations_even_if_it_judged_them(
    state: CheckState,
) -> None:
    opinion = _claim("Rząd sobie nie radzi.", "opinion")
    extracted, _ = _extract(state, opinion)
    judged = ClaimResult(
        claim="Rząd sobie nie radzi.",
        claim_date=date(2026, 1, 1),
        claim_date_source="today",
        verdict="not_verifiable",
        explanation="Ocena, a nie fakt do sprawdzenia.",
    )
    draft = AnswerDraft(claims=[judged], limitations=["Brak faktów do sprawdzenia."])
    deps = CheckDeps(llm=_RecordingLlm(draft), records=InMemoryCheckRecordRepository())
    out = asyncio.run(write_answer(extracted, deps))
    assert out.result is not None
    assert out.result.status == "done"
    assert [(c.claim, c.verdict) for c in out.result.claims] == [
        ("Rząd sobie nie radzi.", "not_verifiable")
    ]
    assert out.result.limitations == ["Brak faktów do sprawdzenia."]
