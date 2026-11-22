"""The one shield between the check and the model: every prompt's data is scanned.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-23
"""

import logging

from meritum_core.security.injection import InjectionDetectorPort, instruction_removed
from meritum_core.shared.llm import LlmPort, LlmResult, Prompt
from pydantic import BaseModel

_log = logging.getLogger(__name__)


class ScreenedLlm:
    """LlmPort that runs the detector on each data part and cuts what it finds.

    Instructions are Meritum's own text and pass as they are; every data part
    (user or source text) is scanned, and a found instruction is cut out
    before the model sees it. The steps already record InjectionEvents; this
    shield only logs the count of what got past them.

    Args:
        llm: The model the cleaned prompt goes to.
        detector: Core's layered detector; it calls its own isolated model.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-23
    """

    def __init__(self, llm: LlmPort, detector: InjectionDetectorPort) -> None:
        self._llm = llm
        self._detector = detector

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        """Scan and clean every data part, then ask the model.

        Args:
            prompt: Instructions and the data they work on.
            output: Pydantic model the answer must validate against.

        Returns:
            The model's answer to the cleaned prompt, with its usage.
        """
        cleaned = [
            instruction_removed(await self._detector.scan(d)) for d in prompt.data
        ]
        if cut := sum(len(c.events) for c in cleaned):
            # The count only: user and source text never reach the log.
            _log.warning("injection shield cut %d instructions from a prompt", cut)
        data = tuple(c.text for c in cleaned)
        return await self._llm.complete(
            prompt.model_copy(update={"data": data}), output
        )
