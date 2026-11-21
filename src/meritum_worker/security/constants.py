"""Constants of the security slice: the injection classifier gate and retention.

Features:
    US-BEZ-01, US-BEZ-05, US-POW-04, F-19, F-20, ADR-12, ADR-13, ADR-35
"""

from datetime import timedelta
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

MAX_CHUNKS: Final = 25
"""Most chunks screened per text (about 95 000 characters): a page is outside
input, so its length must not set the number of paid requests. The rest of the
text is skipped with a log line."""

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

DATA_RETENTION: Final = timedelta(days=30)
"""How long user data lives: check records, notifications, DBOS workflow data and
uploaded files (ADR-13, US-BEZ-05, US-POW-04)."""

ERASURE_RESULT_KEPT: Final = timedelta(hours=1)
"""How long a finished ``delete_subject`` run stays in DBOS so the backend can read
its result; its input names the person, so the next hourly retention run after
that deletes it (at most two hours after the erasure)."""

RETENTION_BATCH: Final = 500
"""Most expired check records deleted in one round of the retention run."""

WORKFLOW_PAGE: Final = 200
"""Workflows read from DBOS per page while looking for one person's data."""

FINISHED_STATUSES: Final = (
    "SUCCESS",
    "ERROR",
    "CANCELLED",
    "MAX_RECOVERY_ATTEMPTS_EXCEEDED",
)
"""DBOS statuses of a workflow that will not run again; a ``delete_subject`` run
goes after an hour only in one of these."""

RETENTION_WORKFLOW: Final = "retention"
"""DBOS name of the daily retention workflow; its schedule starts it, never the API."""

RETENTION_SCHEDULE_NAME: Final = "retention_hourly"
"""Name of the DBOS schedule that starts the retention workflow."""

RETENTION_CRON: Final = "15 * * * *"
"""When the retention workflow runs: every hour at :15 UTC. Expired records need a
daily run; erasure runs (ERASURE_RESULT_KEPT) need the hourly one."""

BLOB_PROVIDER_ENV: Final = "MERITUM_BLOB_PROVIDER"
"""Environment variable naming the blob store; a worker without it has no files."""

CHECK_ID_FIELD: Final = "check_id"
"""Field of an ``EscalateClaimInput`` that names its check."""

REQUEST_FIELD: Final = "request"
"""Field of a ``CheckInput`` holding the ``CheckRequest``."""

AUDIO_ID_FIELD: Final = "audio_id"
"""Field of a ``CheckRequest`` naming its uploaded audio."""
