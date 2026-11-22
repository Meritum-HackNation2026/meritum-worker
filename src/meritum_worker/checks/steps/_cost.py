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
    price from ``WEB_SEARCH_PRICES`` (0 for a provider missing there). Media
    searches that went through OpenRouter get their own entry at
    ``deps.news_search_price``.

    Args:
        state: the check so far.
        deps: the ports; only the search provider name and the media price are read.

    Returns:
        The state with the search entries, or the same state without searches.

    Features:
        US-SPR-01, US-OBS-02, F-22, F-23
    """
    if state.web_search_calls == 0:
        return state
    # Media searches cost the catalogue provider's price unless OpenRouter ran them.
    news = state.news_search_calls if deps.news_search_price else 0
    price = WEB_SEARCH_PRICES.get(deps.web_search_provider)
    if price is None:
        price = WEB_SEARCH_PRICES["stub"].model_copy(
            update={"provider": deps.web_search_provider}
        )
    priced = [(price, state.web_search_calls - news), (deps.news_search_price, news)]
    usages = [
        entry.model_copy(update={"cost_usd": entry.cost_usd * count})
        for entry, count in priced
        if entry is not None and count
    ]
    return state.model_copy(update={"models": [*state.models, *usages]})
