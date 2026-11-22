"""Embeddings retrieval on the golden set's own sources, hand-made vectors (#40)."""

import asyncio
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest
from meritum_core.shared.embeddings import Vector

from meritum_worker.observability import (
    GoldenCase,
    GoldenSet,
    compare_embeddings,
    load_embeddings_config,
    score_retrieval,
)

type Make[T] = Callable[..., T]

AT = datetime(2026, 11, 22, tzinfo=UTC)
CONFIG = """
name = "{name}"
usd_per_million_chars = 2.0

[embeddings]
provider = "stub"
"""

VECTORS: dict[str, Vector] = {
    "Strefa A": (1.0, 0.0),
    "Strefa B": (1.0, 0.1),  # nearer a than b: b ranks second
    "Tytuł a\nCytat a.": (1.0, 0.0),
    "Tytuł b\nCytat b.": (0.0, 1.0),
}


def _source(slug: str) -> dict[str, str]:
    return {
        "url": f"https://www.gov.pl/{slug}",
        "publisher": "Gmina Pcim",
        "title": f"Tytuł {slug}",
        "quote": f"Cytat {slug}.",
    }


class _Fake:
    """Embeds each text as the vector it is mapped to."""

    def __init__(self, vectors: dict[str, Vector]) -> None:
        self._vectors = vectors

    async def embed_query(self, text: str) -> Vector:
        return self._vectors[text]

    async def embed_documents(self, texts: Sequence[str]) -> list[Vector]:
        return [self._vectors[text] for text in texts]


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "e.toml"
    path.write_text(CONFIG.format(name="e"), encoding="utf-8")
    return path


def _cases(case: Make[GoldenCase]) -> GoldenSet:
    return GoldenSet.model_validate(
        [
            case(id="D-own-a", main_claim="Strefa A", sources=[_source("a")]),
            case(id="D-own-b", main_claim="Strefa B", sources=[_source("b")]),
            # A repeat of the same claim is one query, not a second vote.
            case(id="D-own-a-again", main_claim="Strefa A", sources=[_source("a")]),
            case(id="D-own-none", main_claim="Bez źródeł"),
        ]
    )


def test_hit_rate_at_first_rank_and_reciprocal_rank_per_distinct_claim(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))

    score = asyncio.run(score_retrieval(_cases(case), config, _Fake(VECTORS)))

    assert (score.queries, score.documents, score.top_k) == (2, 2, 1)
    assert score.hit_rate == pytest.approx(0.5)
    assert score.mean_reciprocal_rank == pytest.approx(0.75)


def test_cost_counts_every_embedded_character(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))

    score = asyncio.run(score_retrieval(_cases(case), config, _Fake(VECTORS)))

    # 8 + 8 query chars, 16 + 16 document chars, at 2 USD per million chars.
    assert score.characters == 48
    assert score.cost_usd == pytest.approx(48 * 2 / 1_000_000)
    assert score.cost_100_queries_usd == pytest.approx(800 * 2 / 1_000_000)


def test_comparison_keeps_config_order_and_date(
    tmp_path: Path, case: Make[GoldenCase]
) -> None:
    config = load_embeddings_config(_config(tmp_path))
    score = asyncio.run(score_retrieval(_cases(case), config, _Fake(VECTORS)))

    comparison = compare_embeddings([score, score], "cases.json", AT)

    assert comparison.generated_at == AT
    assert "stand-in" in comparison.corpus
    assert [m.name for m in comparison.models] == ["e", "e"]
    assert comparison.models[0].provider == "stub"


@pytest.mark.parametrize(
    "path", sorted(Path(__file__).parents[2].glob("evals/embeddings/*.toml")), ids=str
)
def test_repo_embeddings_configs_are_valid(path: Path) -> None:
    assert load_embeddings_config(path).name == path.stem
