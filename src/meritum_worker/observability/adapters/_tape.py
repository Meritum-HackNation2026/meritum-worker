"""One provider's recorded takes by request key, replayed in call order.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-28
"""

from meritum_worker.observability.errors import CassetteMissError


class Tape[T]:
    """Appends takes while recording; hands them back one by one on replay.

    Calls with the same key get their takes in call order, so a repeated
    request replays as it was answered. A call its caller's deadline cut off
    leaves a None take, replayed as the same ``TimeoutError``.

    Args:
        takes: The cassette's takes of one provider, shared, not copied.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    def __init__(self, takes: dict[str, list[T | None]]) -> None:
        self._takes = takes
        self._served: dict[str, int] = {}

    def record(self, key: str, take: T) -> None:
        """Append a take under ``key``.

        Args:
            key: The request key.
            take: What the provider answered.
        """
        self._takes.setdefault(key, []).append(take)

    def record_timeout(self, key: str) -> None:
        """Note that the caller's deadline cancelled the call under ``key``.

        Args:
            key: The request key.
        """
        self._takes.setdefault(key, []).append(None)

    def next(self, key: str) -> T:
        """The next take of ``key`` not yet replayed.

        Args:
            key: The request key.

        Returns:
            The take.

        Raises:
            CassetteMissError: Every take of ``key`` was replayed, or none exists.
            TimeoutError: The recorded call was cut off by its caller's deadline.
        """
        takes = self._takes.get(key, [])
        index = self._served.get(key, 0)
        if index >= len(takes):
            raise CassetteMissError(key)
        self._served[key] = index + 1
        take = takes[index]
        if take is None:
            raise TimeoutError(key)
        return take
