"""InjectionDetectorPort that records the detector's scans or replays them.

The cassette keeps only the spans, keyed by a hash of the scanned text, so a
replay flags the same instructions without the gate or the classifier model.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-23, ADR-28
"""

import asyncio
import hashlib

from meritum_core.security.injection import InjectionDetectorPort, InjectionScan
from meritum_core.shared.llm import ProviderUnavailableError

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, ScanTake


class CassetteInjection:
    """Records each scan of ``detector``, or replays them when it is None.

    Args:
        cassette: Where scans are recorded or read from.
        detector: The layered detector to record; None replays without keys.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-23, ADR-28
    """

    def __init__(
        self, cassette: Cassette, detector: InjectionDetectorPort | None
    ) -> None:
        self._tape = Tape(cassette.injection)
        self._detector = detector

    async def scan(self, text: str) -> InjectionScan:
        """Scan through the detector (recording it) or answer from the cassette.

        Args:
            text: User or source text, treated as data.

        Returns:
            The text with each detected instruction's range and layer.

        Raises:
            ProviderUnavailableError: The classifier failed, now or when recorded.
            CassetteMissError: Replay found no recorded scan of this text.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = hashlib.sha256(text.encode()).hexdigest()
        if self._detector is None:
            take = self._tape.next(key)
            if take.spans is None:
                raise ProviderUnavailableError(key)
            return InjectionScan(text=text, spans=take.spans)
        try:
            scan = await self._detector.scan(text)
        except asyncio.CancelledError:
            # The caller's deadline cut the call off; replay raises TimeoutError.
            self._tape.record_timeout(key)
            raise
        except ProviderUnavailableError:
            self._tape.record(key, ScanTake())
            raise
        self._tape.record(key, ScanTake(spans=scan.spans))
        return scan
