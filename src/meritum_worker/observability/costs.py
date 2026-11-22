"""Cost of 1,000 checks and the cache hit ratio, from saved CheckRecords.

Features:
    US-OBS-02, F-22, F-23
"""

import argparse
import sys
from collections.abc import Iterable, Sequence
from pathlib import Path

from meritum_core.checks.contracts import CheckRecord
from pydantic import BaseModel

from meritum_worker.observability.constants import COST_PER_CHECKS


class CostLine(BaseModel, frozen=True):
    """Cost and cache hits of one group of checks.

    Attributes:
        channel: the channel, or ``all``.
        checks: how many checks the group has.
        usd_per_1000_checks: mean cost of a check times 1,000.
        cache_hit_ratio: share of checks served from the result cache.

    Features:
        US-OBS-02, F-23
    """

    channel: str
    checks: int
    usd_per_1000_checks: float
    cache_hit_ratio: float


class CostSummary(CostLine, frozen=True):
    """Cost of all checks and of each channel.

    Attributes:
        channels: one line per channel, by name.

    Features:
        US-OBS-02, F-23
    """

    channels: list[CostLine]


def _line(channel: str, records: list[CheckRecord]) -> CostLine:
    count = len(records)
    total = sum(m.cost_usd for r in records for m in r.models)
    hits = sum(r.cache_hit for r in records)
    return CostLine(
        channel=channel,
        checks=count,
        usd_per_1000_checks=total / count * COST_PER_CHECKS if count else 0.0,
        cache_hit_ratio=hits / count if count else 0.0,
    )


def summarize_costs(records: Iterable[CheckRecord]) -> CostSummary:
    """Sum model and search costs of the records, overall and per channel.

    Args:
        records: saved CheckRecords.

    Returns:
        The summary; zeros for no records.

    Features:
        US-OBS-02, F-22, F-23
    """
    kept = list(records)
    names = sorted({r.channel for r in kept})
    channels = [_line(n, [r for r in kept if r.channel == n]) for n in names]
    return CostSummary(**_line("all", kept).model_dump(), channels=channels)


def meritum_cost(argv: Sequence[str] | None = None) -> None:
    """Print the cost summary of CheckRecords exported as JSON lines.

    Args:
        argv: the command line; ``sys.argv[1:]`` when None.

    Features:
        US-OBS-02, F-23
    """
    parser = argparse.ArgumentParser(prog="meritum-cost")
    parser.add_argument("records", type=Path, help="CheckRecords, one JSON per line")
    path = parser.parse_args(argv).records
    lines = path.read_text(encoding="utf-8").splitlines()
    records = (CheckRecord.model_validate_json(line) for line in lines if line.strip())
    sys.stdout.write(summarize_costs(records).model_dump_json(indent=2) + "\n")
