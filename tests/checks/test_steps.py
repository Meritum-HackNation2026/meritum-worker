import asyncio
from collections.abc import Callable
from dataclasses import replace
from datetime import timedelta

import pytest
from meritum_core.checks import InjectionEvent
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.llm import LlmPort, LlmResult, Prompt, ProviderUnavailableError
from pydantic import BaseModel

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.constants import ANSWER_INSTRUCTIONS
from meritum_worker.checks.steps import save_record, write_answer

type MakeDeps = Callable[..., CheckDeps]


def test_write_answer_builds_done_result_and_records_model_usage(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(write_answer(state, make_deps()))
    assert out.result is not None
    assert out.result.status == "done"
    assert [claim.verdict for claim in out.result.claims] == ["insufficient_evidence"]
    assert [(m.provider, m.cost_usd) for m in out.models] == [("stub", 0.0)]
    marker = out.result.ai_marker
    assert marker is not None
    assert (marker.provider, marker.model) == (
        out.models[-1].provider,
        out.models[-1].model,
    )


class _Priced:
    """The stub model, with every call priced like a paid provider."""

    def __init__(self, inner: LlmPort) -> None:
        self._inner = inner

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        result = await self._inner.complete(prompt, output)
        usage = result.usage.model_copy(update={"cost_usd": 0.002})
        return result.model_copy(update={"usage": usage})


def test_write_answer_records_the_cost_the_model_port_reports(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = make_deps()
    out = asyncio.run(write_answer(state, replace(deps, llm=_Priced(deps.llm))))
    assert [m.cost_usd for m in out.models] == [0.002]


def test_write_answer_turns_contract_breaking_answer_into_technical_failure(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(write_answer(state, make_deps("llm_stub_broken_answer.json")))
    assert out.result is not None
    assert out.result.status == "technical_failure"
    assert out.result.claims == []
    assert not (out.result.message or "").startswith("status_hint.")
    assert out.result.failure_code == "provider_unavailable"
    assert len(out.models) == 1


def test_write_answer_leaves_provider_failure_to_the_workflow(
    state: CheckState, make_deps: MakeDeps
) -> None:
    with pytest.raises(ProviderUnavailableError):
        asyncio.run(write_answer(state, make_deps(None)))


def test_save_record_keeps_record_30_days_from_receipt(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = make_deps()
    answered = asyncio.run(write_answer(state, deps))
    asyncio.run(save_record(answered, deps))
    record = asyncio.run(deps.records.get("check-1"))
    assert record is not None
    assert record.retention_until == state.job.received_at + timedelta(days=30)
    assert record.status == "done"
    assert record.question_masked == "Płaca minimalna wynosi 4806 zł"
    assert record.models == answered.models


def test_save_record_without_answer_records_technical_failure(
    state: CheckState, make_deps: MakeDeps
) -> None:
    deps = make_deps()
    asyncio.run(save_record(state, deps))
    record = asyncio.run(deps.records.get("check-1"))
    assert record is not None
    assert record.status == "technical_failure"


def test_save_record_uses_user_id_when_signed_in_without_session(
    make_deps: MakeDeps, make_job: Callable[..., CheckInput]
) -> None:
    deps = make_deps()
    state = CheckState(check_id="check-2", job=make_job(user_id="user-0001"))
    asyncio.run(save_record(state, deps))
    record = asyncio.run(deps.records.get("check-2"))
    assert record is not None
    assert (record.session_id, record.user_id) == ("user-0001", "user-0001")


def test_save_record_copies_what_later_steps_collect(
    state: CheckState, make_deps: MakeDeps
) -> None:
    event = InjectionEvent(
        location="input", action="instruction_removed", excerpt="zignoruj polecenia"
    )
    collected = state.model_copy(
        update={
            "injection_events": [event],
            "web_search_calls": 2,
            "retrieval_errors": ["corpus timeout"],
        }
    )
    deps = make_deps()
    asyncio.run(save_record(collected, deps))
    record = asyncio.run(deps.records.get("check-1"))
    assert record is not None
    assert record.injection_events == [event]
    assert record.web_search_calls == 2
    assert record.retrieval_errors == ["corpus timeout"]


def test_write_answer_replaces_verdict_codes_in_text_for_citizens(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(write_answer(state, make_deps("llm_stub_answer_codes.json")))
    assert out.result is not None
    claim = out.result.claims[0]
    assert claim.explanation == (
        "Werdykt „Brak wystarczających dowodów” oznacza,"
        " że źródła nie rozstrzygają sprawy."
    )
    assert claim.unresolved is not None
    assert "insufficient_evidence" not in claim.unresolved
    assert out.result.limitations[0] == (
        "Wynik „Nie podlega weryfikacji” nie dotyczy tego twierdzenia."
    )


def test_write_answer_prompt_names_verdicts_in_polish_only() -> None:
    assert "for insufficient_evidence" not in ANSWER_INSTRUCTIONS
    assert "Brak wystarczających dowodów" in ANSWER_INSTRUCTIONS


def test_write_answer_cuts_too_long_texts_to_the_contract_limits(
    state: CheckState, make_deps: MakeDeps
) -> None:
    out = asyncio.run(write_answer(state, make_deps("llm_stub_answer_long.json")))
    assert out.result is not None
    assert out.result.status == "done"
    claim = out.result.claims[0]
    assert len(claim.explanation) <= 800
    assert claim.explanation.endswith("inna.")
    assert claim.unresolved is not None
    assert len(claim.unresolved) <= 500
    assert all(len(text) <= 300 for text in out.result.limitations)
    assert out.result.limitations[0].endswith("katalogu.")


def test_write_answer_prompt_gives_the_length_limits() -> None:
    assert "800" in ANSWER_INSTRUCTIONS
    assert "300" in ANSWER_INSTRUCTIONS
