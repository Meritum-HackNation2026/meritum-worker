"""Fetch the page behind a citizen's link and check its text like a pasted one.

Features:
    US-SPR-07, US-ZRD-05, F-06, ADR-12
"""

from meritum_core.corpus.fetching import FetchPurpose, PageFetchError
from meritum_core.security.pii import mask_personal_data

from meritum_worker.checks.constants import (
    FETCH_URL_STEP,
    LIMITATION_MAX_CHARS,
    LINK_UNREAD_NOTE,
    PAGE_DATE_ZONE,
)
from meritum_worker.checks.models import CheckDeps, CheckState
from meritum_worker.corpus import MAX_PAGE_TEXT_CHARS


async def fetch_url(state: CheckState, deps: CheckDeps) -> CheckState:
    """Read the link through the SSRF-safe fetcher; a check with no link skips it.

    The page is read also when the citizen wrote text next to the link, such
    as a question about the article. The page text is masked like the input
    and cut to the length of a pasted text; it stays data for every later
    prompt (ADR-12). Any fetch failure (an internal address, the network,
    robots.txt, a login wall or a paywall) or an empty page marks the step
    failed and adds a limitation saying the page was not read; the check goes
    on with the citizen's text and the address, and extract_claims ends it as
    url_unavailable when those hold no claim. A publication date later than
    the check's receipt is dropped as wrong metadata.

    Args:
        state: the check so far.
        deps: the ports; the page fetcher and the masking gate are called.

    Returns:
        The state with the masked page text, with the step marked failed and
        the limitation, or with the step marked skipped.

    Features:
        US-SPR-07, US-ZRD-05, F-06, ADR-12
    """
    url = state.job.request.url
    if url is None:
        return state.model_copy(
            update={"skipped_steps": [*state.skipped_steps, FETCH_URL_STEP]}
        )
    try:
        page = await deps.pages.fetch(str(url), purpose=FetchPurpose.USER_LINK)
    except PageFetchError:
        page = None
    # An empty plain-text page has nothing to check, like a page we could not open.
    if page is None or not page.untrusted_text.strip():
        note = LINK_UNREAD_NOTE.format(host=url.host)[:LIMITATION_MAX_CHARS]
        return state.model_copy(
            update={
                "failed_steps": [*state.failed_steps, FETCH_URL_STEP],
                "limitations": [*state.limitations, note],
            }
        )
    masked = await mask_personal_data(
        page.untrusted_text[:MAX_PAGE_TEXT_CHARS], deps.pii
    )
    # Cut again: a marker can be longer than the personal data it replaced.
    text = masked.text[:MAX_PAGE_TEXT_CHARS]
    # shortcut: the check's receipt day stands in for the fetch moment (no fetch
    # clock in FetchedPage); a page dated after it has wrong metadata.
    received_on = state.job.received_at.astimezone(PAGE_DATE_ZONE).date()
    published = page.published_at
    if published is not None and published > received_on:
        published = None
    return state.model_copy(update={"page_text": text, "published_at": published})
