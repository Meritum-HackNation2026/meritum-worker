"""Reranker settings: ``MERITUM_RERANKER`` picks the provider.

The rest comes from ``MERITUM_RERANKER_*``.

Features:
    US-KOR-02, US-SPR-04, F-12, ADR-35
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from meritum_worker.corpus.constants import (
    MODEL_ID,
    RERANK_RETRIES,
    RERANKER_ENV,
    RERANKER_ENV_PREFIX,
    URL_SEGMENT,
    VERTEX_RANKING_LOCATION,
)


class RerankerProvider(StrEnum):
    """Which reranker ``build_reranker`` builds.

    Features:
        US-KOR-02, US-SPR-04, F-12, ADR-35
    """

    NONE = "none"
    VERTEX = "vertex"
    WORKERS_AI = "workers_ai"


def _required(provider: RerankerProvider) -> tuple[str, ...]:
    match provider:
        case RerankerProvider.VERTEX:
            return ("project",)
        case RerankerProvider.WORKERS_AI:
            return ("account_id", "api_token")
        case RerankerProvider.NONE:
            return ()


class RerankerSettings(BaseSettings):
    """Reranker configuration read from ``MERITUM_RERANKER`` and ``MERITUM_RERANKER_*``.

    Attributes:
        provider: ``none`` (default: the null gate), ``vertex`` or ``workers_ai``.
        project: Google Cloud project billed for the Vertex AI ranking API.
        location: Location of the Vertex AI ranking config.
        account_id: Cloudflare account running Workers AI.
        api_token: Cloudflare API token with Workers AI read access.
        model: Model id; the provider's default when unset.
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
    model: str | None = Field(default=None, pattern=MODEL_ID)
    retries: int = Field(default=RERANK_RETRIES, ge=1)

    @model_validator(mode="after")
    def _provider_is_configured(self) -> Self:
        missing = [f for f in _required(self.provider) if getattr(self, f) is None]
        if missing:
            names = ", ".join(f"{RERANKER_ENV_PREFIX}{f.upper()}" for f in missing)
            msg = f"{names} required for {self.provider}"
            raise ValueError(msg)
        return self
