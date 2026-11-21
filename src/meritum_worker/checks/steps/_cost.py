"""Placeholder step that prices model and search calls.

Check cost (worker#26) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def cost(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until check cost (worker#26) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
