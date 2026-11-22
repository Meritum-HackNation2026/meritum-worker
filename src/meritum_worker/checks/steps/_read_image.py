"""Read the text of an uploaded image with OCR and check it like a pasted one.

Features:
    US-SPR-08, US-SPR-01, US-OBS-01, F-33, F-22, ADR-30
"""

from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import LimitationCode
from meritum_core.checks.ocr import (
    OcrResult,
    OcrUnavailableError,
    UnsupportedImageError,
)
from meritum_core.security.pii import mask_personal_data
from meritum_core.shared.blobs import BlobNotFoundError

from meritum_worker.checks.image.constants import (
    IMAGE_DATE_NOTE,
    IMAGE_SEARCH_NOT_RUN_NOTE,
    IMAGE_SEARCHED_NOTE,
    MAX_IMAGE_TEXT_CHARS,
    NO_TEXT_ON_IMAGE_MESSAGE,
    READ_IMAGE_STEP,
    UNSUPPORTED_IMAGE_MESSAGE,
)
from meritum_worker.checks.models import CheckDeps, CheckState


async def read_image(state: CheckState, deps: CheckDeps) -> CheckState:
    """Read ``image_id`` through the core OCR port; a request without an image skips it.

    The text is masked like the input and cut to the length of a pasted text.
    A date written in it dates the claims (source ``text``); the limitations say
    it does not confirm the publication date, and whether earlier appearances of
    the image were searched. The file metadata is kept as context only.

    An unsupported or too large image ends as out_of_scope (code ``image``, the
    reason in the limitation code); an image with no text as needs_clarification;
    a provider failure, a missing file or no OCR port as technical_failure. A
    failing image search propagates; the workflow maps it to technical_failure.

    Args:
        state: the check so far.
        deps: the ports; OCR, image search and the masking gate.

    Returns:
        The state with the masked text, its date and the notes, with a result
        that is not a verdict, or with the step marked skipped.

    Features:
        US-SPR-08, F-33, ADR-30
    """
    image_id = state.job.request.image_id
    if image_id is None:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, READ_IMAGE_STEP]}
        )
    if deps.ocr is None:
        return _ended(state, state.technical_failure())
    try:
        read = await deps.ocr.read(image_id)
    except UnsupportedImageError as exc:
        limitation = (exc.limitation_code, UNSUPPORTED_IMAGE_MESSAGE)
        result = state.with_message(
            "out_of_scope",
            UNSUPPORTED_IMAGE_MESSAGE,
            out_of_scope_code="image",
            limitation=limitation,
        )
        return _ended(state, result)
    except OcrUnavailableError, BlobNotFoundError:
        return _ended(state, state.technical_failure())
    if not read.text.strip():
        result = state.with_message("needs_clarification", NO_TEXT_ON_IMAGE_MESSAGE)
        return _ended(state, result)
    masked = await mask_personal_data(read.text[:MAX_IMAGE_TEXT_CHARS], deps.pii)
    return state.model_copy(
        update={
            # Cut again: a marker can be longer than the personal data it replaced.
            "image_text": masked.text[:MAX_IMAGE_TEXT_CHARS],
            "image_date": read.claim_date,
            "image_info": read.metadata,
            "image_notes": [*state.image_notes, *await _notes(read, image_id, deps)],
        }
    )


def _ended(state: CheckState, result: CheckResult) -> CheckState:
    return state.model_copy(update={"result": result})


async def _notes(
    read: OcrResult, image_id: str, deps: CheckDeps
) -> list[tuple[LimitationCode, str]]:
    notes: list[tuple[LimitationCode, str]] = []
    if read.claim_date is not None:
        notes.append(("corpus_scope", IMAGE_DATE_NOTE))
    searched = (
        None if deps.image_search is None else await deps.image_search.search(image_id)
    )
    if searched is None or not searched.searched:
        notes.append(("image_search_not_run", IMAGE_SEARCH_NOT_RUN_NOTE))
    else:
        found = IMAGE_SEARCHED_NOTE.format(found=len(searched.occurrences))
        notes.append(("corpus_scope", found))
    return notes
