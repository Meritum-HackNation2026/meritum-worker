"""Fetch the page behind a citizen's link and check its text like a pasted one.

Features:
    US-SPR-07, US-ZRD-05, F-06, ADR-12
"""

from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.security.pii import mask_personal_data

from meritum_worker.checks.constants import (
    FETCH_URL_STEP,
    MAX_PAGE_TEXT_CHARS,
    URL_UNAVAILABLE_CODE,
    URL_UNAVAILABLE_MESSAGE,
)
from meritum_worker.checks.models import CheckDeps, CheckState


async def fetch_url(state: CheckState, deps: CheckDeps) -> CheckState:
    """Read the link through the SSRF-safe fetcher; pasted text or no link skips it.

    The page text is masked like the input and cut to the length of a pasted
    text; it stays data for every later prompt (ADR-12). Any fetch failure (an
    internal address, the network, a login wall or a paywall) or an empty page
    ends the check as technical_failure with code url_unavailable and a request
    to paste the text.

    Args:
        state: the check so far.
        deps: the ports; the page fetcher and the masking gate are called.

    Returns:
        The state with the masked page text, with a technical failure, or
        with the step marked skipped.

    Features:
        US-SPR-07, US-ZRD-05, F-06, ADR-12
    """
    url = state.job.request.url
    # Pasted text is what the citizen wants checked; a link next to it is context.
    if url is None or state.has_text:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, FETCH_URL_STEP]}
        )
    try:
        page = await deps.pages.fetch(str(url), purpose=FetchPurpose.USER_LINK)
    except PageFetchError:
        page = None
    # An empty plain-text page has nothing to check, like a page we could not open.
    if page is None or not page.untrusted_text.strip():
        failure = state.technical_failure(URL_UNAVAILABLE_CODE, URL_UNAVAILABLE_MESSAGE)
        return state.model_copy(update={"result": failure})
    masked = await mask_personal_data(
        page.untrusted_text[:MAX_PAGE_TEXT_CHARS], deps.pii
    )
    # Cut again: a marker can be longer than the personal data it replaced.
    return state.model_copy(update={"page_text": masked.text[:MAX_PAGE_TEXT_CHARS]})
