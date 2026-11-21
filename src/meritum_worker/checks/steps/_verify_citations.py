"""Placeholder step that keeps only quotes found verbatim in the source.

Citation verification replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def verify_citations(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until citation verification lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
