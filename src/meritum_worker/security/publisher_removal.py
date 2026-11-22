"""The ``publisher_removal`` workflow body: take a page out of the corpus on request.

Features:
    US-KOR-05, F-10, ADR-13
"""

from datetime import datetime

from meritum_worker.corpus import (
    CorpusRetentionPort,
    PublisherRemoval,
    PublisherRemovalRequest,
)
from meritum_worker.security.constants import PUBLISHER_REMOVAL_DEADLINE


async def remove_publisher_document(
    store: CorpusRetentionPort, request: PublisherRemovalRequest, now: datetime
) -> PublisherRemoval:
    """Delete the publisher's documents at the requested URL and log it in the ledger.

    The deadline is 7 days from ``requested_at``; a removal past it still runs and
    ``removal_is_late`` tells. A URL the corpus does not hold, or holds for
    another publisher, deletes nothing but is logged too.

    Args:
        store: the corpus retention.
        request: the publisher's request.
        now: when the removal runs.

    Returns:
        The ledger row.

    Features:
        US-KOR-05, F-10, ADR-13
    """
    return await store.remove_for_publisher(request, now)


def removal_is_late(removal: PublisherRemoval) -> bool:
    """Tell whether a removal missed the 7-day deadline.

    Args:
        removal: a ledger row.

    Returns:
        True when it ran more than ``PUBLISHER_REMOVAL_DEADLINE`` after the request.

    Features:
        US-KOR-05, F-10
    """
    return removal.removed_at - removal.requested_at > PUBLISHER_REMOVAL_DEADLINE
