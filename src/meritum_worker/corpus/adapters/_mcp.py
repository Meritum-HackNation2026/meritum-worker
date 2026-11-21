"""EUvsDisinfo MCP client over streamable HTTP, in the server's stateless mode.

Each page is one JSON-RPC ``tools/call`` POST; the server answers with JSON or
with one SSE ``message`` event.

Features:
    US-KOR-08, F-11, ADR-32
"""

import json
from collections.abc import Callable
from itertools import count

from httpx2 import AsyncClient, HTTPError, Response
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from meritum_worker.corpus.constants import MCP_ACCEPT, SSE_DATA_PREFIX
from meritum_worker.corpus.errors import EuvsDisinfoUnavailableError
from meritum_worker.corpus.models import EuvsArticle, EuvsCase


class McpEuvsDisinfo:
    """The ``cases`` and ``articles`` tools of the EUvsDisinfo MCP server.

    Args:
        url: The ``/mcp`` endpoint.
        token: The API key, sent as ``Authorization: Bearer``.
        http_client: The HTTP client; owned by the caller.

    Features:
        US-KOR-08, F-11, ADR-32
    """

    def __init__(self, url: str, token: str, http_client: AsyncClient) -> None:
        self._url = url
        self._headers = {"Authorization": f"Bearer {token}", "Accept": MCP_ACCEPT}
        self._http = http_client
        self._ids = count(1)

    async def cases(self, *, limit: int, offset: int) -> list[EuvsCase]:
        """Return one page of cases (see ``EuvsDisinfoPort.cases``).

        Args:
            limit: Page size.
            offset: Cases to skip.

        Returns:
            The page.
        """
        return await self._page("cases", limit, offset, EuvsCase.from_json)

    async def articles(self, *, limit: int, offset: int) -> list[EuvsArticle]:
        """Return one page of articles (see ``EuvsDisinfoPort.articles``).

        Args:
            limit: Page size.
            offset: Articles to skip.

        Returns:
            The page.
        """
        return await self._page("articles", limit, offset, EuvsArticle.from_json)

    async def _page[T](
        self,
        tool: str,
        limit: int,
        offset: int,
        parse: Callable[[dict[str, object]], T],
    ) -> list[T]:
        request = {
            "jsonrpc": "2.0",
            "id": next(self._ids),
            "method": "tools/call",
            "params": {"name": tool, "arguments": {"limit": limit, "offset": offset}},
        }
        try:
            response = await self._http.post(
                self._url, json=request, headers=self._headers
            )
            response.raise_for_status()
            return [parse(item) for item in _items(_message(response), tool)]
        except (
            HTTPError,
            ValidationError,
            ValueError,
            TypeError,
            LookupError,
        ) as error:
            msg = f"EUvsDisinfo {tool} at offset {offset} failed: {error}"
            raise EuvsDisinfoUnavailableError(msg) from error


class _Text(BaseModel):
    text: str


class _Result(BaseModel):
    content: list[_Text] = []
    structured: object = Field(default=None, alias="structuredContent")
    is_error: bool = Field(default=False, alias="isError")


class _Message(BaseModel):
    result: _Result | None = None
    error: object = None


def _message(response: Response) -> _Message:
    if "text/event-stream" not in response.headers.get("content-type", ""):
        return _Message.model_validate_json(response.content)
    lines = response.text.splitlines()
    payloads = [
        line.removeprefix(SSE_DATA_PREFIX)
        for line in lines
        if line.startswith(SSE_DATA_PREFIX)
    ]
    if not payloads:
        msg = "empty SSE response"
        raise ValueError(msg)
    return _Message.model_validate_json(payloads[-1])


def _items(message: _Message, tool: str) -> list[dict[str, object]]:
    result = message.result
    if result is None or result.is_error:
        msg = f"tool error: {message.error or result}"
        raise ValueError(msg)
    # Without structured content the tool answers with one text block of JSON.
    data = result.structured
    if data is None:
        data = json.loads(result.content[0].text)
    # shortcut: accepts a bare list or {"<tool>": [...]}; the documented shape
    # is only "a paginated list", so check it on the first manual run.
    if isinstance(data, dict):
        data = data.get(tool)
    return TypeAdapter(list[dict[str, object]]).validate_python(data)
