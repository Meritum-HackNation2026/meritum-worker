"""Constants of the notifications slice: rechecks after a new corpus snapshot.

Features:
    US-POW-03, F-39, ADR-29
"""

from datetime import timedelta
from typing import Final

RECHECK_WORKFLOW: Final = "recheck_unanswered"
"""DBOS name of the workflow the snapshot workflow starts after each snapshot."""

RECHECK_CLAIM_WORKFLOW: Final = "recheck_claim"
"""DBOS name of one recheck: the `check` workflow body on the new snapshot."""

RECHECK_PLAN_STEP: Final = "plan rechecks"
"""DBOS step that picks the claims to check again."""

RECHECK_ANNOUNCE_STEP: Final = "announce recheck"
"""DBOS step that saves ``new_evidence`` when a recheck changed the verdict."""

RECHECK_WINDOW: Final = timedelta(days=30)
"""How far back an unanswered claim is looked for; the record's own
``retention_until`` decides, this only bounds the listing (record retention)."""

SNAPSHOT_INTERVAL: Final = timedelta(hours=1)
"""Time between two snapshots; the previous one tells which documents are new."""

RECHECK_SEARCH_LIMIT: Final = 5
"""Passages searched per claim; a new document among them makes it similar."""

RECHECK_LIMIT: Final = 20
"""Most rechecks started after one snapshot, so a large import cannot start
hundreds of model-backed checks at once."""

RECHECK_KEY: Final = "recheck:{old_check_id}:{claim}:{corpus_version}"
"""What makes one recheck unique; its uuid5 is the new check's id."""

NEW_EVIDENCE_KEY: Final = "new_evidence:{old_check_id}:{check_id}"
"""Notification key, the same as the new_evidence step's, so the two never add
a second entry for one recheck."""
