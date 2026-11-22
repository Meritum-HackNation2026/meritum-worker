"""Reranker settings: ``MERITUM_RERANKER`` picks the provider.

The rest comes from ``MERITUM_RERANKER_*``.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-35
"""

import re
from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from meritum_worker.corpus.constants import (
    MODEL_ID,
    OPENROUTER_MODEL_ID,
    RERANK_RETRIES,
    RERANKER_ENV,
    RERANKER_ENV_PREFIX,
    URL_SEGMENT,
    VERTEX_RANKING_LOCATION,
)
from meritum_worker.corpus.fact_check_constants import FACT_CHECK_ENV_PREFIX


class RerankerProvider(StrEnum):
    """Which reranker ``build_reranker`` builds.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """

    NONE = "none"
    VERTEX = "vertex"
    WORKERS_AI = "workers_ai"
    OPENROUTER = "openrouter"


def _required(provider: RerankerProvider) -> tuple[str, ...]:
    match provider:
        case RerankerProvider.VERTEX:
            return ("project",)
        case RerankerProvider.WORKERS_AI:
            return ("account_id", "api_token")
        case RerankerProvider.OPENROUTER:
            return ("api_token",)
        case RerankerProvider.NONE:
            return ()


class RerankerSettings(BaseSettings):
    """Reranker configuration read from ``MERITUM_RERANKER`` and ``MERITUM_RERANKER_*``.

    Attributes:
        provider: ``none`` (default: the null gate), ``vertex``, ``workers_ai``
            or ``openrouter``.
        project: Google Cloud project billed for the Vertex AI ranking API.
        location: Location of the Vertex AI ranking config.
        account_id: Cloudflare account running Workers AI.
        api_token: Cloudflare API token with Workers AI read access, or the
            OpenRouter API key.
        model: Model id; the provider's default when unset. OpenRouter ids may
            hold a ``.`` (``cohere/rerank-v3.5``), the others may not.
        retries: HTTP attempts per reranking, the first included.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """

    model_config = SettingsConfigDict(
        env_prefix=RERANKER_ENV_PREFIX, frozen=True, validate_by_name=True
    )

    provider: RerankerProvider = Field(
        default=RerankerProvider.NONE, validation_alias=RERANKER_ENV
    )
    project: str | None = Field(default=None, pattern=URL_SEGMENT)
    location: str = Field(default=VERTEX_RANKING_LOCATION, pattern=URL_SEGMENT)
    account_id: str | None = Field(default=None, pattern=URL_SEGMENT)
    api_token: SecretStr | None = Field(default=None, min_length=1)
    model: str | None = None
    retries: int = Field(default=RERANK_RETRIES, ge=1)

    @model_validator(mode="after")
    def _provider_is_configured(self) -> Self:
        pattern = (
            OPENROUTER_MODEL_ID
            if self.provider is RerankerProvider.OPENROUTER
            else MODEL_ID
        )
        if self.model is not None and not re.fullmatch(pattern, self.model):
            msg = f"model must match {pattern}"
            raise ValueError(msg)
        missing = [f for f in _required(self.provider) if getattr(self, f) is None]
        if missing:
            names = ", ".join(f"{RERANKER_ENV_PREFIX}{f.upper()}" for f in missing)
            msg = f"{names} required for {self.provider}"
            raise ValueError(msg)
        return self


class FactCheckProvider(StrEnum):
    """Which fact-check search ``build_fact_check`` builds.

    Features:
        US-KOR-01, F-14, ADR-34
    """

    STUB = "stub"
    GOOGLE = "google"


class FactCheckSettings(BaseSettings):
    """Fact Check Tools configuration from ``MERITUM_FACT_CHECK_*``.

    Attributes:
        provider: ``stub`` (default: finds no review) or ``google``.
        api_key: Google API key; empty (default) fails every ``google`` search as
            unavailable (the readiness report names it, worker#27).

    Features:
        US-KOR-01, F-14, ADR-34
    """

    model_config = SettingsConfigDict(env_prefix=FACT_CHECK_ENV_PREFIX, frozen=True)

    provider: FactCheckProvider = FactCheckProvider.STUB
    api_key: SecretStr = SecretStr("")
