"""PiiGatePort that records the masking gate's answers or replays them.

The cassette keeps only the masked text, keyed by a hash of the original, so
a replayed run masks exactly as the recording did without the gate's keys.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-13, ADR-28
"""

import asyncio
import hashlib

from meritum_core.security.pii import (
    MaskedText,
    PiiGatePort,
    PiiGateUnavailableError,
)

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, PiiTake


class CassettePii:
    """Records each answer of ``gate``, or replays them when it is None.

    Args:
        cassette: Where answers are recorded or read from.
        gate: The masking gate to record; None replays without keys or network.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-13, ADR-28
    """

    def __init__(self, cassette: Cassette, gate: PiiGatePort | None) -> None:
        self._tape = Tape(cassette.pii)
        self._gate = gate

    async def mask(self, text: str) -> MaskedText:
        """Mask through the gate (recording it) or answer from the cassette.

        Args:
            text: Free text that may contain personal data.

        Returns:
            The masked text and how many items were replaced.

        Raises:
            PiiGateUnavailableError: The gate failed, now or when recorded.
            CassetteMissError: Replay found no recorded answer for this text.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = hashlib.sha256(text.encode()).hexdigest()
        if self._gate is None:
            take = self._tape.next(key)
            if take.masked is None:
                raise PiiGateUnavailableError(key)
            return take.masked
        try:
            masked = await self._gate.mask(text)
        except asyncio.CancelledError:
            # The caller's deadline cut the call off; replay raises TimeoutError.
            self._tape.record_timeout(key)
            raise
        except PiiGateUnavailableError:
            self._tape.record(key, PiiTake())
            raise
        self._tape.record(key, PiiTake(masked=masked))
        return masked
