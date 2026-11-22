"""Compare embedding models by corpus retrieval on the golden set (US-OBS-04).

Each candidate re-embeds the passages of one corpus snapshot and searches it
the way checks do (hybrid search, fused, top 20). Each case with sources
queries by its main claim, and a hit is a passage of one of its sources in the
top k. Config files name the model and its price, so no model is named in code.

Features:
    US-WDR-02, US-OBS-04, F-12, F-27
"""

import math
import tomllib
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated

from meritum_core.corpus import CorpusProvider, CorpusSettings, build_corpus_search
from meritum_core.shared.embeddings import EmbeddingsPort, EmbeddingsSettings
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.observability.constants import (
    CHARS_PER_PRICE_UNIT,
    COST_DECIMALS,
    COST_SAMPLE_QUERIES,
    REPORT_DECIMALS,
    RETRIEVAL_TOP_K,
)
from meritum_worker.observability.models import GoldenSet
from meritum_worker.observability.snapshot import MeteredEmbeddings, SnapshotCorpus


class EmbeddingsConfig(BaseModel):
    """One candidate embedding model, read from a config file.

    Attributes:
        name: Label of the candidate in the report.
        usd_per_million_chars: List price of embedding a million characters.
        embeddings: The model's settings; unset fields come from
            ``MERITUM_EMBEDDINGS_*``, unknown fields fail.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    usd_per_million_chars: Annotated[float, Field(ge=0)]
    embeddings: EmbeddingsSettings


class RetrievalScore(BaseModel):
    """One candidate's retrieval quality and cost on the golden set.

    Attributes:
        name: Label of the candidate.
        provider: Embeddings provider.
        model: Model ID of the provider.
        region: Region of the provider.
        dimensions: Vector size.
        queries: Distinct main claims of the cases with sources.
        queries_with_targets: Queries with a source in the snapshot, scored.
        documents: Documents of the snapshot.
        passages: Passages of the snapshot, each embedded once.
        top_k: Ranks of the fused search that count as a hit.
        hit_rate: Scored queries with a passage of their sources in the top k.
        mean_reciprocal_rank: Mean of 1 / rank of that passage, 0 below top k.
        characters: Characters embedded, queries and passages.
        cost_usd: Cost of this run.
        cost_100_queries_usd: Cost of 100 queries at the mean query length.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True)

    name: str
    provider: str
    model: str
    region: str
    dimensions: int
    queries: int
    queries_with_targets: int
    documents: int
    passages: int
    top_k: int
    hit_rate: float
    mean_reciprocal_rank: float
    characters: int
    cost_usd: float
    cost_100_queries_usd: float


class EmbeddingsComparison(BaseModel):
    """Every embedding candidate's score on the same case file and snapshot.

    Attributes:
        generated_at: When the comparison ran.
        cases_file: The case file every candidate ran on.
        corpus: The ``corpus_version`` every candidate searched.
        models: One entry per config file, in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    cases_file: str
    corpus: str
    models: tuple[RetrievalScore, ...]


def load_embeddings_config(path: Path) -> EmbeddingsConfig:
    """Read one embedding candidate's config file.

    Args:
        path: TOML file with ``name``, ``usd_per_million_chars`` and an
            ``[embeddings]`` table.

    Returns:
        The validated config; a file that is not TOML or a missing, unknown
        or invalid field fails while parsing.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    with path.open("rb") as file:
        return EmbeddingsConfig.model_validate(tomllib.load(file))


async def score_retrieval(
    cases: GoldenSet,
    corpus: SnapshotCorpus,
    config: EmbeddingsConfig,
    embeddings: EmbeddingsPort,
    top_k: int = RETRIEVAL_TOP_K,
) -> RetrievalScore:
    """Search the snapshot for each case's main claim; its sources are targets.

    Args:
        cases: The case file; cases without sources are skipped, and cases
            with the same main claim are one query.
        corpus: The snapshot every candidate searches.
        config: The candidate, for its label and price.
        embeddings: The candidate's model; it embeds every passage once.
        top_k: Ranks of the fused search that count as a hit.

    Returns:
        The candidate's score.

    Features:
        US-WDR-02, US-OBS-04, F-12, F-27
    """
    metered = MeteredEmbeddings(embeddings)
    search = build_corpus_search(
        CorpusSettings(provider=CorpusProvider.MEMORY),
        metered,
        snapshots={corpus.version: corpus.passages},
    )
    urls = {source: _normalised(url) for source, url in corpus.urls.items()}
    queries = _queries(cases)
    known = set(urls.values())
    targeted = {claim: own for claim, own in queries.items() if own & known}
    ranks: list[float] = []
    for claim, own in targeted.items():
        found = await search.search(
            claim,
            claim_date=corpus.taken_at.date(),
            corpus_version=corpus.version,
            limit=top_k,
        )
        hits = (r for r, p in enumerate(found, 1) if urls.get(p.source_id) in own)
        ranks.append(next(hits, math.inf))
    query_chars = sum(map(len, queries))
    mean_query = query_chars / max(len(queries), 1)
    settings = config.embeddings
    return RetrievalScore(
        name=config.name,
        provider=settings.provider,
        model=settings.model,
        region=settings.region,
        dimensions=settings.dimensions,
        queries=len(queries),
        queries_with_targets=len(targeted),
        documents=len(urls),
        passages=len(corpus.passages),
        top_k=top_k,
        hit_rate=_mean([rank <= top_k for rank in ranks]),
        mean_reciprocal_rank=_mean([1 / rank for rank in ranks]),
        characters=metered.characters,
        cost_usd=_price(metered.characters, config),
        cost_100_queries_usd=_price(mean_query * COST_SAMPLE_QUERIES, config),
    )


def compare_embeddings(
    scores: Sequence[RetrievalScore],
    cases_file: str,
    corpus_version: str,
    generated_at: datetime,
) -> EmbeddingsComparison:
    """Put each candidate's score into one comparison.

    Args:
        scores: One score per config file.
        cases_file: The case file the scores come from.
        corpus_version: The snapshot every candidate searched.
        generated_at: When the comparison ran.

    Returns:
        The comparison, candidates in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    return EmbeddingsComparison(
        generated_at=generated_at,
        cases_file=cases_file,
        corpus=corpus_version,
        models=tuple(scores),
    )


def _queries(cases: GoldenSet) -> dict[str, set[str]]:
    # One query per distinct main claim, so a claim repeated by H or E cases
    # weighs as much as any other; its targets are every case's sources.
    queries: dict[str, set[str]] = {}
    for case in cases.root:
        if case.sources:
            urls = queries.setdefault(case.main_claim, set())
            urls.update(_normalised(str(source.url)) for source in case.sources)
    return queries


def _normalised(url: str) -> str:
    return url.removesuffix("/")


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), REPORT_DECIMALS) if values else 0.0


def _price(characters: float, config: EmbeddingsConfig) -> float:
    cost = characters * config.usd_per_million_chars / CHARS_PER_PRICE_UNIT
    return round(cost, COST_DECIMALS)
