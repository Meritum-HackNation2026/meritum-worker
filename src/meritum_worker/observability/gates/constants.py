"""Names and labels of the gate comparison.

Features:
    US-BEZ-01, US-OBS-04, F-27, ADR-35
"""

from typing import Final
from zoneinfo import ZoneInfo

GATES_COMMAND: Final = "gates"
"""First argument of meritum-eval that starts the gate comparison."""

CLAIM_CLASS: Final = "claim"
"""Input classifier class of a case the main model must check."""

CLAIM_STATUSES: Final = frozenset({"done", "technical_failure"})
"""Expected states of a case whose input is a claim (a failure is forced later)."""

REPORT_ZONE: Final = ZoneInfo("Europe/Warsaw")
"""Time zone of the report's date: the day the team ran it, in Poland."""

COST_SAMPLE_CALLS: Final = 100
"""The report prices this many gate calls."""

PAGE_ATTACK: Final = "source_page"
"""Injection place of an attack hidden on a source page."""
