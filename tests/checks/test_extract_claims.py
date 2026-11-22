import asyncio
from datetime import date

import pytest
from meritum_core.checks.fakes import InMemoryCheckRecordRepository
from meritum_core.security.pii import NullPiiGate
from meritum_core.shared.llm import (
    LlmPort,
    ProviderUnavailableError,
)
from tests.llm_fakes import RecordingLlm

from meritum_worker.checks import (
    AnswerDraft,
    CheckDeps,
    CheckState,
    ClaimExtraction,
    ExtractedClaim,
    FakePageFetcher,
    audio_ports,
    corpus_ports,
    web_ports,
)
from meritum_worker.checks.prompts import EXTRACTION_INSTRUCTIONS
from meritum_worker.checks.steps import extract_claims, write_answer
from meritum_worker.evidence import ClaimExplanation


def _deps(llm: LlmPort) -> CheckDeps:
    return CheckDeps(
        llm=llm,
        records=InMemoryCheckRecordRepository(),
        pages=FakePageFetcher(),
        pii=NullPiiGate(),
        **audio_ports(),
        **web_ports(),
        **corpus_ports(),
    )


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
) -> tuple[CheckState, RecordingLlm]:
    llm = RecordingLlm(ClaimExtraction(out_of_scope=out_of_scope, claims=[*claims]))
    return asyncio.run(
        extract_claims(state.model_copy(update={"claims": []}), _deps(llm))
    ), llm


def test_request_not_about_information_is_out_of_scope_with_message(
    state: CheckState,
) -> None:
    out, _ = _extract(state, out_of_scope=True)
    assert out.result is not None
    assert (out.result.status, out.result.claims) == ("out_of_scope", [])
    assert not (out.result.message or "").startswith("status_hint.")
    assert len(out.models) == 1


def test_input_without_claims_needs_clarification(state: CheckState) -> None:
    out, _ = _extract(state)
    assert out.result is not None
    assert out.result.status == "needs_clarification"
    assert not (out.result.message or "").startswith("status_hint.")


def test_only_opinion_is_still_a_claim_not_a_clarification(state: CheckState) -> None:
    out, _ = _extract(state, _claim("Rząd sobie nie radzi.", "opinion"))
    assert out.result is None
    assert [c.kind for c in out.claims] == ["opinion"]


def test_claim_without_date_in_text_is_dated_today(state: CheckState) -> None:
    out, _ = _extract(state, _claim("Bezrobocie wynosi 5,3%"))
    (claim,) = out.claims
    assert claim.claim_date == state.job.received_at.date()
    assert claim.claim_date_source == "today"


def test_claim_without_date_from_a_dated_page_takes_its_publication_date(
    state: CheckState,
) -> None:
    page_state = state.model_copy(update={"published_at": date(2026, 11, 18)})
    out, _ = _extract(page_state, _claim("Bezrobocie wynosi 5,3%"))
    (claim,) = out.claims
    assert (claim.claim_date, claim.claim_date_source) == (
        date(2026, 11, 18),
        "input_published_at",
    )


def test_page_metadata_date_wins_over_a_publication_date_the_model_read(
    state: CheckState,
) -> None:
    page_state = state.model_copy(update={"published_at": date(2026, 11, 18)})
    byline = _claim(
        "Bezrobocie wynosi 5,3%",
        claim_date="2026-11-17",
        claim_date_source="input_published_at",
    )
    out, _ = _extract(page_state, byline)
    assert out.claims[0].claim_date == date(2026, 11, 18)


def test_publication_date_of_the_page_goes_into_the_instructions(
    state: CheckState,
) -> None:
    page_state = state.model_copy(update={"published_at": date(2026, 11, 20)})
    _, llm = _extract(page_state, _claim("Wczoraj rząd przyjął ustawę"))
    (prompt,) = llm.prompts
    assert "2026-11-20" in prompt.instructions


def test_relative_date_the_model_resolved_from_the_page_date_stays(
    state: CheckState,
) -> None:
    page_state = state.model_copy(update={"published_at": date(2026, 11, 20)})
    yesterday = _claim(
        "Wczoraj rząd przyjął ustawę",
        claim_date="2026-11-19",
        claim_date_source="text",
    )
    out, _ = _extract(page_state, yesterday)
    assert (out.claims[0].claim_date, out.claims[0].claim_date_source) == (
        date(2026, 11, 19),
        "text",
    )


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


def test_provider_failure_reaches_the_workflow(state: CheckState) -> None:
    deps = _deps(RecordingLlm())
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(extract_claims(state, deps))


def test_answer_with_other_count_than_facts_is_technical_failure(
    state: CheckState,
) -> None:
    llm = RecordingLlm(AnswerDraft(claims=[], limitations=["Brak korpusu."]))
    deps = _deps(llm)
    out = asyncio.run(write_answer(state, deps))
    assert out.result is not None
    assert out.result.status == "technical_failure"


def test_write_answer_keeps_a_result_set_by_extraction(state: CheckState) -> None:
    done, _ = _extract(state)
    llm = RecordingLlm()
    deps = _deps(llm)
    out = asyncio.run(write_answer(done, deps))
    assert out.result == done.result
    assert llm.prompts == []


def test_only_opinions_are_done_with_model_limitations_even_if_it_judged_them(
    state: CheckState,
) -> None:
    opinion = _claim("Rząd sobie nie radzi.", "opinion")
    extracted, _ = _extract(state, opinion)
    judged = ClaimExplanation(explanation="Ocena, a nie fakt do sprawdzenia.")
    draft = AnswerDraft(claims=[judged], limitations=["Brak faktów do sprawdzenia."])
    deps = _deps(RecordingLlm(draft))
    out = asyncio.run(write_answer(extracted, deps))
    assert out.result is not None
    assert out.result.status == "done"
    assert [(c.claim, c.verdict) for c in out.result.claims] == [
        ("Rząd sobie nie radzi.", "not_verifiable")
    ]
    assert out.result.limitation_codes == ["corpus_scope"]


def test_extraction_prompt_keeps_reasons_inside_the_claim() -> None:
    assert "reason given for a claim" in EXTRACTION_INSTRUCTIONS
    assert "rule or decision already made" in EXTRACTION_INSTRUCTIONS


def test_extraction_prompt_turns_a_yes_no_question_into_its_claim() -> None:
    # Benchmark worker#170: "Czy X?" ended needs_clarification with no claims.
    assert "yes/no question" in EXTRACTION_INSTRUCTIONS
    assert "Sejm ma 460 posłów" in EXTRACTION_INSTRUCTIONS


def test_extraction_prompt_puts_tasks_for_the_assistant_out_of_scope() -> None:
    # Benchmark worker#170: "Ile to jest 17 razy 23?" ended needs_clarification.
    for task in ("calculation", "recipe", "translation", "code"):
        assert task in EXTRACTION_INSTRUCTIONS
    assert "do something rather than check" in EXTRACTION_INSTRUCTIONS
    assert "Co o tym sądzisz?" in EXTRACTION_INSTRUCTIONS


def test_extraction_prompt_reads_a_ban_from_a_date_as_a_fact() -> None:
    # Benchmark worker#170: "Od stycznia nie zapłacisz gotówką" came out a prediction.
    assert "Od stycznia nie zapłacisz gotówką" in EXTRACTION_INSTRUCTIONS
