"""Add the neutral EU sanctions note to the answer when the link is to a listed entity.

Features:
    US-ZRD-07, US-OBS-01, F-22, F-34
"""

from meritum_worker.checks.models import CheckDeps, CheckState


async def sanctions_warning(state: CheckState, deps: CheckDeps) -> CheckState:
    """Set ``source_warning`` from the local EU list; the verdicts stay as they are.

    The warning rests only on a current entry of the official list whose domain
    is the link's. Pasted text, a failed check or no match leaves the result
    untouched.

    Args:
        state: the check so far, after write_answer.
        deps: the ports; the local copy of the sanctions list is read.

    Returns:
        The state, with the warning on its result when the link matches.

    Features:
        US-ZRD-07, US-OBS-01, F-22, F-34
    """
    link = state.job.request.url
    if link is None or state.result is None or state.result.status != "done":
        return state
    day = state.job.received_at.date()
    warning = deps.sanctions.warning_for(str(link), on=day)
    if warning is None:
        return state
    result = state.result.model_copy(update={"source_warning": warning})
    return state.model_copy(update={"result": result})
