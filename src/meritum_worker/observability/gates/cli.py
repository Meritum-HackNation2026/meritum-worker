"""``meritum-eval gates``: compare the gates before the LLM, the report as JSON.

Features:
    US-BEZ-01, US-OBS-04, F-27, ADR-28, ADR-35
"""

import argparse
import asyncio
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from meritum_worker.observability.constants import DEFAULT_CASES_FILE, EVAL_NAME
from meritum_worker.observability.gates.compare import compare_gates, load_gate_config
from meritum_worker.observability.gates.constants import GATES_COMMAND, REPORT_ZONE
from meritum_worker.observability.gates.factory import build_gate_builders
from meritum_worker.observability.golden import load_golden_set


def gates_eval(argv: Sequence[str]) -> None:
    """Score every ``--config`` on the golden set; live gates call their providers.

    Args:
        argv: Arguments after ``gates``.

    Features:
        US-BEZ-01, US-OBS-04, F-27, ADR-28, ADR-35
    """
    parser = argparse.ArgumentParser(prog=f"{EVAL_NAME} {GATES_COMMAND}")
    parser.add_argument("--config", type=Path, action="append", required=True)
    parser.add_argument("--cases", type=Path, default=Path(DEFAULT_CASES_FILE))
    parser.add_argument("--output", type=Path, help="report file; stdout without it")
    args = parser.parse_args(argv)
    try:
        configs = [load_gate_config(path) for path in args.config]
        golden = load_golden_set(args.cases)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    day = datetime.now(REPORT_ZONE).date()
    try:
        run = compare_gates(configs, golden, build_gate_builders(), day)
        report = asyncio.run(run)
    except (OSError, ValueError) as error:
        # A missing recorded file or bad gate settings: a message, not a traceback.
        parser.error(str(error))
    text = report.model_dump_json(indent=2) + "\n"
    if args.output is None:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
