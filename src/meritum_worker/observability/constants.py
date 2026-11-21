"""Limits of the golden set case file.

Features:
    US-OBS-04, F-27, ADR-27
"""

from typing import Final

MAX_QUOTE_CHARS: Final = 300
"""Longest cited fragment of a source; full texts stay out of the repo (ADR-27)."""

MAX_TEXT_CHARS: Final = 4000
"""Longest case input text, the same limit as CheckRequest.text in meritum-core."""

REPEAT_VARIANTS: Final = frozenset({"same_session", "other_channel"})
"""Variants that repeat another case and so name it in related_case (G, H)."""

MIN_EVAL_CASES: Final = 30
"""Fewest cases an evaluation file may hold (US-OBS-05)."""

CSV_JSON_COLUMNS: Final = frozenset({"sources", "injection"})
"""CSV columns whose cells hold JSON, since a case nests them."""

DECISIVE_VERDICTS: Final = frozenset({"confirmed", "false", "misleading"})
"""Verdicts that settle a claim; a wrong one is the worst outcome (US-OBS-04)."""

ABSTAINING_VERDICTS: Final = frozenset({"insufficient_evidence", "not_verifiable"})
"""Verdicts that abstain from settling the claim."""

NON_VERDICT_CLASS: Final = "non_verdict"
"""macro-F1 class of every state that is not a verdict (US-OBS-04)."""

OUTCOME_ORDER: Final = ("wrong_decisive", "non_verdict", "wrong_abstention", "correct")
"""Case outcomes from the worst; several main-claim results keep the worst one."""

COST_SAMPLE_CHECKS: Final = 100
"""The report prices this many checks (the brief's cost of 100 tests)."""

LATENCY_PERCENTILE: Final = 95
"""Upper latency percentile next to the median, for comparing models."""

DEFAULT_MAX_CONCURRENCY: Final = 1
"""Cases checked at once by default; 1 keeps repeats after the cases they repeat
and keeps latency free of contention, so runs on different models compare."""

DEFAULT_CASES_FILE: Final = "evals/golden/cases.json"
"""Case file meritum-eval reads without --cases, relative to the repo root."""

EVAL_NAME: Final = "meritum-eval"
"""Name of the pydantic-evals dataset and experiment."""

REPORT_DECIMALS: Final = 4
"""Decimal places of every number in the report."""

UNANSWERED_VERDICT: Final = "insufficient_evidence"
"""Verdict that must reach the moderator queue to close the information loop."""

FAILURE_MESSAGE: Final = "status_hint.technical_failure"
"""Copy key of a case whose check raised, as the check workflow uses it."""

FAILURE_CODE: Final = "provider_unavailable"
"""failure_code of a case whose check raised before the workflow answered."""

NO_CORPUS_VERSION: Final = "none"
"""Corpus version of a case whose check raised before searching any corpus."""
