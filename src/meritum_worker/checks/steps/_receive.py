"""Receive step: the backend already validated and masked the request.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def receive(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Accept the request as the backend sent it.

    Args:
        state: the check so far.
        _deps: the ports; unused.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
