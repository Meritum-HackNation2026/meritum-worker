"""Match each fact to known incidents from the organiser's database and EUvsDisinfo.

Both databases sit in one table (worker#29), so one function compares them.
The match and the domain warning are context and never reach the verdict. The
fact text of an EUvsDisinfo case on the claim's topic joins the evidence as an
ordinary secondary source, so it is assessed and verified like any other.

Features:
    US-ZRD-08, US-ZRD-09, F-11, ADR-06, ADR-26
"""

from urllib.parse import urlsplit

from meritum_core.checks.contracts import IncidentMatch
from meritum_core.evidence import SourceDocument
from meritum_core.security.pii import mask_personal_data
from meritum_core.shared.embeddings import EmbeddingsPort, EmbeddingsUnavailableError

from meritum_worker import evidence
from meritum_worker.checks.models import CheckDeps, CheckState, ExtractedClaim
from meritum_worker.corpus import StoredEntry


async def match_incidents(state: CheckState, deps: CheckDeps) -> CheckState:
    """Find the incident each fact matches and the EUvsDisinfo facts on its topic.

    Args:
        state: the check so far, with its dated claims.
        deps: the incident copy, the embeddings and the masking gate.

    Returns:
        The state with a match per fact that has one and the fact texts added
        to the evidence; unchanged without incident ports or facts. Unavailable
        embeddings add a retrieval error instead of failing the check.

    Features:
        US-ZRD-08, US-ZRD-09, F-11
    """
    facts = [claim for claim in state.claims if claim.is_fact]
    if deps.incidents is None or deps.embeddings is None or not facts:
        return state
    stored = {s.entry.key: s for s in await deps.incidents.entries() if _live(s)}
    candidates = [c for s in stored.values() if (c := _candidate(s))]
    matches: dict[str, IncidentMatch] = {}
    facts_on_topic: dict[str, SourceDocument] = {}
    try:
        for fact in facts:
            match, near = await _compare(state, deps, deps.embeddings, fact, candidates)
            if match is not None:
                matches[fact.claim] = match
            facts_on_topic |= {key: doc for key in near if (doc := _fact(stored[key]))}
    except EmbeddingsUnavailableError:
        errors = [*state.retrieval_errors, evidence.INCIDENTS_UNAVAILABLE]
        return state.model_copy(update={"retrieval_errors": errors})
    known = {doc.source.url for doc in state.evidence}
    added = [d for d in facts_on_topic.values() if d.source.url not in known]
    return state.model_copy(
        update={"incidents": matches, "evidence": [*state.evidence, *added]}
    )


async def _compare(
    state: CheckState,
    deps: CheckDeps,
    embeddings: EmbeddingsPort,
    fact: ExtractedClaim,
    candidates: list[evidence.IncidentCandidate],
) -> tuple[IncidentMatch | None, list[str]]:
    # The claim goes to an outside embeddings provider: mask it first.
    masked = (await mask_personal_data(fact.claim, deps.pii)).text
    vector = await embeddings.embed_query(masked)
    near = evidence.on_topic(vector, candidates)
    titles = await embeddings.embed_documents([c.title for c in near]) if near else []
    titled = [
        c.model_copy(update={"title_vector": t})
        for c, t in zip(near, titles, strict=True)
    ]
    on = state.published_at or fact.claim_date or state.job.received_at.date()
    probe = evidence.IncidentProbe(vector=vector, on=on, domain=_domain(state))
    return evidence.match_incident(probe, titled), [c.incident_id for c in near]


def _live(stored: StoredEntry) -> bool:
    return stored.deleted_at is None


def _candidate(stored: StoredEntry) -> evidence.IncidentCandidate | None:
    entry = stored.entry
    if entry.published_at is None:
        # An incident with no date cannot agree on the date or be shown with one.
        return None
    return evidence.IncidentCandidate(
        database=entry.database,
        incident_id=entry.key,
        title=entry.title,
        date=entry.published_at,
        url=entry.url,
        domains=entry.domains,
        description_vector=stored.description_vector,
    )


def _fact(stored: StoredEntry) -> SourceDocument | None:
    fact = stored.entry.fact
    if stored.source is None or fact is None:
        return None
    return SourceDocument(source=stored.source, text=fact)


def _domain(state: CheckState) -> str | None:
    url = state.job.request.url
    host = urlsplit(str(url)).hostname if url is not None else None
    return host.removeprefix("www.") if host is not None else None
