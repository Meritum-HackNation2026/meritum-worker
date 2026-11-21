"""POST with retries for gate adapters; a failure skips the gate instead of raising.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

import asyncio
import logging

from httpx2 import AsyncClient, TransportError, codes
from pydantic import BaseModel, JsonValue, ValidationError

from meritum_worker.security.constants import RETRY_BACKOFF_SECONDS

_log = logging.getLogger(__name__)


def skipped(provider: str, reason: str) -> None:
    """Log that the gate was skipped; never with the screened text.

    Args:
        provider: The gate's provider name.
        reason: Why, without user or page text.

    Features:
        US-BEZ-01, F-19, ADR-35
    """
    _log.warning("%s injection gate unavailable (%s); skipped", provider, reason)


def _is_transient(status: int) -> bool:
    return status == codes.TOO_MANY_REQUESTS or status >= codes.INTERNAL_SERVER_ERROR


async def post_reply[T: BaseModel](  # ruff: ignore[too-many-arguments]  # one call site per adapter, all keyword
    client: AsyncClient,
    *,
    url: str,
    body: dict[str, JsonValue],
    headers: dict[str, str],
    retries: int,
    reply: type[T],
    provider: str,
) -> T | None:
    """POST ``body`` and parse the first successful reply, retrying transient errors.

    Args:
        client: The HTTP client.
        url: Provider endpoint.
        body: JSON request body.
        headers: Auth headers.
        retries: Attempts, the first included.
        reply: Model of the provider's reply.
        provider: Provider name for the skip log.

    Returns:
        The parsed reply, or None (logged as a skip) when every attempt failed,
        the provider refused the request or the reply did not parse.

    Features:
        US-BEZ-01, F-19, ADR-35
    """
    last = "no reply"
    for attempt in range(retries):
        if attempt:
            await asyncio.sleep(RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))
        try:
            response = await client.post(url, json=body, headers=headers)
        except TransportError as exc:
            last = f"{type(exc).__name__} on attempt {attempt + 1}"
            continue
        last = f"HTTP {response.status_code} on attempt {attempt + 1}"
        if response.is_success:
            try:
                return reply.model_validate_json(response.content)
            except ValidationError:
                last = "reply did not parse"
                break
        if not _is_transient(response.status_code):
            break
    skipped(provider, last)
    return None
