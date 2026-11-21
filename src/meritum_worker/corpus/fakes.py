"""A fake EUvsDisinfo MCP server for tests and behave scenarios, no network.

Features:
    US-KOR-08, F-11
"""

import json

from httpx2 import AsyncClient, MockTransport, Request, Response


class FakeEuvsDisinfoServer:
    """Answers ``tools/call`` for ``cases`` and ``articles`` like the real server.

    Args:
        token: The only token the server accepts.
        sse: Answer with one SSE event instead of plain JSON.

    Attributes:
        calls: ``(tool, limit, offset)`` of every page served, in order.

    Features:
        US-KOR-08, F-11
    """

    def __init__(self, token: str, *, sse: bool = False) -> None:
        self._token = token
        self._sse = sse
        self._items: dict[str, list[dict[str, object]]] = {"cases": [], "articles": []}
        self._next_id = 1
        self._failing_offset: int | None = None
        self.calls: list[tuple[str, int, int]] = []

    def client(self) -> AsyncClient:
        """Return an HTTP client whose requests reach this server.

        Returns:
            The client.
        """
        return AsyncClient(transport=MockTransport(self._handle))

    def seed(self, *, cases: int, articles: int) -> None:
        """Add cases and articles, newest first like the real server.

        Args:
            cases: Cases to add.
            articles: Articles to add.
        """
        self.add_cases(cases)
        for _ in range(articles):
            article_id = self._take_id()
            self._items["articles"].insert(0, _article(article_id))

    def add_cases(self, count: int) -> None:
        """Publish new cases.

        Args:
            count: How many.
        """
        for _ in range(count):
            self._items["cases"].insert(0, _case(self._take_id()))

    def change_cases(self, count: int) -> None:
        """Edit the fact text of the oldest cases.

        Args:
            count: How many.
        """
        for case in self._items["cases"][-count:]:
            case["fact"] = f"{case['fact']} Updated."

    def remove_cases(self, count: int) -> list[dict[str, object]]:
        """Withdraw cases, skipping the 10 oldest (``change_cases`` edits those).

        Args:
            count: How many.

        Returns:
            The withdrawn cases, for ``restore_cases``.
        """
        removed = self._items["cases"][-count - 10 : -10]
        del self._items["cases"][-count - 10 : -10]
        return removed

    def restore_cases(self, cases: list[dict[str, object]]) -> None:
        """Publish withdrawn cases again.

        Args:
            cases: Cases from ``remove_cases``.
        """
        self._items["cases"] = cases + self._items["cases"]

    def fail_at_offset(self, offset: int) -> None:
        """Answer the page at ``offset`` with a server error.

        Args:
            offset: Offset of the failing page.
        """
        self._failing_offset = offset

    def _take_id(self) -> int:
        self._next_id += 1
        return self._next_id - 1

    def _handle(self, request: Request) -> Response:
        if request.headers.get("authorization") != f"Bearer {self._token}":
            return Response(401, json={"jsonrpc": "2.0", "error": {"code": -32001}})
        call = json.loads(request.content)
        tool = call["params"]["name"]
        limit, offset = (call["params"]["arguments"][k] for k in ("limit", "offset"))
        self.calls.append((tool, limit, offset))
        if offset == self._failing_offset:
            return Response(500, json={"jsonrpc": "2.0", "error": {"code": -32603}})
        page = self._items[tool][offset : offset + limit]
        content = [{"type": "text", "text": json.dumps(page)}]
        message = {"jsonrpc": "2.0", "id": call["id"], "result": {"content": content}}
        if not self._sse:
            return Response(200, json=message)
        body = f"event: message\ndata: {json.dumps(message)}\n\n"
        return Response(200, text=body, headers={"content-type": "text/event-stream"})


def _case(case_id: int) -> dict[str, object]:
    return {
        "id": case_id,
        "title": f"Case {case_id}: NATO plans an attack",
        "claim": f"Disinformation summary {case_id}: NATO prepares an invasion.",
        "fact": f"Fact {case_id}: no evidence supports the claim.",
        "date": 1_700_000_000 + case_id,
        "keywords": ["NATO"],
        "countries": ["Poland"],
        "linksToDisinformation": [f"https://www.fake-news-{case_id % 3}.example/a"],
        "url": f"https://euvsdisinfo.eu/report/case-{case_id}/",
    }


def _article(article_id: int) -> dict[str, object]:
    return {
        "id": article_id,
        "title": f"Article {article_id}",
        "content": f"Analysis {article_id} of a disinformation campaign.",
        "dateGmt": "2025-05-01T10:00:00",
        "keywords": [],
        "categories": [],
        "articleLanguage": ["en"],
        "thumbnailURL": "",
        "url": f"https://euvsdisinfo.eu/article-{article_id}/",
    }
