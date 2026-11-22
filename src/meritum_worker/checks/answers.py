"""What the model answers in write_answer.

Features:
    US-SPR-01, F-22
"""

import re
from collections.abc import Sequence

from meritum_core.shared.llm import Prompt
from pydantic import BaseModel

from meritum_worker.checks.constants import (
    CODE_PATTERN,
    SENTENCE_END,
    STANCE_LABELS,
    VERDICT_LABELS,
)
from meritum_worker.checks.models import ExtractedClaim
from meritum_worker.checks.prompts import ANSWER_INSTRUCTIONS, ANSWER_VERDICTS
from meritum_worker.evidence import ClaimExplanation, Judgement


class AnswerDraft(BaseModel):
    """What the model answers in write_answer, before the CheckResult rules apply.

    Attributes:
        claims: one explanation per fact, in order; the verdict comes from code.
        limitations: what the check could not cover.

    Features:
        US-SPR-01, F-22
    """

    claims: list[ClaimExplanation]
    limitations: list[str]


def answer_prompt(
    question: str, facts: Sequence[ExtractedClaim], judged: Sequence[Judgement]
) -> Prompt:
    """Build the write_answer prompt: claims and quotes as data, verdicts as ours.

    The verdicts are Meritum's text, so they end the instructions. In the data,
    which the injection shield scans, a "verdict: ..." line was cut as a command
    and the model explained nothing (worker#221).

    Args:
        question: the user's text.
        facts: the checked facts.
        judged: each fact's judgement from the core rules, in the same order.

    Returns:
        The prompt; the user text and one item per fact are data.

    Features:
        US-SPR-01, US-BEZ-01, F-22
    """
    verdicts = "; ".join(
        f"{i}. {VERDICT_LABELS[j.verdict]}" for i, j in enumerate(judged, start=1)
    )
    ending = ANSWER_VERDICTS.format(verdicts=verdicts) if facts else ""
    data = (question, *map(_described, facts, judged, strict=True))
    return Prompt(instructions=ANSWER_INSTRUCTIONS + ending, data=data)


def _described(fact: ExtractedClaim, judged: Judgement) -> str:
    # Source fragments go to the model as data, so it can explain them.
    quotes = [
        f"- {STANCE_LABELS[c.stance]}, {c.source.publisher}: {c.fragment}"
        for c in judged.citations
    ]
    ratings = (
        f"- {STANCE_LABELS[r.stance]}, {r.publisher}: ocena {r.rating}, {r.title}"
        for r in judged.claim_review_premises
    )
    return "\n".join((fact.claim, *quotes, *ratings))


def plain_text(text: str, limit: int) -> str:
    """Make a model text fit for the citizen: Polish names, contract length.

    The prompt forbids codes and gives the limits; this is the check after it,
    so a code that slips through never reaches the citizen and a text over the
    contract limit is cut instead of failing the whole check.

    Args:
        text: an explanation, unresolved or limitation written by the model.
        limit: the longest text the contract accepts for this field.

    Returns:
        The text with each code replaced by its Polish name (verdicts quoted),
        cut after its last whole sentence within the limit, or after its last
        whole word with an ellipsis when no sentence fits.

    Features:
        US-SPR-01, F-22
    """

    def name(match: re.Match[str]) -> str:
        code = match[1]
        return (
            f"„{VERDICT_LABELS[code]}”"
            if code in VERDICT_LABELS
            else STANCE_LABELS[code]
        )

    return _fit(CODE_PATTERN.sub(name, text), limit)


def _fit(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = text[:limit]
    ends = list(SENTENCE_END.finditer(head))
    if ends:
        return head[: ends[-1].end()]
    return head[: limit - 1].rsplit(" ", 1)[0] + "…"
