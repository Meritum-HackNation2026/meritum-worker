"""Builds the moderation ports over the app repositories.

Features:
    US-MOD-01, US-MOD-02, F-24, ADR-35
"""

import re
from collections.abc import Mapping

from meritum_core.observability import AppRepositories
from meritum_core.shared.embeddings import EmbeddingsPort

from meritum_worker.moderation.adapters import DbosCheckResults
from meritum_worker.moderation.constants import ADMIN_EMAILS_ENV
from meritum_worker.moderation.models import CheckResults, ModerationDeps


def build_moderation_deps(
    app: AppRepositories,
    embeddings: EmbeddingsPort,
    env: Mapping[str, str],
    results: CheckResults | None = None,
) -> ModerationDeps:
    """Wire cases, topics, staff and records with embeddings and DBOS results.

    Args:
        app: the app repositories; the same ones the check uses.
        embeddings: the embeddings port.
        env: the environment; ``MERITUM_ADMIN_EMAILS`` lists the administrators.
        results: finished checks; DBOS by default.

    Returns:
        The ports.

    Features:
        US-MOD-01, US-MOD-02, F-24, ADR-35
    """
    emails = re.split(r"[,\s]+", env.get(ADMIN_EMAILS_ENV, "").lower())
    return ModerationDeps(
        cases=app.cases,
        topics=app.topics,
        staff=app.staff,
        records=app.records,
        embeddings=embeddings,
        results=results or DbosCheckResults(),
        admin_emails=frozenset(e for e in emails if e),
    )
