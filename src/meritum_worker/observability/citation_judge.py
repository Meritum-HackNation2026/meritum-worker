"""Citation precision: a judge model reads each fragment against its claim.

The judge sees what a reader sees under the citation: the fragment and its
source's title, date and address (worker#247).

The pipeline already keeps only fragments found verbatim in the fetched page
(``verify_citation``), so the judge checks the stance alone.

Features:
    US-OBS-04, US-OBS-05, US-ZRD-01, F-15, F-27
"""

import asyncio
from collections.abc import Sequence

from meritum_core.checks.contracts import Citation
from meritum_core.shared.llm import LlmPort, Prompt
from pydantic import BaseModel, ConfigDict

from meritum_worker.observability.constants import (
    CITATION_JUDGE_INSTRUCTIONS,
    JUDGE_UNKNOWN_DATE,
    STANCE_WORDS,
)
from meritum_worker.observability.quality import share
from meritum_worker.observability.report import CaseRun, Ratio


class CitationJudgement(BaseModel):
    """The judge's answer about one cited fragment.

    Attributes:
        correct: Whether the fragment bears on the claim as its stance says.

    Features:
        US-OBS-04, US-ZRD-01, F-27
    """

    model_config = ConfigDict(frozen=True)

    correct: bool


async def judge_citations(runs: Sequence[CaseRun], llm: LlmPort) -> Ratio:
    """Ask the judge about every citation of every claim, one call each.

    Args:
        runs: One run per case.
        llm: The judge model; a run against dev uses ``MERITUM_LLM_*``.

    Returns:
        The share of fragments the judge confirms; None without citations.

    Features:
        US-OBS-04, US-OBS-05, US-ZRD-01, F-15, F-27
    """
    hits = await citation_hits(runs, llm)
    return share([hit for case in hits.values() for hit in case])


async def citation_hits(
    runs: Sequence[CaseRun], llm: LlmPort
) -> dict[str, tuple[bool, ...]]:
    """The judge's answer about each citation, grouped by case.

    Args:
        runs: One run per case.
        llm: The judge model.

    Returns:
        Whether the judge confirms each citation, by case id, in claim order.

    Features:
        US-OBS-04, US-OBS-05, US-ZRD-01, F-15, F-27
    """

    async def one(run: CaseRun) -> tuple[str, tuple[bool, ...]]:
        prompts = [
            Prompt(
                instructions=CITATION_JUDGE_INSTRUCTIONS,
                data=(claim.claim, STANCE_WORDS[c.stance], c.fragment, *_source(c)),
            )
            for claim in run.result.claims
            for c in claim.citations
        ]
        answers = await asyncio.gather(
            *(llm.complete(p, CitationJudgement) for p in prompts)
        )
        return run.case.id, tuple(answer.output.correct for answer in answers)

    return dict(await asyncio.gather(*map(one, runs)))


def _source(citation: Citation) -> tuple[str, str, str]:
    source = citation.source
    published = source.published_at
    day = published.date().isoformat() if published else JUDGE_UNKNOWN_DATE
    return source.title, day, str(source.url)
