"""Constants of the `check` workflow.

Features:
    US-SPR-01, US-SPR-03, US-SPR-06, US-ZRD-05, US-OBS-01, US-BEZ-03, F-07, F-18, F-22
"""

import re
from datetime import timedelta
from types import MappingProxyType
from typing import Final
from zoneinfo import ZoneInfo

from meritum_core.checks.contracts import FailureCode, ModelUsage
from meritum_core.checks.transcription import MAX_AUDIO_BYTES, MAX_AUDIO_SECONDS

from meritum_worker.corpus import WEB_SEARCH_MARGIN, WEB_SEARCH_TIMEOUT

RECORD_RETENTION: Final = timedelta(days=30)
"""How long a CheckRecord is kept: retention_until = received_at + 30 days (ADR-13)."""

NO_CORPUS_VERSION: Final = "none"
"""Corpus version of a check that searched no corpus snapshot (the stub step)."""

TECHNICAL_FAILURE_MESSAGE: Final = "The worker could not produce a valid result."
"""Diagnostic for a technical failure."""

TECHNICAL_FAILURE_CODE: Final[FailureCode] = "provider_unavailable"
"""failure_code of a technical failure: the model call failed or broke the rules."""

MAX_CLAIMS_PER_CHECK: Final = 5
"""Most claims checked from one request; the rest go to limitations (US-SPR-03, F-07).

Facts take the places first, so opinions never push a fact out of the check. Each
claim over the limit is one limitation holding the claim's own text, so no Polish
copy lives in code.
"""

PAGE_DATE_ZONE: Final = ZoneInfo("Europe/Warsaw")
"""Zone a page's metadata date is read in: Polish pages date their articles locally."""

NEEDS_CLARIFICATION_MESSAGE: Final = "Claim extraction found no claims."
"""Diagnostic for an input with no claims."""

OUT_OF_SCOPE_MESSAGE: Final = "Claim extraction classified the input as out of scope."
"""Diagnostic for a request outside the scope of a check."""

LIMITATION_MAX_CHARS: Final = 300
"""Longest limitation CheckResult accepts; a longer skipped claim is cut to fit."""

PARTIAL_SUPPORT_NOTE: Final = (
    "Nie potwierdzono: {missing}. Źródła potwierdzają tylko część twierdzenia"
    " „{claim}”."
)
"""Limitation for a fact whose sources confirm only a part of it."""

EXPLANATION_MAX_CHARS: Final = 800
"""Longest ClaimResult.explanation; a longer model text is cut to fit."""

DRAFT_MAX_CHARS: Final = 4000
"""Longest AnalysisStatus.draft."""

ANSWER_ATTEMPTS: Final = 2
"""Model calls write_answer makes before an answer breaking the contract is a
technical failure (worker#194)."""

UNRESOLVED_MAX_CHARS: Final = 500
"""Longest ClaimResult.unresolved; a longer model text is cut to fit."""

SENTENCE_END: Final = re.compile(r"[.!?](?=\s)")
"""End of a sentence followed by more text: where a too long model text is cut."""

FETCH_URL_STEP: Final = "fetch_url"
"""AnalysisStep code of fetching the citizen's link; skipped when there is none."""

URL_UNAVAILABLE_CODE: Final[FailureCode] = "url_unavailable"
"""failure_code of a check whose link could not be fetched (contract v4)."""

URL_UNAVAILABLE_MESSAGE: Final = (
    "The link could not be fetched; the citizen should paste the text."
)
"""Diagnostic for a link that could not be fetched."""

STEP_TIMEOUTS: Final[dict[str, timedelta]] = {
    "receive": timedelta(seconds=100),
    "fetch_url": timedelta(seconds=30),
    "transcribe_audio": timedelta(minutes=16),
    "screen_injection": timedelta(seconds=30),
    "extract_claims": timedelta(seconds=90),
    "search_corpus": timedelta(seconds=30),
    "search_web": WEB_SEARCH_TIMEOUT + WEB_SEARCH_MARGIN,
    "search_fact_checks": timedelta(seconds=30),
    "assess_evidence": timedelta(seconds=90),
    "verify_citations": timedelta(seconds=30),
    "write_answer": timedelta(seconds=90),
    "save_record": timedelta(seconds=30),
}
"""Longest wait per AnalysisStep code (US-SPR-06, F-18).

search_web keeps its own 10 s deadline (WEB_SEARCH_TIMEOUT) for the searches
and pages; this backstop adds WEB_SEARCH_MARGIN so pages drop out first.

Transcription allows for the core batch mode (up to 15 min for 10 min of
audio); model codes allow for the core adapter's retries; a timeout ends the check as
technical_failure. receive also runs read_image (OCR: 3 calls of 30 s).
"""

TRANSCRIPTION_FAILED_CODE: Final[FailureCode] = "transcription_failed"
"""failure_code of a check whose voice message could not be transcribed."""

WEB_SEARCH_UNAVAILABLE_CODE: Final[FailureCode] = "web_search_unavailable"
"""failure_code of a check whose web search failed or timed out."""

TIMEOUT_REASON: Final = "timeout"
"""What retrieval_errors records after ``<step code>: `` for a step that timed out."""

STEP_FAILURE_CODES: Final[dict[str, FailureCode]] = {
    "fetch_url": URL_UNAVAILABLE_CODE,
    "transcribe_audio": TRANSCRIPTION_FAILED_CODE,
    "search_web": WEB_SEARCH_UNAVAILABLE_CODE,
}
"""failure_code of a failed or timed-out step code; any other: provider_unavailable."""

TRANSCRIBE_AUDIO_STEP: Final = "transcribe_audio"
"""AnalysisStep code of transcribing a voice message; skipped without audio."""

MAX_TRANSCRIPT_CHARS: Final = 4000
"""Longest transcript checked and shown: the limit of a pasted text and of
CheckResult.transcript."""

UNSUPPORTED_AUDIO_FORMAT_MESSAGE: Final = (
    "The recording format is not supported; send OGG Opus, MP3, M4A or WAV, "
    "or paste the text."
)
"""Diagnostic for a recording the transcription port does not accept."""

AUDIO_TOO_LONG_MESSAGE: Final = (
    f"The recording is over {MAX_AUDIO_SECONDS // 60} minutes or "
    f"{MAX_AUDIO_BYTES // 2**20} MiB; send a shorter one or the text."
)
"""Diagnostic for a recording over the transcription limits."""

LONG_AUDIO_SECONDS: Final = 55
"""Recordings longer than this go to the provider's batch mode (core
SYNC_MAX_SECONDS); their end is announced with a check_done notification."""

CHECK_LINK: Final = "/sprawdzenie/{check_id}"
"""In-app path of a check's result (meritum-frontend route)."""

SEARCH_WEB_STEP: Final = "search_web"
"""AnalysisStep code of live web search; skipped when the check has no fact."""

NOTIFICATION_RETENTION: Final = timedelta(days=30)
"""How long a Notification is kept: retention_until = created_at + 30 days."""

USER_ID_PATTERN: Final = re.compile(r"^[^:\s]+:\S+$")
"""A signed-in user id as the backend reads it: ``{provider}:{subject}``."""

SEARCH_CORPUS_STEP: Final = "search_corpus"
"""AnalysisStep code of the corpus research agent; skipped with no fact or snapshot."""

CORPUS_VERSION_ENV: Final = "MERITUM_CORPUS_VERSION"
"""Environment variable pinning the corpus snapshot checks search; unset: none."""

INJECTION_EXCERPT_MAX_CHARS: Final = 300
"""Longest InjectionEvent.excerpt the contract accepts (US-BEZ-01)."""

VERDICT_LABELS: Final = {
    "confirmed": "Potwierdzone",
    "false": "Fałszywe",
    "misleading": "Wprowadzające w błąd",
    "insufficient_evidence": "Brak wystarczających dowodów",
    "not_verifiable": "Nie podlega weryfikacji",
}
"""Polish verdict names, as in copy/pl.json (verdict.*); the user never sees a code."""

STANCE_LABELS: Final = {
    "supports": "potwierdza",
    "refutes": "przeczy",
    "context": "daje kontekst",
}
"""Polish stance names for the model data, so no code reaches its text."""

CODE_PATTERN: Final = re.compile(
    r"\b(" + "|".join([*VERDICT_LABELS, "supports", "refutes"]) + r")\b"
)
"""A verdict or stance code standing alone in a model text (write_answer post-check)."""

WEB_SEARCH_PRICES: Final = MappingProxyType(
    {
        "stub": ModelUsage(
            provider="stub",
            model="stub",
            region="local",
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
        ),
        "vertex_search": ModelUsage(
            provider="vertex_search",
            model="basic_website_search",
            region="global",
            input_tokens=0,
            output_tokens=0,
            cost_usd=1.5 / 1000,
        ),
    }
)
"""Usage of one web search per provider; cost_usd is one call (US-OBS-02, F-23).

Vertex AI Search Standard: USD 1.50 per 1,000 queries (2026-11-22); stub is free.
"""

SOURCE_DROPPED_NOTE: Final = (
    "Pominęliśmy stronę {host}, bo zawierała polecenia dla modelu."
)
"""Limitation for a page the injection detector dropped; the full address stays in
the InjectionEvent for moderators, the citizen gets the host only."""
