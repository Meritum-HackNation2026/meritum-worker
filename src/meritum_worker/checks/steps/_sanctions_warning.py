"""Placeholder step that warns about content from a sanctioned entity.

The sanctions warning (worker#46) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def sanctions_warning(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until the sanctions warning (worker#46) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
