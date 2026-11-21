"""Fetch the page behind a citizen's link and check its text like a pasted one.

Features:
    US-SPR-07, US-ZRD-05, F-06, ADR-12
"""

from meritum_core.checks import CheckResult
from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.security.pii import mask_personal_data

from meritum_worker.checks.constants import (
    MAX_PAGE_TEXT_CHARS,
    URL_UNAVAILABLE_CODE,
    URL_UNAVAILABLE_MESSAGE,
)
from meritum_worker.checks.models import CheckDeps, CheckState


async def fetch_url(state: CheckState, deps: CheckDeps) -> CheckState:
    """Read the link through the SSRF-safe fetcher; a text without a link skips it.

    The page text is masked like the input and cut to the length of a pasted
    text; it stays data for every later prompt (ADR-12). Any fetch failure (an
    internal address, the network, a login wall or a paywall) ends the check as
    technical_failure with code url_unavailable and a request to paste the text.

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
    if url is None:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, "fetch_url"]}
        )
    try:
        page = await deps.pages.fetch(str(url), purpose=FetchPurpose.USER_LINK)
    except PageFetchError:
        return state.model_copy(update={"result": _url_unavailable(state)})
    masked = await mask_personal_data(
        page.untrusted_text[:MAX_PAGE_TEXT_CHARS], deps.pii
    )
    text = masked.text
    return state.model_copy(update={"page_text": text[:MAX_PAGE_TEXT_CHARS]})


def _url_unavailable(state: CheckState) -> CheckResult:
    return CheckResult(
        check_id=state.check_id,
        status="technical_failure",
        message=URL_UNAVAILABLE_MESSAGE,
        failure_code=URL_UNAVAILABLE_CODE,
        corpus_version=state.corpus_version,
    )
