"""Shared pieces of the LlmPort fakes in the worker tests."""

from meritum_core.shared.llm import (
    LlmResult,
    LlmToolResult,
    LlmUsage,
    Prompt,
    ProviderUnavailableError,
    Tool,
)
from pydantic import BaseModel


class NoTools:
    """Mixin for fakes of LlmPort: the worker never asks for tool calls."""

    @staticmethod
    async def complete_with_tools[T: BaseModel](
        prompt: Prompt, output: type[T], tools: tuple[Tool, ...]
    ) -> LlmToolResult[T]:
        """Fails: no worker step calls tools yet.

        Raises:
            NotImplementedError: always.
        """
        raise NotImplementedError(prompt, output, tools)


USAGE = LlmUsage(
    provider="stub", model="stub", region="local", input_tokens=0, output_tokens=0
)


class RecordingLlm(NoTools):
    """Answers each output model from ``answers`` and keeps every prompt."""

    def __init__(self, *answers: BaseModel) -> None:
        self.answers = {type(answer).__name__: answer for answer in answers}
        self.prompts: list[Prompt] = []

    async def complete[T: BaseModel](
        self, prompt: Prompt, output: type[T]
    ) -> LlmResult[T]:
        self.prompts.append(prompt)
        if output.__name__ not in self.answers:
            raise ProviderUnavailableError(output.__name__)
        answer = output.model_validate(self.answers[output.__name__].model_dump())
        return LlmResult[T](output=answer, usage=USAGE)
