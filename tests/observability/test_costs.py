import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from meritum_core.checks.contracts import Channel, CheckRecord, ModelUsage

from meritum_worker.observability import meritum_cost, summarize_costs

_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)


def _record(
    n: int, channel: Channel, cost_usd: float, *, cache_hit: bool
) -> CheckRecord:
    usage = ModelUsage(
        provider="vertex_ai",
        model="gemini",
        region="europe-central2",
        input_tokens=10,
        output_tokens=1,
        cost_usd=cost_usd,
    )
    return CheckRecord(
        check_id=f"check-{n}",
        session_id="session-1",
        channel=channel,
        received_at=_AT,
        answered_at=_AT,
        question_masked="q",
        status="done",
        verdicts=[],
        source_ids=[],
        corpus_version="none",
        models=[usage] if cost_usd else [],
        web_search_calls=0,
        retrieval_errors=[],
        injection_events=[],
        cache_hit=cache_hit,
        retention_until=_AT + timedelta(days=30),
    )


_RECORDS = [
    _record(1, "web", 0.002, cache_hit=False),
    _record(2, "web", 0.0, cache_hit=True),
    _record(3, "extension", 0.004, cache_hit=False),
    _record(4, "extension", 0.002, cache_hit=False),
]


def test_summary_prices_1000_checks_and_counts_cache_hits() -> None:
    summary = summarize_costs(_RECORDS)
    assert summary.checks == 4
    assert summary.usd_per_1000_checks == pytest.approx(2.0)
    assert summary.cache_hit_ratio == pytest.approx(0.25)
    by_channel = {c.channel: c for c in summary.channels}
    assert by_channel["web"].usd_per_1000_checks == pytest.approx(1.0)
    assert by_channel["extension"].usd_per_1000_checks == pytest.approx(3.0)
    assert by_channel["web"].cache_hit_ratio == pytest.approx(0.5)


def test_summary_of_no_records_is_zero() -> None:
    summary = summarize_costs([])
    assert (summary.checks, summary.usd_per_1000_checks) == (0, 0.0)


def test_command_reads_records_as_json_lines(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "records.jsonl"
    path.write_text("\n".join(r.model_dump_json() for r in _RECORDS) + "\n")
    meritum_cost([str(path)])
    report = json.loads(capsys.readouterr().out)
    assert report["checks"] == 4
    assert report["usd_per_1000_checks"] == pytest.approx(2.0)
