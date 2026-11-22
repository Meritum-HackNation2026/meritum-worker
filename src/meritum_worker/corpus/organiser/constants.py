"""Constants of the organiser's materials import.

Features:
    US-KOR-02, US-ZRD-08, F-10, F-11, ADR-32
"""

from typing import Final

IMPORT_WORKFLOW: Final = "organiser_import"
"""DBOS name of the workflow that imports the organiser's files."""

DATABASE: Final = "organiser"
"""``Entry.database`` of an incident from the organiser's file."""

INCIDENT_KEY_PREFIX: Final = "organiser:"
"""Prefix of an incident's key in the local copy, before its id in the file."""

TOPIC_SEPARATOR: Final = ";"
"""Separates topics in one CSV cell."""

MISSING_LICENSE: Final = "missing_license"
"""Skip reason of a record without a licence."""

INVALID_RECORD: Final = "invalid_record"
"""Skip reason of a record that fails validation for another reason."""

EMBED_BATCH: Final = 100
"""Texts embedded per call."""
