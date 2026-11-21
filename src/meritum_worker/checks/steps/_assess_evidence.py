"""Placeholder step that assesses each citation's stance.

Evidence assessment (worker#34) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def assess_evidence(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until evidence assessment (worker#34) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
