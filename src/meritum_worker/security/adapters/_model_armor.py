"""Model Armor gate: prompt injection and jailbreak filter in the ``eu`` multi-region.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-14, ADR-35
"""

import asyncio

from google.auth import default as adc_lookup
from google.auth.credentials import Credentials
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request
from httpx2 import AsyncClient
from meritum_core.security.injection import TextRange
from pydantic import BaseModel, ConfigDict, Field

from meritum_worker.security.adapters._http import post_reply, skipped
from meritum_worker.security.constants import (
    HTTP_TIMEOUT_SECONDS,
    MODEL_ARMOR_ENDPOINT,
    MODEL_ARMOR_EXECUTED,
    MODEL_ARMOR_LOCATION,
    MODEL_ARMOR_MATCH,
    MODEL_ARMOR_SCOPES,
)
from meritum_worker.security.settings import (
    InjectionGateProvider,
    InjectionGateSettings,
)


class _PiResult(BaseModel):
    execution_state: str = Field(default="", alias="executionState")
    match_state: str = Field(default="", alias="matchState")


class _PiFilter(BaseModel):
    result: _PiResult = Field(alias="piAndJailbreakFilterResult")


class _Filters(BaseModel):
    pi_and_jailbreak: _PiFilter | None = None


class _Sanitization(BaseModel):
    filter_results: _Filters = Field(default=_Filters(), alias="filterResults")


class _Reply(BaseModel):
    model_config = ConfigDict(frozen=True)

    sanitization_result: _Sanitization = Field(alias="sanitizationResult")


class ModelArmorGate:
    """InjectionGatePort on Model Armor's ``sanitizeUserPrompt`` (ADR-35).

    Model Armor gives no offsets for injections, so a match flags the whole text;
    the detector widens nothing further. Multi-language detection is on for every
    request, since most texts are Polish.

    Args:
        settings: Validated ``model_armor`` settings (project and template set).
        credentials: Google credentials; Application Default Credentials when None.
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-14, ADR-35
    """

    def __init__(
        self,
        settings: InjectionGateSettings,
        *,
        credentials: Credentials | None = None,
        http_client: AsyncClient | None = None,
    ) -> None:
        self._retries = settings.retries
        self._credentials = credentials
        self._client = http_client or AsyncClient(timeout=HTTP_TIMEOUT_SECONDS)
        self._url = (
            f"{MODEL_ARMOR_ENDPOINT}/projects/{settings.project}"
            f"/locations/{MODEL_ARMOR_LOCATION}/templates/{settings.template}"
            ":sanitizeUserPrompt"
        )

    async def screen(self, text: str) -> tuple[TextRange, ...]:
        """Screen ``text`` with the template's prompt injection filter.

        Args:
            text: User or page text, sent to Model Armor as the user prompt.

        Returns:
            The whole text when the filter matched; nothing when it did not,
            or when the gate was skipped (logged).
        """
        if not text.strip():
            return ()
        token = await self._token()
        if token is None:
            return ()
        reply = await post_reply(
            self._client,
            url=self._url,
            body={
                "userPromptData": {"text": text},
                "multiLanguageDetectionMetadata": {
                    "enableMultiLanguageDetection": True
                },
            },
            headers={"Authorization": f"Bearer {token}"},
            retries=self._retries,
            reply=_Reply,
            provider=InjectionGateProvider.MODEL_ARMOR,
        )
        flagged = reply is not None and _matched(reply)
        return (TextRange(0, len(text)),) if flagged else ()

    async def _token(self) -> str | None:
        try:
            if self._credentials is None:
                self._credentials, _ = await asyncio.to_thread(
                    adc_lookup, scopes=MODEL_ARMOR_SCOPES
                )
            credentials = self._credentials
            if not credentials.valid:
                await asyncio.to_thread(credentials.refresh, Request())
        except GoogleAuthError:
            skipped(InjectionGateProvider.MODEL_ARMOR, "credentials were refused")
            return None
        return str(credentials.token)


def _matched(reply: _Reply) -> bool:
    # A filter that is missing or did not run is a skip, not a clean result.
    pi_filter = reply.sanitization_result.filter_results.pi_and_jailbreak
    if pi_filter is None:
        skipped(InjectionGateProvider.MODEL_ARMOR, "template has no injection filter")
        return False
    if pi_filter.result.execution_state != MODEL_ARMOR_EXECUTED:
        skipped(InjectionGateProvider.MODEL_ARMOR, "filter did not run")
        return False
    return pi_filter.result.match_state == MODEL_ARMOR_MATCH
