"""Cut instructions out of the citizen's input and drop a linked page carrying one.

Pasted text and the transcript are the citizen's own words: an instruction is
cut and the rest stays data (ADR-23). A linked page is a source: one with an
instruction drops out whole and the limitations say so (scenario E).

Features:
    US-BEZ-01, US-SPR-01, US-OBS-01, F-19, F-22, ADR-12, ADR-23
"""

from meritum_core.checks import InjectionEvent
from meritum_core.security.injection import instruction_removed

from meritum_worker.checks.constants import (
    INJECTION_EXCERPT_MAX_CHARS,
    LIMITATION_MAX_CHARS,
)
from meritum_worker.checks.models import CheckDeps, CheckState


async def screen_injection(state: CheckState, deps: CheckDeps) -> CheckState:
    """Scan the text, the transcript and the linked page with the detector.

    Args:
        state: the check so far.
        deps: the ports; only the injection detector is called.

    Returns:
        The state with instructions cut, a flagged page dropped and one
        InjectionEvent per finding.

    Features:
        US-BEZ-01, US-SPR-01, US-OBS-01, F-19, F-22, ADR-12, ADR-23
    """
    if state.result is not None:
        return state
    events: list[InjectionEvent] = []
    request = state.job.request
    text = await _cleaned(request.text, deps, events)
    transcript = await _cleaned(state.transcript, deps, events)
    page_text, limitations = state.page_text, state.limitations
    if page_text is not None and request.url is not None:
        scan = await deps.injection.scan(page_text)
        if scan.detected:
            first = scan.spans[0]
            excerpt = page_text[first.start : first.end][:INJECTION_EXCERPT_MAX_CHARS]
            url = str(request.url)
            events.append(
                InjectionEvent(
                    location="source",
                    action="source_dropped",
                    source_url=request.url,
                    excerpt=excerpt,
                )
            )
            page_text, limitations = None, [*limitations, url[:LIMITATION_MAX_CHARS]]
    if not events:
        return state
    job = state.job.model_copy(
        update={"request": request.model_copy(update={"text": text})}
    )
    return state.model_copy(
        update={
            "job": job,
            "transcript": transcript,
            "page_text": page_text,
            "limitations": limitations,
            "injection_events": [*state.injection_events, *events],
        }
    )


async def _cleaned(
    text: str | None, deps: CheckDeps, events: list[InjectionEvent]
) -> str | None:
    if text is None or not text.strip():
        return text
    cleaned = instruction_removed(await deps.injection.scan(text))
    events += cleaned.events
    return cleaned.text
