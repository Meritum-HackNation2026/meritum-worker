"""Who is told about a case: staff inboxes as the backend names them.

Features:
    US-POW-05, F-26
"""

from hashlib import sha256

from meritum_worker.moderation.constants import (
    STAFF_INBOX_HASH_CHARS,
    STAFF_INBOX_PREFIX,
)
from meritum_worker.moderation.models import ModerationDeps


def staff_inbox_id(email: str) -> str:
    """The inbox id of a staff address, the same as the backend computes.

    Args:
        email: the address.

    Returns:
        ``staff:`` and the first characters of the hash of the lower-cased address.

    Features:
        US-POW-05, F-26
    """
    digest = sha256(email.strip().lower().encode()).hexdigest()
    return STAFF_INBOX_PREFIX + digest[:STAFF_INBOX_HASH_CHARS]


async def case_recipients(deps: ModerationDeps) -> list[str]:
    """The inbox ids of the moderators and administrators; analysts are left out.

    Args:
        deps: the moderation ports.

    Returns:
        The ids, sorted.

    Features:
        US-POW-05, F-26
    """
    granted = {a.email for a in await deps.staff.list_accounts() if a.role != "analyst"}
    return sorted(staff_inbox_id(e) for e in granted | deps.admin_emails)
