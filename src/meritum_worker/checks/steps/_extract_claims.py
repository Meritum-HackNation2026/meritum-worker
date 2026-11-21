"""Placeholder step that extracts up to 5 dated claims.

Claim extraction (worker#20) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def extract_claims(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until claim extraction (worker#20) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
