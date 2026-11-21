"""Endpoints, limits and environment names of the injection classifier gate.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from typing import Final

ENV_PREFIX: Final = "MERITUM_INJECTION_GATE_"
"""Prefix of the gate's environment variables (``MERITUM_INJECTION_GATE_PROVIDER``)."""

DEFAULT_RETRIES: Final = 2
"""HTTP attempts per screened text, the first included; then the gate is skipped."""

HTTP_TIMEOUT_SECONDS: Final = 10.0
"""Longest wait for one provider reply; a slow gate must not stall the pipeline."""

RETRY_BACKOFF_SECONDS: Final = 0.5
"""Pause before the second attempt, doubled before each further one."""

CHUNK_CHARS: Final = 4000
"""Longest text sent in one gate request; longer pages are screened in chunks, so
they never hit a provider's size limit and skip the gate."""

CHUNK_OVERLAP_CHARS: Final = 200
"""Characters each chunk shares with the next, so a short instruction cut by a
chunk boundary is still whole in one of them."""

MODEL_ARMOR_LOCATION: Final = "eu"
"""Model Armor multi-region: texts are screened in the EU only (ADR-14)."""

MODEL_ARMOR_ENDPOINT: Final = (
    f"https://modelarmor.{MODEL_ARMOR_LOCATION}.rep.googleapis.com/v1"
)
"""Regional Model Armor REST endpoint; sanitization runs on regional endpoints only."""

MODEL_ARMOR_SCOPES: Final = ("https://www.googleapis.com/auth/cloud-platform",)
"""OAuth scope Model Armor accepts for Application Default Credentials."""

MODEL_ARMOR_EXECUTED: Final = "EXECUTION_SUCCESS"
"""``executionState`` of a filter that ran; any other state means it was skipped,
e.g. for a language or size it does not support."""

MODEL_ARMOR_MATCH: Final = "MATCH_FOUND"
"""``matchState`` of a filter that flagged the text."""

WORKERS_AI_ENDPOINT: Final = "https://api.cloudflare.com/client/v4/accounts"
"""Cloudflare API base; the run URL is ``{base}/{account}/ai/run/{model}``."""

WORKERS_AI_INJECTION_CATEGORIES: Final = frozenset({"S14"})
"""Llama Guard 3 hazard categories the gate flags: only S14 (code interpreter abuse)
is about steering the model. The others (violence, elections, defamation...) are
topics citizens ask Meritum to check, so cutting them would drop real claims."""
