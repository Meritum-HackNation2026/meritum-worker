"""Placeholder step that reads fact-checkers' ratings.

Fact-check search (worker#43) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def search_fact_checks(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until fact-check search (worker#43) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
