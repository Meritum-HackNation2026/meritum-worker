"""High-risk topics: embedding similarity first, the keyword list as a fallback.

Features:
    US-MOD-05, F-20, ADR-35
"""

from collections.abc import Sequence
from typing import Literal

from meritum_core.moderation import HighRiskTopic
from meritum_core.shared.embeddings import EmbeddingsPort, EmbeddingsUnavailableError

from meritum_worker.moderation.constants import TOPIC_THRESHOLD
from meritum_worker.moderation.similarity import cosine

type Classified = tuple[str, Literal["embeddings", "keywords"]]
"""The matched topic and how it was classified."""


def _description(topic: HighRiskTopic) -> str:
    return f"{topic.name}: {', '.join(topic.keywords)}"


def _by_keywords(claim: str, topics: Sequence[HighRiskTopic]) -> Classified | None:
    text = claim.casefold()
    for topic in topics:
        if any(keyword.casefold() in text for keyword in topic.keywords):
            return topic.name, "keywords"
    return None


async def classify(
    claim: str, topics: Sequence[HighRiskTopic], embeddings: EmbeddingsPort
) -> Classified | None:
    """Find the admin's high-risk topic a claim falls under.

    The claim and the topics (name and keywords) are embedded together; the
    closest topic at or above TOPIC_THRESHOLD wins. Without such a topic, or
    when the embeddings are unavailable, the keyword list decides.

    Args:
        claim: the claim text.
        topics: the admin's list.
        embeddings: the embeddings port.

    Returns:
        The topic name and how it was classified, or None.

    Features:
        US-MOD-05, F-20, ADR-35
    """
    if not topics:
        return None
    try:
        vectors = await embeddings.embed_documents(
            [claim, *(_description(t) for t in topics)]
        )
    except EmbeddingsUnavailableError:
        return _by_keywords(claim, topics)
    scores = [cosine(vectors[0], v) for v in vectors[1:]]
    best = max(range(len(topics)), key=scores.__getitem__)
    if scores[best] >= TOPIC_THRESHOLD:
        return topics[best].name, "embeddings"
    return _by_keywords(claim, topics)
