"""Constants of the moderation slice.

Features:
    US-MOD-01, US-MOD-02, F-24, ADR-22, ADR-35
"""

import re
from datetime import timedelta
from typing import Final, LiteralString

from meritum_core.checks.contracts import CaseReason
from meritum_core.jobs.contracts import CHECK

SIMILARITY_THRESHOLD: Final = 0.85
"""Cosine similarity of two claim embeddings above which the claims may be the
same; tuned only on the golden set (US-MOD-02)."""

TOPIC_THRESHOLD: Final = 0.65
"""Cosine similarity of a claim and a high-risk topic above which the claim falls
under the topic (ADR-35); tuned only on the golden set."""

SIMILARITY_WINDOW: Final = timedelta(days=14)
"""How far back an earlier unanswered claim or an open case still counts."""

HISTORY_LIMIT: Final = 500
"""Most finished checks read when looking for earlier unanswered claims."""

UNANSWERED_VERDICT: Final = "insufficient_evidence"
"""The verdict of a claim without an answer."""

RECHECK_CLAIM_WORKFLOW: Final = "recheck_claim"
"""DBOS name of one recheck after a new snapshot: the `check` workflow body with
its own CheckRecord (US-POW-03). Its result is a check's result like any other."""

CHECK_RESULT_WORKFLOWS: Final = (CHECK.name, RECHECK_CLAIM_WORKFLOW)
"""DBOS names of the workflows whose output is a ``CheckOutput``: moderators get
the claims of both, and both count as earlier unanswered claims."""

SUMMARY_MAX_CHARS: Final = 300
"""Longest ``ModeratorCase.summary``."""

CASE_ID_PREFIX: Final = "#S-"
"""A case id is this prefix and a number."""

NUMBER_PATTERN: Final = re.compile(r"\d+(?:[ .,]\d+)*")
"""A number in a claim; two claims with different numbers are different claims."""

PROPER_NAME_PATTERN: Final = re.compile(r"(?<=\s)[A-ZĄĆĘŁŃÓŚŹŻ][a-ząćęłńóśźż]+")
"""A capitalised word that does not open the claim: a proper name."""

NAME_STEM_CHARS: Final = 4
"""Letters compared of a proper name, so Polish inflections ("Pcim", "Pcimia") match."""

MONTH_STEMS: Final = (
    "stycz",
    "luty",
    "lutego",
    "marc",
    "kwie",
    "maj",
    "czerw",
    "lipc",
    "sierp",
    "wrze",
    "paźdz",
    "listop",
    "grud",
)
"""Stems of the Polish month names; a claim's months must agree too."""

STAFF_INBOX_PREFIX: Final = "staff:"
"""Prefix of a staff member's inbox id, as the backend reads it."""

STAFF_INBOX_HASH_CHARS: Final = 32
"""Hex characters of the address hash in the inbox id (backend contract)."""

PANEL_LINK: Final = "/panel"
"""In-app path of the moderator panel (meritum-frontend route)."""

ADMIN_EMAILS_ENV: Final = "MERITUM_ADMIN_EMAILS"
"""The backend's administrator list; they are moderators too."""

BASE_REASON: Final[dict[str, CaseReason]] = {
    "recommended_clicked": "insufficient_evidence",
    "user_dispute": "user_dispute",
}
"""The case reason a trigger gives by itself; the other triggers give none."""

ANSWER_NOTICE_WORKFLOW: Final = "case_answers"
"""Name of the scheduled workflow that tells askers a moderator answered."""

ANSWER_NOTICE_CRON: Final = "*/5 * * * *"
"""Every five minutes; a repeated run replaces entries, so it adds none."""

SERVED_OF_CHECK: Final[LiteralString] = (
    "SELECT served FROM result_cache_checks WHERE check_id = %s AND served IS NOT NULL"
)
"""The entry a cache hit got; the backend writes it with the hit (backend#25)."""
