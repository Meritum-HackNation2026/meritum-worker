"""Compare embedding models by corpus retrieval on the golden set (US-OBS-04).

The golden set's own sources stand in for the corpus: each case with sources
queries by its main claim, and a hit is one of its sources ranked in the top k.
Config files name the model and its price, so no model is named in code.

Features:
    US-WDR-02, US-OBS-04, F-27
"""

import math
import tomllib
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Annotated

from meritum_core.shared.embeddings import (
    EmbeddingsPort,
    EmbeddingsSettings,
    Vector,
)
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.observability.constants import (
    CHARS_PER_MILLION,
    COST_DECIMALS,
    COST_SAMPLE_QUERIES,
    REPORT_DECIMALS,
    RETRIEVAL_TOP_K,
)
from meritum_worker.observability.models import GoldenSet


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
        queries: Cases with sources, each one query.
        documents: Distinct source URLs embedded as the corpus.
        top_k: Ranks that count as a hit.
        hit_rate: Queries with one of their sources in the top k.
        mean_reciprocal_rank: Mean of 1 / rank of the first own source.
        characters: Characters embedded, queries and documents.
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
    documents: int
    top_k: int
    hit_rate: float
    mean_reciprocal_rank: float
    characters: int
    cost_usd: float
    cost_100_queries_usd: float


class EmbeddingsComparison(BaseModel):
    """Every embedding candidate's score on the same case file.

    Attributes:
        generated_at: When the comparison ran.
        cases_file: The case file every candidate ran on.
        models: One entry per config file, in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """

    model_config = ConfigDict(frozen=True)

    generated_at: datetime
    cases_file: str
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
    config: EmbeddingsConfig,
    embeddings: EmbeddingsPort,
    top_k: int = RETRIEVAL_TOP_K,
) -> RetrievalScore:
    """Rank the golden set's sources for each case's main claim.

    Args:
        cases: The case file; cases without sources are skipped.
        config: The candidate, for its label and price.
        embeddings: The candidate's model.
        top_k: Ranks that count as a hit.

    Returns:
        The candidate's score.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    documents: dict[str, str] = {}
    for case in cases.root:
        for source in case.sources:
            documents.setdefault(str(source.url), f"{source.title}\n{source.quote}")
    index = {url: i for i, url in enumerate(documents)}
    vectors = await embeddings.embed_documents(list(documents.values()))
    queried = [case for case in cases.root if case.sources]
    ranks: list[int] = []
    for case in queried:
        order = _ranking(await embeddings.embed_query(case.main_claim), vectors)
        own = {index[str(source.url)] for source in case.sources}
        ranks.append(next(r for r, i in enumerate(order, 1) if i in own))
    query_chars = sum(len(case.main_claim) for case in queried)
    characters = query_chars + sum(len(text) for text in documents.values())
    mean_query = query_chars / max(len(queried), 1)
    settings = config.embeddings
    return RetrievalScore(
        name=config.name,
        provider=settings.provider,
        model=settings.model,
        region=settings.region,
        dimensions=settings.dimensions,
        queries=len(queried),
        documents=len(index),
        top_k=top_k,
        hit_rate=_mean([rank <= top_k for rank in ranks]),
        mean_reciprocal_rank=_mean([1 / rank for rank in ranks]),
        characters=characters,
        cost_usd=_price(characters, config),
        cost_100_queries_usd=_price(mean_query * COST_SAMPLE_QUERIES, config),
    )


def compare_embeddings(
    scores: Sequence[RetrievalScore], cases_file: str, generated_at: datetime
) -> EmbeddingsComparison:
    """Put each candidate's score into one comparison.

    Args:
        scores: One score per config file.
        cases_file: The case file the scores come from.
        generated_at: When the comparison ran.

    Returns:
        The comparison, candidates in the order given.

    Features:
        US-WDR-02, US-OBS-04, F-27
    """
    return EmbeddingsComparison(
        generated_at=generated_at, cases_file=cases_file, models=tuple(scores)
    )


def _ranking(query: Vector, documents: Sequence[Vector]) -> list[int]:
    # Document indices from the most similar; ties keep file order.
    similarity = [_cosine(query, document) for document in documents]
    return sorted(range(len(documents)), key=lambda i: -similarity[i])


def _cosine(a: Vector, b: Vector) -> float:
    norms = math.hypot(*a) * math.hypot(*b)
    return sum(x * y for x, y in zip(a, b, strict=True)) / norms if norms else 0.0


def _mean(values: Sequence[float]) -> float:
    return round(sum(values) / len(values), REPORT_DECIMALS) if values else 0.0


def _price(characters: float, config: EmbeddingsConfig) -> float:
    cost = characters * config.usd_per_million_chars / CHARS_PER_MILLION
    return round(cost, COST_DECIMALS)
