"""Workers AI gate: a Llama Guard model on Cloudflare, called over REST.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from httpx2 import AsyncClient
from meritum_core.security.injection import TextRange
from pydantic import BaseModel

from meritum_worker.security.adapters._http import post_reply
from meritum_worker.security.constants import (
    HTTP_TIMEOUT_SECONDS,
    WORKERS_AI_ENDPOINT,
    WORKERS_AI_INJECTION_CATEGORIES,
)
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)


class _Verdict(BaseModel):
    safe: bool
    categories: tuple[str, ...] = ()


class _Result(BaseModel):
    response: _Verdict


class _Reply(BaseModel):
    result: _Result


class WorkersAiGate:
    """InjectionGatePort on a Llama Guard model in Cloudflare Workers AI (ADR-35).

    Llama Guard gives no offsets, so a flagged text is flagged whole. Only the
    categories in ``WORKERS_AI_INJECTION_CATEGORIES`` count as an injection.

    Args:
        settings: Validated ``workers_ai`` settings (account, token, model set).
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """

    def __init__(
        self, settings: InjectionGateSettings, *, http_client: AsyncClient | None = None
    ) -> None:
        self._retries = settings.retries
        self._client = http_client or AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
        self._url = (
            f"{WORKERS_AI_ENDPOINT}/{settings.account_id}/ai/run/{settings.model}"
        )
        token = settings.api_token
        secret = "" if token is None else token.get_secret_value()
        self._headers = {"Authorization": f"Bearer {secret}"}

    async def screen(self, text: str) -> tuple[TextRange, ...]:
        """Classify ``text`` with Llama Guard as a user message.

        Args:
            text: User or page text.

        Returns:
            The whole text when the model flags an injection category; nothing
            otherwise, or when the gate was skipped (logged).
        """
        if not text.strip():
            return ()
        reply = await post_reply(
            self._client,
            url=self._url,
            body={
                "messages": [{"role": "user", "content": text}],
                "response_format": {"type": "json_object"},
                "temperature": 0,
            },
            headers=self._headers,
            retries=self._retries,
            reply=_Reply,
            provider=InjectionGateProvider.WORKERS_AI,
        )
        if reply is None:
            return ()
        verdict = reply.result.response
        flagged = not verdict.safe and bool(
            WORKERS_AI_INJECTION_CATEGORIES.intersection(verdict.categories)
        )
        return (TextRange(0, len(text)),) if flagged else ()
