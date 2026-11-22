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

REVIEW_RATING_MAX_CHARS: Final = 120
"""Longest textualRating ClaimReviewPremise and ClaimReviewContext accept; a longer
rating is dropped, since cutting it would no longer be the rating verbatim."""

REVIEW_TITLE_MAX_CHARS: Final = 200
"""Longest fact-check title ``ClaimReviewPremise`` accepts; longer ones are cut."""

FACT_CHECK_PHRASES_PER_FACT: Final = 4
"""Most key phrases searched per fact besides the full claim. The API matches
phrases literally (worker#84), so a short phrase with the claim's names, places
and numbers finds a review the whole sentence misses; four covers the entities
of a typical claim without flooding the index with one-word queries."""

FACT_CHECK_QUERIES_PER_CHECK: Final = 16
"""Most Fact Check Tools searches per check: every full claim first, then the
phrases fact by fact. Two rounds of FACT_CHECK_PARALLEL_QUERIES, each at most
FACT_CHECK_TIMEOUT_SECONDS, stay under the step's 30 s backstop."""

FACT_CHECK_PARALLEL_QUERIES: Final = 8
"""Fact Check Tools searches in flight at once; the API's default quota is per
minute, far above one check's 16 calls."""

FACT_CHECK_SIMILARITY_THRESHOLD: Final = 0.8
"""Cosine similarity of the fact and a review's ``claimReviewed`` from which the
review goes on to the model's comparison of topic, numbers and date (ADR-34).
gemini-embedding-001 gives paraphrases of one Polish claim about 0.85 to 0.95
and claims on the same topic about another place or number about 0.7 to 0.8;
to be tuned on the golden set (worker#13)."""

FACT_CHECK_CONTEXT_MIN_SIMILARITY: Final = 0.6
"""Below this similarity a review is about something else and is dropped;
between it and FACT_CHECK_SIMILARITY_THRESHOLD it stays context with a link.
Phrase queries such as a city name return many unrelated reviews."""
