"""Keep only fragments found verbatim in their source, then set their validity.

Features:
    US-ZRD-01, US-ZRD-10, F-15, F-16, ADR-06
"""

from meritum_core.evidence import verify_citation

from meritum_worker import evidence
from meritum_worker.checks.models import CheckDeps, CheckState


async def verify_citations(state: CheckState, deps: CheckDeps) -> CheckState:
    """Check every proposed fragment word for word; drop the rest.

    Title, publisher, date and link come from the database by source id, never
    from the model. Validity (``superseded`` included) is set per fact at its
    claim date by the core rule.

    Args:
        state: the check so far; a state that already has a result passes on.
        deps: the ports; only the catalogue is read.

    Returns:
        The state with the verified citations.

    Features:
        US-ZRD-01, US-ZRD-10, F-15, F-16, ADR-06
    """
    if state.result is not None:
        return state
    sources = {document.source.id: document for document in state.evidence}
    catalog = {entry.domain: entry for entry in deps.catalog}
    facts = [claim for claim in state.claims if claim.is_fact]
    verified: list[evidence.VerifiedCitation] = []
    for index, fact in enumerate(facts):
        drafts = [a.draft for a in state.assessed if a.fact == index]
        found = [c for d in drafts if (c := verify_citation(d, sources)) is not None]
        if not found or fact.claim_date is None:
            continue
        dated = evidence.with_validity(found, catalog, claim_date=fact.claim_date)
        verified += [evidence.VerifiedCitation(fact=index, citation=c) for c in dated]
    return state.model_copy(update={"citations": [*state.citations, *verified]})
