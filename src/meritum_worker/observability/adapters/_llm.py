"""LlmPort that records a provider's answers or replays them from a cassette.

Features:
    US-OBS-07, US-OBS-04, F-27, ADR-28
"""

import asyncio
import hashlib
import json

from meritum_core.shared.llm import (
    LlmPort,
    LlmResult,
    Prompt,
    ProviderUnavailableError,
)
from pydantic import BaseModel

from meritum_worker.observability.adapters._tape import Tape
from meritum_worker.observability.cassette import Cassette, LlmTake


class CassetteLlm:
    """Records each call of ``provider``, or replays them when it is None.

    Args:
        cassette: Where answers are recorded or read from.
        provider: The model to record; None replays without keys or network.

    Features:
        US-OBS-07, US-OBS-04, F-27, ADR-28
    """

    def __init__(self, cassette: Cassette, provider: LlmPort | None) -> None:
        self._tape = Tape(cassette.llm)
        self._provider = provider

    @staticmethod
    def key(prompt: Prompt, output: type[BaseModel]) -> str:
        """The request key of a call: SHA-256 of the prompt and the output type.

        Args:
            prompt: The call's prompt.
            output: The model the answer validates against.

        Returns:
            The hex key.
        """
        request = {"prompt": prompt.model_dump(mode="json"), "output": output.__name__}
        canonical = json.dumps(request, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        """Answer from the provider (recording it) or from the cassette.

        Args:
            prompt: Instructions and data, kept apart.
            output: Pydantic model the answer must validate against.

        Returns:
            The answer and its usage.

        Raises:
            ProviderUnavailableError: The provider failed, now or when recorded.
            CassetteMissError: Replay found no recorded answer for this call.
            CancelledError: The caller's deadline cut the call off while recording.
            TimeoutError: The recorded call was cut off by the same deadline.
        """  # ruff: ignore[docstring-extraneous-exception]  # raised by Tape.next
        key = self.key(prompt, output)
        if self._provider is None:
            return self._replay(key, output)
        try:
            result = await self._provider.complete(prompt, output)
        except asyncio.CancelledError:
            # The caller's deadline cut the call off; replay raises TimeoutError.
            self._tape.record_timeout(key)
            raise
        except ProviderUnavailableError as error:
            self._tape.record(key, LlmTake(error=str(error)))
            raise
        take = LlmTake(output=result.output.model_dump(mode="json"), usage=result.usage)
        self._tape.record(key, take)
        return result

    def _replay[T: BaseModel](self, key: str, output: type[T]) -> LlmResult[T]:
        take = self._tape.next(key)
        if take.usage is None:
            raise ProviderUnavailableError(take.error)
        return LlmResult[T](output=output.model_validate(take.output), usage=take.usage)
