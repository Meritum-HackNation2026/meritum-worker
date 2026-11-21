"""Placeholder step that fetches the page behind a link safely.

Fetching user links (worker#30) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def fetch_url(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until fetching user links (worker#30) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
