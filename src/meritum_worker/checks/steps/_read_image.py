"""Placeholder step that reads text from a screenshot or photo.

Image reading (worker#39) replaces this module.

Features:
    US-SPR-01, US-OBS-01, F-22
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def read_image(state: CheckState, _deps: CheckDeps) -> CheckState:
    """Pass the state on unchanged until image reading (worker#39) lands.

    Args:
        state: the check so far.
        _deps: the ports; unused by the placeholder.

    Returns:
        The same state.

    Features:
        US-SPR-01, US-OBS-01, F-22
    """
    return state
