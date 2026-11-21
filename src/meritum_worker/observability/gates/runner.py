"""Call a live gate on every case and record what it returned.

Features:
    US-BEZ-01, US-BEZ-04, US-OBS-04, F-27, ADR-35
"""

import time
from collections.abc import Sequence

from meritum_core.security.injection import (
    DetectionLayer,
    InjectionGatePort,
    InjectionScan,
    InjectionSpan,
    instruction_removed,
)
from meritum_core.security.pii import PiiGatePort, mask_personal_data

from meritum_worker.observability.gates.models import DlpCase, GateCall
from meritum_worker.observability.gates.scoring import screened_text
from meritum_worker.observability.models import GoldenSet


async def screen_cases(golden: GoldenSet, gate: InjectionGatePort) -> list[GateCall]:
    """Screen every case with text and cut what the gate flags (ADR-23).

    Args:
        golden: The golden set.
        gate: The classifier gate under test.

    Returns:
        One call per case with text; the output is the text left after cutting.

    Features:
        US-OBS-04, US-BEZ-01, F-19, F-27, ADR-23, ADR-35
    """
    calls: list[GateCall] = []
    for case in golden.root:
        text = screened_text(case)
        if text is None:
            continue
        started = time.perf_counter()
        ranges = await gate.screen(text)
        seconds = time.perf_counter() - started
        spans = tuple(
            InjectionSpan(start=r.start, end=r.end, layer=DetectionLayer.GATE)
            for r in sorted(ranges)
        )
        left = instruction_removed(InjectionScan(text=text, spans=spans)).text
        calls.append(GateCall(case_id=case.id, output=left, seconds=seconds))
    return calls


async def mask_cases(cases: Sequence[DlpCase], gate: PiiGatePort) -> list[GateCall]:
    """Mask every DLP case the way the API does: the gate, then the patterns.

    Args:
        cases: The DLP cases.
        gate: The masking gate under test.

    Returns:
        One call per case; the output is the masked text.

    Features:
        US-OBS-04, US-BEZ-01, US-BEZ-04, F-20, F-27, ADR-35
    """
    calls: list[GateCall] = []
    for case in cases:
        started = time.perf_counter()
        masked = await mask_personal_data(case.text, gate)
        seconds = time.perf_counter() - started
        calls.append(GateCall(case_id=case.id, output=masked.text, seconds=seconds))
    return calls
