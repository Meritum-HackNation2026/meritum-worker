"""Answer rubric: a judge model reads the answer text against the scenario's checks.

The checks come from the owner's model answers for scenarios A-J
(``evals/rubric.json``); the judge also gets the case's model answer and sees
what a reader sees: explanations, citations with their source's title and
date, fact-checkers' ratings, the message and the limitations (worker#252).

Features:
    US-OBS-04, US-OBS-05, F-27
"""

import asyncio
from collections.abc import Sequence
from pathlib import Path
from statistics import mean
from typing import Self, get_args

from meritum_core.checks import CheckResult
from meritum_core.shared.llm import LlmPort, Prompt, ProviderUnavailableError
from pydantic import BaseModel, ConfigDict, model_validator

from meritum_worker.observability.constants import (
    ANSWER_HIDDEN_FIELDS,
    REPORT_DECIMALS,
    RUBRIC_BLOCKS,
    RUBRIC_JUDGE_INSTRUCTIONS,
)
from meritum_worker.observability.models import GoldenCase, Scenario
from meritum_worker.observability.report import (
    CaseRubric,
    CaseRun,
    CheckStatus,
    RubricCheck,
)


class Rubric(BaseModel):
    """The checks every answer meets and the checks of each scenario.

    Attributes:
        common: Checks of every scenario, judged first.
        scenarios: Each scenario's own checks.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    common: tuple[str, ...]
    scenarios: dict[Scenario, tuple[str, ...]]

    @model_validator(mode="after")
    def _complete(self) -> Self:
        missing = sorted(set(get_args(Scenario.__value__)) - set(self.scenarios))
        if missing:
            msg = f"no rubric for scenarios {', '.join(missing)}"
            raise ValueError(msg)
        return self

    def checks(self, scenario: Scenario) -> tuple[str, ...]:
        """The checks of a scenario's answer, common ones first.

        Args:
            scenario: The case's scenario.

        Returns:
            The checks in the order the judge numbers them.

        Features:
            US-OBS-04, F-27
        """
        return self.common + self.scenarios[scenario]


class _Status(BaseModel):
    number: int
    status: CheckStatus
    reason: str = ""


class RubricAnswer(BaseModel):
    """One vote of the rubric judge.

    Attributes:
        checks: Each check's number, status and reason.

    Features:
        US-OBS-04, F-27
    """

    checks: list[_Status]


def load_rubric(path: Path) -> Rubric:
    """Read and validate the rubric file.

    Args:
        path: Usually ``evals/rubric.json``.

    Returns:
        The rubric.

    Features:
        US-OBS-04, F-27
    """
    return Rubric.model_validate_json(path.read_text(encoding="utf-8"))


async def judge_rubric(
    runs: Sequence[CaseRun], llm: LlmPort, rubric: Rubric, *, votes: int
) -> dict[str, CaseRubric]:
    """Ask the judge ``votes`` times about each case's answer text.

    A vote whose call fails is left out; a case with no vote left is not judged.

    Args:
        runs: One run per case; a repeat is judged next to the first answer.
        llm: The judge model; a run against dev uses ``MERITUM_LLM_*``.
        rubric: The checks per scenario.
        votes: Judge calls per case.

    Returns:
        The rubric of each judged case, by case id.

    Features:
        US-OBS-04, US-OBS-05, F-27
    """
    by_id = {run.case.id: run for run in runs}

    async def one(run: CaseRun) -> tuple[str, CaseRubric | None]:
        checks = rubric.checks(run.case.scenario)
        first = by_id.get(run.case.related_case or "")
        prompt = _prompt(run, checks, first.result if first else None)
        answers = await asyncio.gather(*(_vote(llm, prompt) for _ in range(votes)))
        counted = [_checks(a, checks) for a in answers if a is not None]
        return run.case.id, _rubric(counted) if counted else None

    judged = await asyncio.gather(*map(one, runs))
    return {case_id: rubric for case_id, rubric in judged if rubric is not None}


def _prompt(run: CaseRun, checks: Sequence[str], first: CheckResult | None) -> Prompt:
    numbered = "".join(f"\n{n}. {check}" for n, check in enumerate(checks, 1))
    texts = [_question(run.case), run.case.expected_behavior, _shown(run.result)]
    if first is not None:
        texts.append(_shown(first))
    # Labelled blocks: the judge mixed up the reference and the bot's answer.
    data = tuple(
        f"<{tag}>\n{text}\n</{tag}>"
        for tag, text in zip(RUBRIC_BLOCKS, texts, strict=False)
    )
    return Prompt(instructions=RUBRIC_JUDGE_INSTRUCTIONS + numbered, data=data)


def _question(case: GoldenCase) -> str:
    url = None if case.url is None else str(case.url)
    parts: tuple[str | None, ...] = (case.text, url, case.image_text)
    return "\n".join(part for part in parts if part is not None)


def _shown(result: CheckResult) -> str:
    return result.model_dump_json(exclude=ANSWER_HIDDEN_FIELDS, exclude_none=True)


async def _vote(llm: LlmPort, prompt: Prompt) -> RubricAnswer | None:
    try:
        return (await llm.complete(prompt, RubricAnswer)).output
    except ProviderUnavailableError:
        return None


def _checks(answer: RubricAnswer, checks: Sequence[str]) -> tuple[RubricCheck, ...]:
    # A check the judge skipped counts as not met.
    said = {status.number: status for status in reversed(answer.checks)}
    skipped = _Status(number=0, status="not_met")
    return tuple(
        RubricCheck(check=check, status=s.status, reason=s.reason)
        for n, check in enumerate(checks, 1)
        for s in (said.get(n, skipped),)
    )


def _rubric(votes: Sequence[tuple[RubricCheck, ...]]) -> CaseRubric:
    scores = [s for s in map(_score, votes) if s is not None]
    failed = dict.fromkeys(
        f"{c.check} ({c.reason})" if c.reason else c.check
        for vote in votes
        for c in vote
        if c.status == "not_met"
    )
    return CaseRubric(
        score=round(mean(scores), REPORT_DECIMALS) if scores else None,
        passed=mean(all(c.status != "not_met" for c in vote) for vote in votes),
        failed=tuple(failed),
        votes=tuple(votes),
    )


def _score(vote: Sequence[RubricCheck]) -> float | None:
    applicable = [c.status == "met" for c in vote if c.status != "not_applicable"]
    return mean(applicable) if applicable else None
