"""Fact-checking quality metrics of one run: sources found, abstentions, ratings.

Features:
    US-OBS-04, US-OBS-05, F-27
"""

from collections.abc import Sequence
from urllib.parse import urlsplit

from meritum_core.checks.contracts import ClaimResult

from meritum_worker.observability.constants import (
    ABSTAINING_VERDICTS,
    FACT_CHECKED_CATEGORY,
    REPORT_DECIMALS,
)
from meritum_worker.observability.report import CaseRun, Ratio


def abstention_rate(runs: Sequence[CaseRun]) -> Ratio:
    """Answered checks whose main claims got no decision.

    Args:
        runs: One run per case.

    Returns:
        The share of done results with only abstaining verdicts; None without any.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    done = [run.result for run in runs if run.result.status == "done"]
    return share([_abstains(result.claims) for result in done])


def citation_recall(runs: Sequence[CaseRun]) -> Ratio:
    """Mean share of a case's expected source hosts the answer cited or rated.

    A fact-checker's rating counts by its link, like a citation.

    Args:
        runs: One run per case.

    Returns:
        The mean over cases that list sources; None when none does.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    shares: list[float] = []
    for run in runs:
        expected = {host(str(source.url)) for source in run.case.sources}
        if expected:
            found = _found_hosts(run.result.claims)
            shares.append(len(expected & found) / len(expected))
    return _round(sum(shares) / len(shares)) if shares else None


def fact_check_hit_rate(runs: Sequence[CaseRun]) -> Ratio:
    """Cases with a fact-checker's rating whose answer shows any rating.

    Args:
        runs: One run per case.

    Returns:
        The share of ``fact_checked`` cases with a rating; None without any.

    Features:
        US-OBS-04, US-KOR-01, F-14, F-27
    """
    rated = [run for run in runs if run.case.category == FACT_CHECKED_CATEGORY]
    return share([_has_rating(run.result.claims) for run in rated])


def share(hits: Sequence[bool]) -> Ratio:
    """The rounded share of true values.

    Args:
        hits: One value per counted item.

    Returns:
        The share; None for no items.

    Features:
        US-OBS-04, F-27
    """
    return _round(sum(hits) / len(hits)) if hits else None


def host(url: str) -> str:
    """A link's host without ``www.``, how sources are compared.

    Args:
        url: The link.

    Returns:
        The host; empty for a link without one.

    Features:
        US-OBS-04, F-27
    """
    return (urlsplit(url).hostname or "").removeprefix("www.")


def _abstains(claims: Sequence[ClaimResult]) -> bool:
    return bool(claims) and all(c.verdict in ABSTAINING_VERDICTS for c in claims)


def _found_hosts(claims: Sequence[ClaimResult]) -> set[str]:
    links = [str(c.source.url) for claim in claims for c in claim.citations]
    for claim in claims:
        links += [str(r.url) for r in claim.claim_review_premises]
        links += [str(r.url) for r in claim.claim_reviews]
    return {host(link) for link in links}


def _has_rating(claims: Sequence[ClaimResult]) -> bool:
    return any(claim.claim_review_premises or claim.claim_reviews for claim in claims)


def _round(value: float) -> float:
    return round(value, REPORT_DECIMALS)
