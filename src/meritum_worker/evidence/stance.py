"""The per-citation stance call: one claim, one source, nothing else (ADR-05, ADR-06).

Features:
    US-ZRD-01, US-ZRD-04, US-ZRD-10, F-15, F-16
"""

from datetime import date

from meritum_core.checks.contracts import Validity
from meritum_core.evidence import CitationDraft, SourceDocument
from meritum_core.shared.llm import LlmPort, LlmUsage, Prompt

from meritum_worker.evidence.constants import (
    NO_CLAIM_DATE,
    STANCE_INSTRUCTIONS,
    UNKNOWN_DATE,
)
from meritum_worker.evidence.models import StanceJudgement


def stance_prompt(
    claim: str, claim_date: date | None, document: SourceDocument, validity: Validity
) -> Prompt:
    """Build the stance prompt from the pair and the database's metadata only.

    The user's question and other sources never reach it, so no text outside
    the pair can steer the stance.

    Args:
        claim: the claim as extracted.
        claim_date: the date the claim refers to; None when the text states
            none, so the claim is about the present.
        document: the source with its database metadata and full text.
        validity: the validity of the source's catalogue entry.

    Returns:
        The prompt; every item is data.

    Features:
        US-ZRD-01, US-ZRD-04, F-15, F-16
    """
    published = document.source.published_at
    return Prompt(
        instructions=STANCE_INSTRUCTIONS,
        data=(
            claim,
            claim_date.isoformat() if claim_date else NO_CLAIM_DATE,
            published.isoformat() if published else UNKNOWN_DATE,
            validity,
            document.text,
        ),
    )


async def assess_stance(
    llm: LlmPort,
    claim: str,
    claim_date: date | None,
    document: SourceDocument,
    validity: Validity,
) -> tuple[CitationDraft | None, LlmUsage, str]:
    """Ask the model how one source bears on one claim.

    Args:
        llm: the language model.
        claim: the claim as extracted.
        claim_date: the date the claim refers to; None when the text states none.
        document: the source with its database metadata and full text.
        validity: the validity of the source's catalogue entry.

    Returns:
        The proposed citation (None when the source is not about the claim), the
        call's usage and the part of the claim the source does not confirm
        (empty when it confirms all). Partial support is only context: a verdict
        is never stronger than what the citations confirm.

    A model failure propagates.

    Features:
        US-ZRD-01, US-ZRD-04, F-15, F-16
    """
    prompt = stance_prompt(claim, claim_date, document, validity)
    answer = await llm.complete(prompt, StanceJudgement)
    judged = answer.output
    if not judged.relevant:
        return None, answer.usage, ""
    partial = judged.stance == "supports" and bool(judged.missing.strip())
    draft = CitationDraft(
        source_id=document.source.id,
        fragment=judged.fragment,
        stance="context" if partial else judged.stance,
        validity=validity,
    )
    return draft, answer.usage, judged.missing.strip() if partial else ""
