"""Gate settings from ``MERITUM_INJECTION_GATE_*``: provider, account, model.

Features:
    US-BEZ-01, F-19, ADR-12, ADR-35
"""

from enum import StrEnum
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from meritum_worker.security.constants import DEFAULT_RETRIES, ENV_PREFIX


class InjectionGateProvider(StrEnum):
    """Which classifier gate ``build_injection_gate`` builds.

    Features:
        US-BEZ-01, F-19, ADR-35
    """

    NONE = "none"
    MODEL_ARMOR = "model_armor"
    WORKERS_AI = "workers_ai"


def _required(provider: InjectionGateProvider) -> tuple[str, ...]:
    match provider:
        case InjectionGateProvider.MODEL_ARMOR:
            return ("project", "template")
        case InjectionGateProvider.WORKERS_AI:
            return ("account_id", "api_token", "model")
        case InjectionGateProvider.NONE:
            return ()


class InjectionGateSettings(BaseSettings):
    """Classifier gate configuration read from ``MERITUM_INJECTION_GATE_*``.

    Attributes:
        provider: ``none`` (default: the null gate), ``model_armor`` or ``workers_ai``.
        project: Google Cloud project holding the Model Armor template.
        template: Model Armor template id in the ``eu`` location, with the prompt
            injection and jailbreak filter on.
        account_id: Cloudflare account running Workers AI.
        api_token: Cloudflare API token with Workers AI read access.
        model: Workers AI model id, e.g. ``@cf/meta/llama-guard-3-8b``.
        retries: HTTP attempts per text, the first included.

    Features:
        US-BEZ-01, F-19, ADR-12, ADR-35
    """

    model_config = SettingsConfigDict(env_prefix=ENV_PREFIX, frozen=True)

    provider: InjectionGateProvider = InjectionGateProvider.NONE
    project: str | None = Field(default=None, min_length=1)
    template: str | None = Field(default=None, min_length=1)
    account_id: str | None = Field(default=None, min_length=1)
    api_token: SecretStr | None = None
    model: str | None = Field(default=None, min_length=1)
    retries: int = Field(default=DEFAULT_RETRIES, ge=1)

    @model_validator(mode="after")
    def _provider_is_configured(self) -> Self:
        missing = [f for f in _required(self.provider) if getattr(self, f) is None]
        if missing:
            names = ", ".join(f"{ENV_PREFIX}{f.upper()}" for f in missing)
            msg = f"{names} required for {self.provider}"
            raise ValueError(msg)
        return self
