"""Price the web searches of the check; model calls carry their own cost.

Features:
    US-SPR-01, US-OBS-02, F-22, F-23
"""

from meritum_worker.checks.constants import WEB_SEARCH_PRICES
from meritum_worker.checks.models import CheckDeps, CheckState


async def cost(state: CheckState, deps: CheckDeps) -> CheckState:
    """Add one usage entry for the check's web searches, priced per call.

    Model calls already hold the cost the model port reported; the search
    entry has no tokens and costs ``web_search_calls`` times the provider's
    price from ``WEB_SEARCH_PRICES`` (0 for a provider missing there).

    Args:
        state: the check so far.
        deps: the ports; only the web search provider name is read.

    Returns:
        The state with the search entry, or the same state without searches.

    Features:
        US-SPR-01, US-OBS-02, F-22, F-23
    """
    calls = state.web_search_calls
    if calls == 0:
        return state
    price = WEB_SEARCH_PRICES.get(deps.web_search_provider)
    if price is None:
        price = WEB_SEARCH_PRICES["stub"].model_copy(
            update={"provider": deps.web_search_provider}
        )
    usage = price.model_copy(update={"cost_usd": price.cost_usd * calls})
    return state.model_copy(update={"models": [*state.models, usage]})
