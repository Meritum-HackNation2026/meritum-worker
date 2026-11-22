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

FAILURE_MESSAGE: Final = "The check raised before the workflow answered."
"""Diagnostic of a case whose check raised; never shown to citizens (#70)."""

FAILURE_CODE: Final = "provider_unavailable"
"""failure_code of a case whose check raised before the workflow answered."""

NO_CORPUS_VERSION: Final = "none"
"""Corpus version of a case whose check raised before searching any corpus."""

OUT_OF_SCOPE_MESSAGE: Final = "A screenshot without text cannot be read without OCR."
"""Diagnostic of a screenshot-only case; never shown to citizens (#70)."""

ENV_NAME_VAR: Final = "MERITUM_ENV"
"""Environment variable naming the worker's env; ``local`` picks the local path."""

LOCAL_ENV: Final = "local"
"""MERITUM_ENV of a worker run on a laptop; every other value is the public demo."""

DEMO_PATH: Final = "demo"
"""Path of a worker under dev or prd: the public demo."""

REQUIRED_ENV: Final = {
    LOCAL_ENV: (),
    DEMO_PATH: ("MERITUM_DATABASE_URL",),
}
"""Variables each path needs, before the model's; README lists the same.

The EUvsDisinfo token is optional: without it the provider is only unavailable (#102).
"""

LLM_PROVIDER_VAR: Final = "MERITUM_LLM_PROVIDER"
"""Variable choosing the model adapter; unset means meritum-core's default."""

LLM_REQUIRED_ENV: Final = {
    "stub": (),
    "vertex": ("MERITUM_LLM_MODEL", "MERITUM_LLM_REGION"),
    "openrouter": ("OPENROUTER_API_KEY",),
}
"""Variables each model provider needs on top of its path (core#97: openrouter)."""

EUVSDISINFO_PROBE: Final = "euvsdisinfo"
"""Provider name of the EUvsDisinfo MCP server in the readiness report."""

RETRIEVAL_TOP_K: Final = 1
"""Ranks that count as a hit; the stand-in corpus has about a dozen documents, so
only the first rank separates candidates (worker#40)."""

STAND_IN_CORPUS: Final = "stand-in: golden-set sources, one query per main claim"
"""Corpus label of the embeddings report until a run searches the real corpus."""

CHARS_PER_PRICE_UNIT: Final = 1_000_000
"""Characters in the unit of an embedding price (usd_per_million_chars)."""

API_KEY_FIELDS: Final = frozenset({"openrouter_api_key"})
"""LlmSettings fields (any case) a committed config file must not set."""

COST_DECIMALS: Final = 8
"""Decimal places of an embedding cost; a golden-set run costs fractions of a cent."""

COST_SAMPLE_QUERIES: Final = 100
"""The embeddings report prices this many corpus queries."""

BUNDLE_NAME: Final = "meritum-eval-bundle"
"""Name of the command that writes the public reproduction bundle."""

BUNDLE_FILES: Final = ("cases.json", "sources.json", "manifest.json")
"""Files of the public bundle: cases, their sources with quotes, the manifest."""

EVAL_RUN_LINK: Final = "/ewaluacja/{run_id}"
"""In-app path of a finished run, opened by its eval_run_done notification."""

EVAL_RUN_DONE_KEY: Final = "eval_run_done:{run_id}"
"""Notification key; one per run, so a retried workflow notifies once."""

CREATE_EVAL_RUNS_SQL: Final = (
    "CREATE TABLE IF NOT EXISTS eval_runs (id text PRIMARY KEY,"
    " user_id text, started_at timestamptz NOT NULL, run jsonb NOT NULL)"
)
"""Creates the table of stored runs (adapters/_postgres_runs.py)."""

UPSERT_EVAL_RUN_SQL: Final = (
    "INSERT INTO eval_runs (id, user_id, started_at, run) VALUES (%s, %s, %s, %s)"
    " ON CONFLICT (id) DO UPDATE SET run = excluded.run"
)
"""Stores a run, replacing the one with the same id."""

EVAL_FILES_DIR_VAR: Final = "MERITUM_EVAL_FILES_DIR"
"""Variable naming the directory of uploaded case files."""

DEFAULT_EVAL_FILES_DIR: Final = "evals/uploads"
"""Uploads directory without ``MERITUM_EVAL_FILES_DIR``, relative to the repo root."""
