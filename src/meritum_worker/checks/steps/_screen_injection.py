"""Placeholder step that cuts instructions out of the input.

The injection detector (worker#23) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def screen_injection(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until the injection detector (worker#23) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
