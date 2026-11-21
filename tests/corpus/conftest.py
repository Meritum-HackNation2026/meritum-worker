"""Recorded reranker replies: no network.

The fixtures follow the shape in each provider's API reference; they are not
captures of real calls. Replace them after the first ``-m integration`` run.
"""

from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from google.oauth2.credentials import Credentials
from meritum_core.corpus.rerank import RerankerPort
from pydantic import SecretStr

from meritum_worker.corpus import RerankerProvider, RerankerSettings, build_reranker

FIXTURES = Path(__file__).parent / "fixtures"

type Reply = tuple[int, str] | Exception
type Sent = list[httpx2.Request]
type RerankerFactory = Callable[[list[Reply]], tuple[RerankerPort, Sent]]

VERTEX = RerankerSettings(
    provider=RerankerProvider.VERTEX, project="meritum-test", retries=2
)
WORKERS_AI = RerankerSettings(
    provider=RerankerProvider.WORKERS_AI,
    account_id="acc123",
    api_token=SecretStr("cf-recorded"),
    retries=2,
)


def recorded(settings: RerankerSettings) -> RerankerFactory:
    """Build the reranker through the factory; each HTTP call gets the next reply.

    A reply is (status, fixture name) or an exception to raise; the last repeats.
    """

    def build(replies: list[Reply]) -> tuple[RerankerPort, Sent]:
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
        reranker = build_reranker(settings, credentials=token, http_client=client)
        return reranker, sent

    return build


@pytest.fixture
def vertex() -> RerankerFactory:
    return recorded(VERTEX)


@pytest.fixture
def workers_ai() -> RerankerFactory:
    return recorded(WORKERS_AI)
