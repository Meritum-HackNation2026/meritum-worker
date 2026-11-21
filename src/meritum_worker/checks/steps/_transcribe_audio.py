"""Transcribe a voice message and check its text like a pasted one.

Features:
    US-SPR-11, F-08, ADR-30
"""

from meritum_core.checks.transcription import (
    AudioTooLongError,
    UnsupportedAudioError,
    inspect_audio,
)
from meritum_core.security.pii import mask_personal_data
from meritum_core.shared.blobs import BlobNotFoundError

from meritum_worker.checks.constants import (
    AUDIO_TOO_LONG_MESSAGE,
    MAX_TRANSCRIPT_CHARS,
    TRANSCRIBE_AUDIO_STEP,
    TRANSCRIPTION_FAILED_CODE,
    UNSUPPORTED_AUDIO_FORMAT_MESSAGE,
)
from meritum_worker.checks.models import CheckDeps, CheckState


async def transcribe_audio(state: CheckState, deps: CheckDeps) -> CheckState:
    """Transcribe ``audio_id`` through the core port; pasted text or no audio skips it.

    The transcript is masked like the input and cut to the length of a pasted
    text. An unsupported or too long recording ends as out_of_scope with what to
    send instead; a missing file as technical_failure with code
    transcription_failed. A provider failure propagates; the workflow maps it to
    the same code (worker#21).

    Args:
        state: the check so far.
        deps: the ports; the blob store, the transcriber and the masking gate.

    Returns:
        The state with the masked transcript and the recording's length, with a
        result that is not a verdict, or with the step marked skipped.

    Features:
        US-SPR-11, F-08, ADR-30
    """
    audio_id = state.job.request.audio_id
    if audio_id is None or state.has_text:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, TRANSCRIBE_AUDIO_STEP]}
        )
    try:
        info = inspect_audio(await deps.blobs.get(audio_id))
        transcript = await deps.transcriber.transcribe(audio_id)
    except AudioTooLongError:
        result = state.with_message("out_of_scope", AUDIO_TOO_LONG_MESSAGE)
        return state.model_copy(update={"result": result})
    except UnsupportedAudioError:
        result = state.with_message("out_of_scope", UNSUPPORTED_AUDIO_FORMAT_MESSAGE)
        return state.model_copy(update={"result": result})
    except BlobNotFoundError:
        failure = state.technical_failure(TRANSCRIPTION_FAILED_CODE)
        return state.model_copy(update={"result": failure})
    masked = await mask_personal_data(transcript.text[:MAX_TRANSCRIPT_CHARS], deps.pii)
    # Cut again: a marker can be longer than the personal data it replaced.
    return state.model_copy(
        update={
            "transcript": masked.text[:MAX_TRANSCRIPT_CHARS],
            "audio_seconds": info.duration_seconds,
        }
    )
