"""Recorded provider replies for the gate adapters: no network.

The fixtures follow the shape in each provider's API reference; they are not
captures of real calls. Replace them after the first ``-m integration`` run.
"""

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from google.oauth2.credentials import Credentials
from meritum_core.security.injection import InjectionGatePort
from pydantic import SecretStr

from meritum_worker.security import (
    InjectionGateProvider,
    InjectionGateSettings,
    build_injection_gate,
)

FIXTURES = Path(__file__).parent / "fixtures"

type Reply = tuple[int, str] | Exception
type Sent = list[httpx2.Request]
type GateFactory = Callable[[list[Reply]], tuple[InjectionGatePort, Sent]]

MODEL_ARMOR = InjectionGateSettings(
    provider=InjectionGateProvider.MODEL_ARMOR,
    project="meritum-test",
    template="meritum-injection",
)
WORKERS_AI = InjectionGateSettings(
    provider=InjectionGateProvider.WORKERS_AI,
    account_id="acc123",
    api_token=SecretStr("cf-recorded"),
    model="@cf/meta/llama-guard-3-8b",
)


def recorded(settings: InjectionGateSettings) -> GateFactory:
    """Build the gate through the factory; each HTTP call gets the next reply.

    A reply is (status, fixture name) or an exception to raise; the last repeats.
    """

    def build(replies: list[Reply]) -> tuple[InjectionGatePort, Sent]:
        sent: Sent = []

        def reply(request: httpx2.Request) -> httpx2.Response:
            planned = replies[min(len(sent), len(replies) - 1)]
            sent.append(request)
            if isinstance(planned, Exception):
                raise planned
            status, name = planned
            return httpx2.Response(status, content=(FIXTURES / name).read_bytes())

        client = httpx2.AsyncClient(transport=httpx2.MockTransport(reply))
        token = Credentials(token="recorded")  # ruff: ignore[hardcoded-password-func-arg]  # fake token, no network
        gate = build_injection_gate(settings, credentials=token, http_client=client)
        return gate, sent

    return build


@pytest.fixture
def model_armor_settings() -> InjectionGateSettings:
    return MODEL_ARMOR


@pytest.fixture
def model_armor() -> GateFactory:
    return recorded(MODEL_ARMOR)


@pytest.fixture
def workers_ai() -> GateFactory:
    return recorded(WORKERS_AI)
