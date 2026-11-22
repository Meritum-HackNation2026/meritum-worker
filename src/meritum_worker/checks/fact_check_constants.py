"""Constants of the fact-check search step.

Features:
    US-KOR-01, US-BEZ-03, F-14, F-18, ADR-34
"""

from typing import Final

SEARCH_FACT_CHECKS_STEP: Final = "search_fact_checks"
"""AnalysisStep code of the fact-check search; skipped when the check has no fact."""

FACT_CHECK_UNAVAILABLE_NOTE: Final = (
    "Nie udało się sprawdzić indeksu Google Fact Check z powodu błędu dostępu;"
    " to nie znaczy, że takiej oceny albo artykułu nie ma."
)
"""Limitation text of ``fact_check_unavailable``: the index was not checked, and
never that the review does not exist (scenario J)."""
