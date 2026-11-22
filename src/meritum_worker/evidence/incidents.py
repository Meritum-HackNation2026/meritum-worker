"""Match a claim to known incidents by content (title, topic, date) or by domain.

One function serves every incident database (organiser, EUvsDisinfo, fact-checks).
The match is context: nothing here reaches the verdict rule.

Features:
    US-ZRD-08, US-ZRD-09, F-11
"""

import math
from collections.abc import Sequence

from meritum_core.checks.contracts import IncidentMatch, MatchBasis, MatchedOn
from meritum_core.shared.embeddings import Vector

from meritum_worker.evidence.constants import (
    INCIDENT_DATE_WINDOW,
    INCIDENT_TITLE_THRESHOLD,
    INCIDENT_TOPIC_THRESHOLD,
)
from meritum_worker.evidence.models import IncidentCandidate, IncidentProbe


def _cosine(first: Vector, second: Vector) -> float:
    norms = math.hypot(*first) * math.hypot(*second)
    if norms == 0:
        return 0.0
    return sum(a * b for a, b in zip(first, second, strict=True)) / norms


def on_topic(
    vector: Vector, candidates: Sequence[IncidentCandidate]
) -> list[IncidentCandidate]:
    """Keep the incidents whose description is about the same topic as the claim.

    Args:
        vector: embedding of the claim.
        candidates: the incidents to compare.

    Returns:
        The incidents at or above INCIDENT_TOPIC_THRESHOLD, in input order.

    Features:
        US-ZRD-08, US-ZRD-09, F-11
    """
    return [
        c
        for c in candidates
        if _cosine(vector, c.description_vector) >= INCIDENT_TOPIC_THRESHOLD
    ]


def _basis(probe: IncidentProbe, candidate: IncidentCandidate) -> list[MatchBasis]:
    basis: list[MatchBasis] = ["topic"]
    title = candidate.title_vector
    if title is not None and _cosine(probe.vector, title) >= INCIDENT_TITLE_THRESHOLD:
        basis.append("title")
    if abs(candidate.date.date() - probe.on) <= INCIDENT_DATE_WINDOW:
        basis.append("date")
    if probe.domain is not None and probe.domain in candidate.domains:
        basis.append("domain")
    return basis


def _matched_on(basis: list[MatchBasis]) -> MatchedOn | None:
    if {"title", "date"} <= set(basis):
        return "content"
    return "domain" if "domain" in basis else None


def _match(probe: IncidentProbe, candidate: IncidentCandidate) -> IncidentMatch | None:
    basis = _basis(probe, candidate)
    matched_on = _matched_on(basis)
    if matched_on is None:
        return None
    similarity = _cosine(probe.vector, candidate.description_vector)
    return IncidentMatch.model_validate(
        {
            "database": candidate.database,
            "incident_id": candidate.incident_id,
            "matched_on": matched_on,
            "match_basis": basis,
            "title": candidate.title[:200],
            "date": candidate.date,
            "url": candidate.url,
            "similarity": min(1.0, similarity),
        }
    )


def match_incident(
    probe: IncidentProbe, candidates: Sequence[IncidentCandidate]
) -> IncidentMatch | None:
    """Find the known incident a claim matches, if any.

    The topic must agree for any match. A content match needs the title and the
    date to agree as well; without them, the checked link's domain listed by the
    incident makes a domain warning. The domain alone never matches.

    Args:
        probe: the claim's embedding, date and checked domain.
        candidates: incidents from every database, titles embedded.

    Returns:
        The closest content match, else the closest domain match, else None.

    Features:
        US-ZRD-08, US-ZRD-09, F-11
    """
    found = [m for c in on_topic(probe.vector, candidates) if (m := _match(probe, c))]
    if not found:
        return None
    return max(found, key=lambda m: (m.matched_on == "content", m.similarity))
