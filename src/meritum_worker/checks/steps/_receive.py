"""Receive step: the backend already validated and masked the request.

Features:
    US-SPR-01, US-SPR-07, US-OBS-01, F-06, F-22
"""

from meritum_core.checks.constants import MIN_TEXT_CHARS
from pydantic import HttpUrl, ValidationError

from meritum_worker.checks.constants import LINK_IN_TEXT, LINK_TRAILING
from meritum_worker.checks.models import CheckDeps, CheckState


async def receive(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Accept the request; a link written inside the text becomes its link.

    Channels send what the citizen typed, so „Czy ten artykuł mówi prawdę
    https://…” arrives as text with no ``url``. The first http(s) address in
    the text is copied to ``request.url``, so every later step treats it as the
    citizen's link. The text stays as typed; a text that is only the address
    is dropped, which makes it a plain link check. A request that already has
    a ``url`` is left alone.

    Args:
        state: the check so far.
        _deps: the ports; unused.

    Returns:
        The state, with the link lifted out of the text when there is one.

    Features:
        US-SPR-01, US-SPR-07, US-OBS-01, F-06, F-22
    """
    request = state.job.request
    text = request.text or ""
    found = LINK_IN_TEXT.search(text)
    if request.url is not None or found is None:
        return state
    try:
        url = HttpUrl(found.group().rstrip(LINK_TRAILING))
    except ValidationError:
        return state
    rest = text[: found.start()] + text[found.end() :]
    only_link = len(rest.strip(LINK_TRAILING + " \n\t(")) < MIN_TEXT_CHARS
    lifted = request.model_copy(
        update={"url": url, "text": None if only_link else request.text}
    )
    return state.model_copy(
        update={"job": state.job.model_copy(update={"request": lifted})}
    )
