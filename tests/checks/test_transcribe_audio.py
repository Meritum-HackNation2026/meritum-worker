import asyncio
import dataclasses
from collections.abc import Callable
from datetime import timedelta
from pathlib import Path

import pytest
from meritum_core.checks import CheckRequest
from meritum_core.checks.transcription import Transcript
from meritum_core.jobs.contracts import CheckInput
from meritum_core.shared.blobs import BlobKind

from meritum_worker.checks import (
    CheckDeps,
    CheckState,
    InlineCheckRuntime,
    audio_ports,
    ogg_opus,
    run_check,
)
from meritum_worker.checks.constants import (
    AUDIO_TOO_LONG_MESSAGE,
    TRANSCRIPTION_FAILED_CODE,
)
from meritum_worker.checks.steps import notify_done, transcribe_audio

SPOKEN = "Od jutra pociągi do Gdańska nie jeżdżą, dzwoń 600 700 800."


def _deps(
    make_deps: Callable[..., CheckDeps], tmp_path: Path, text: str = SPOKEN
) -> CheckDeps:
    fixture = tmp_path / "transcript.json"
    fixture.write_text(Transcript(text=text, language="pl-PL").model_dump_json())
    return dataclasses.replace(make_deps(), **audio_ports(fixture))


def _state(job: CheckInput, deps: CheckDeps, data: bytes) -> CheckState:
    ref = asyncio.run(
        deps.blobs.put(
            data,
            kind=BlobKind.AUDIO,
            content_type="audio/ogg",
            expires_at=job.received_at + timedelta(days=30),
        )
    )
    request = CheckRequest(channel="web", audio_id=ref.blob_id)
    return CheckState(
        check_id="check-1", job=job.model_copy(update={"request": request})
    )


def test_transcribe_audio_masks_the_transcript_and_keeps_the_length(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
) -> None:
    deps = _deps(make_deps, tmp_path)
    out = asyncio.run(transcribe_audio(_state(make_job(), deps, ogg_opus(8)), deps))
    assert out.result is None
    assert out.audio_seconds == 8
    assert out.transcript is not None
    assert out.transcript.startswith("Od jutra pociągi do Gdańska")
    assert "600 700 800" not in out.transcript
    assert out.question == out.transcript
    assert out.final_result().transcript == out.transcript


def test_transcribe_audio_cuts_a_long_transcript_to_the_contract_limit(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
) -> None:
    deps = _deps(make_deps, tmp_path, "a" * 9000)
    out = asyncio.run(transcribe_audio(_state(make_job(), deps, ogg_opus(8)), deps))
    assert out.transcript is not None
    assert len(out.transcript) == 4000


def test_transcribe_audio_is_skipped_without_audio(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    state = CheckState(check_id="check-1", job=make_job())
    out = asyncio.run(transcribe_audio(state, make_deps()))
    assert out.skipped_steps == ["transcribe_audio"]
    assert out.transcript is None


def test_transcribe_audio_over_ten_minutes_is_out_of_scope(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
) -> None:
    deps = _deps(make_deps, tmp_path)
    out = asyncio.run(transcribe_audio(_state(make_job(), deps, ogg_opus(601)), deps))
    assert out.result is not None
    assert out.result.status == "out_of_scope"
    assert out.result.message == AUDIO_TOO_LONG_MESSAGE


def test_transcribe_audio_without_the_file_is_a_transcription_failure(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
) -> None:
    deps = _deps(make_deps, tmp_path)
    state = _state(make_job(), deps, ogg_opus(8))
    asyncio.run(deps.blobs.delete(state.job.request.audio_id or ""))
    out = asyncio.run(transcribe_audio(state, deps))
    assert out.result is not None
    assert out.result.failure_code == TRANSCRIPTION_FAILED_CODE


@pytest.mark.parametrize(("seconds", "sent"), [(8, 0), (55, 0), (120, 1)])
def test_notify_done_announces_only_a_long_recording_once(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    seconds: float,
    sent: int,
) -> None:
    deps = make_deps()
    state = CheckState(check_id="check-1", job=make_job(), audio_seconds=seconds)
    asyncio.run(notify_done(state, deps))
    asyncio.run(notify_done(state, deps))  # a retried step replaces the entry
    inbox = asyncio.run(deps.notifications.list_for("session_id", "session-1"))
    assert len(inbox) == sent
    assert all(n.kind == "check_done" and n.check_id == "check-1" for n in inbox)
    assert all(n.link == "/sprawdzenie/check-1" for n in inbox)


def test_check_of_a_long_recording_masks_the_transcript_and_announces_the_end(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
) -> None:
    deps = _deps(make_deps, tmp_path)
    state = _state(make_job(), deps, ogg_opus(120))
    output = asyncio.run(
        run_check(
            state.job.model_dump(mode="json"), "check-1", deps, InlineCheckRuntime()
        )
    )
    assert output.result.transcript is not None
    assert "600 700 800" not in output.result.transcript
    inbox = asyncio.run(deps.notifications.list_for("session_id", "session-1"))
    assert sorted((n.kind, n.check_id) for n in inbox) == [
        ("check_done", "check-1"),
        ("check_progress", "check-1"),
    ]


@pytest.mark.parametrize(("seconds", "sent"), [(55, 0), (120, 1)])
def test_transcribe_audio_tells_a_long_recording_is_transcribed(
    make_job: Callable[..., CheckInput],
    make_deps: Callable[..., CheckDeps],
    tmp_path: Path,
    seconds: int,
    sent: int,
) -> None:
    deps = _deps(make_deps, tmp_path)
    state = _state(make_job(), deps, ogg_opus(seconds))
    asyncio.run(transcribe_audio(state, deps))
    asyncio.run(transcribe_audio(state, deps))  # a retried step replaces the entry
    inbox = asyncio.run(deps.notifications.list_for("session_id", "session-1"))
    assert [(n.kind, n.step_code) for n in inbox] == [
        ("check_progress", "transcribe_audio")
    ] * sent
