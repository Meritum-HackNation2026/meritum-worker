"""Constants of the fact-check search (Google Fact Check Tools API).

Features:
    US-KOR-01, F-14, ADR-34
"""

from typing import Final

FACT_CHECK_URL: Final = "https://factchecktools.googleapis.com/v1alpha1/claims:search"
"""Google Fact Check Tools API search endpoint (ClaimReview index)."""

FACT_CHECK_NO_KEY: Final = "no_api_key"
"""Reason of the unavailable error for a missing API key; never the key itself."""

FACT_CHECK_ENV_PREFIX: Final = "MERITUM_FACT_CHECK_"
"""Prefix of the Fact Check Tools settings (``_PROVIDER``, ``_API_KEY``)."""

FACT_CHECK_LANGUAGE: Final = "pl"
"""Language the claims are searched in."""

FACT_CHECK_TIMEOUT_SECONDS: Final = 10.0
"""Timeout of one Fact Check Tools call; the step's backstop is 30 s."""

REVIEW_TITLE_MAX_CHARS: Final = 200
"""Longest fact-check title ``ClaimReviewPremise`` accepts; longer ones are cut."""
