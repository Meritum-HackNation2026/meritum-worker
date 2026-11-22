"""Fakes of the corpus slice for tests and behave: EUvsDisinfo and web search.

Features:
    US-KOR-08, US-KOR-04, F-11, F-13
"""

import asyncio
import json

from httpx2 import AsyncClient, MockTransport, Request, Response
from meritum_core.corpus.web_search import WebSearchCandidate
from meritum_core.security.pii import MaskedText


class FakeEuvsDisinfoServer:
    """Answers ``tools/call`` for ``cases`` and ``articles`` like the real server.

    Args:
        token: The only token the server accepts.
        sse: Answer with one SSE event instead of plain JSON.
        split_data: Split the SSE event's JSON over several ``data:`` lines.

    Attributes:
        calls: ``(tool, limit, offset)`` of every page served, in order.

    Features:
        US-KOR-08, F-11
    """

    def __init__(
        self, token: str, *, sse: bool = False, split_data: bool = False
    ) -> None:
        self._token = token
        self._sse = sse
        self._split_data = split_data
        self._late_cases = 0
        self._dropped: set[str] = set()
        self._ignore_offset = False
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

    def remove_cases(
        self, count: int, *, keep_oldest: int = 10
    ) -> list[dict[str, object]]:
        """Withdraw cases, sparing the oldest ones ``change_cases`` edits.

        Args:
            count: How many.
            keep_oldest: Oldest cases left in place.

        Returns:
            The withdrawn cases, for ``restore_cases``.
        """
        end = len(self._items["cases"]) - keep_oldest
        window = slice(end - count, end)
        removed = self._items["cases"][window]
        del self._items["cases"][window]
        return removed

    def add_cases_after_first_page(self, count: int) -> None:
        """Publish new cases right after the first page is served.

        Args:
            count: How many; they shift later pages, so some cases repeat.
        """
        self._late_cases = count

    def patch_cases(self, **fields: object) -> None:
        """Overwrite fields of every case, e.g. with malformed values.

        Args:
            **fields: Field names and their new values.
        """
        for case in self._items["cases"]:
            case.update(fields)

    def ignore_offset(self) -> None:
        """Serve the first page for every offset, like a broken cache."""
        self._ignore_offset = True

    def drop_field(self, name: str) -> None:
        """Leave a field out of every served item.

        Args:
            name: The field.
        """
        self._dropped.add(name)

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
        offset = 0 if self._ignore_offset else offset
        if offset == self._failing_offset:
            return Response(500, json={"jsonrpc": "2.0", "error": {"code": -32603}})
        page = [
            {k: v for k, v in item.items() if k not in self._dropped}
            for item in self._items[tool][offset : offset + limit]
        ]
        if self._late_cases:
            self.add_cases(self._late_cases)
            self._late_cases = 0
        content = [{"type": "text", "text": json.dumps(page)}]
        message = {"jsonrpc": "2.0", "id": call["id"], "result": {"content": content}}
        return self._respond(message)

    def _respond(self, message: dict[str, object]) -> Response:
        if not self._sse:
            return Response(200, json=message)
        text = json.dumps(message, indent=1 if self._split_data else None)
        data = "".join(f"data: {line}\n" for line in text.splitlines())
        body = f"event: message\n{data}\n"
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


class FakeWebSearch:
    """WebSearchPort that finds the same candidates for every query.

    Args:
        candidates: what every search returns; none by default.

    Attributes:
        queries: the text of every query, in order.
        most_at_once: the most searches that were running at the same time.

    Features:
        US-KOR-04, US-SPR-02, F-09, F-13
    """

    def __init__(self, candidates: tuple[WebSearchCandidate, ...] = ()) -> None:
        self.queries: list[str] = []
        self.most_at_once = 0
        self._candidates = candidates
        self._running = 0

    async def search(
        self, query: MaskedText, *, limit: int = 10
    ) -> list[WebSearchCandidate]:
        """Note the query, yield once so parallel searches overlap, return candidates.

        Args:
            query: the masked claim.
            limit: most candidates returned.

        Returns:
            The first ``limit`` candidates given at construction.
        """
        self.queries.append(query.text)
        self._running += 1
        self.most_at_once = max(self.most_at_once, self._running)
        await asyncio.sleep(0)
        self._running -= 1
        return list(self._candidates[:limit])
