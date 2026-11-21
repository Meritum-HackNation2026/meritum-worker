"""Placeholder step that matches claims to known incidents.

Incident matching (worker#42) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def match_incidents(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until incident matching (worker#42) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
