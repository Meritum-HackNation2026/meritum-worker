"""Research agent of the corpus: hybrid search, then the reranker gate, per fact.

Calls ``CorpusSearchPort`` in process, never through MCP (ADR-32); passages
pass the reranker before stance assessment (ADR-35).

Features:
    US-SPR-02, US-SPR-04, US-KOR-02, F-09, F-12, ADR-20, ADR-32, ADR-35
"""

import asyncio

from meritum_worker.checks.constants import (
    MAX_PARALLEL_CLAIMS,
    NO_CORPUS_VERSION,
    SEARCH_CORPUS_STEP,
)
from meritum_worker.checks.models import CheckDeps, CheckState, ExtractedClaim
from meritum_worker.corpus import Reranking, rerank_passages


async def search_corpus(state: CheckState, deps: CheckDeps) -> CheckState:
    """Search the pinned snapshot for every fact, at most 3 facts at once.

    Args:
        state: the check so far, with its dated claims.
        deps: the corpus search, the reranker and the pinned snapshot.

    Returns:
        The state with reranked passages per fact and the snapshot searched;
        skipped when there is no fact or no snapshot is pinned. A reranker
        failure keeps the search order and adds a retrieval error.

    Features:
        US-SPR-02, US-SPR-04, F-09, F-12, ADR-20, ADR-32, ADR-35
    """
    facts = [claim for claim in state.claims if claim.is_fact]
    if not facts or deps.corpus_version == NO_CORPUS_VERSION:
        skipped = [*state.skipped_steps, SEARCH_CORPUS_STEP]
        return state.model_copy(update={"skipped_steps": skipped})
    gate = asyncio.Semaphore(MAX_PARALLEL_CLAIMS)
    found = await asyncio.gather(*(_research(f, state, deps, gate) for f in facts))
    # One failing reranker fails every fact the same way: record it once.
    errors = dict.fromkeys(e for reranking in found for e in reranking.retrieval_errors)
    passages = {f.claim: r.passages for f, r in zip(facts, found, strict=True)}
    return state.model_copy(
        update={
            "corpus_version": deps.corpus_version,
            "passages": passages,
            "retrieval_errors": [*state.retrieval_errors, *errors],
        }
    )


async def _research(
    fact: ExtractedClaim, state: CheckState, deps: CheckDeps, gate: asyncio.Semaphore
) -> Reranking:
    async with gate:
        found = await deps.corpus.search(
            fact.claim,
            claim_date=fact.claim_date or state.job.received_at.date(),
            corpus_version=deps.corpus_version,
        )
        return await rerank_passages(deps.reranker, fact.claim, found)
