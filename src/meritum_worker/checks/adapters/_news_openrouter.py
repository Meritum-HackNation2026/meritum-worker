"""Media search on OpenRouter's ``web`` plugin, limited to the listed outlets.

Features:
    US-KOR-04, F-13, ADR-07, ADR-14
"""

from collections.abc import Sequence

from httpx2 import AsyncClient, HTTPError, TimeoutException
from meritum_core.checks.contracts import CatalogEntry
from meritum_core.corpus.web_search import (
    WebSearchCandidate,
    WebSearchTimeoutError,
    WebSearchUnavailableError,
    catalog_entry_for,
)
from meritum_core.security import MaskedText
from pydantic import BaseModel, Field, SecretStr, ValidationError

from meritum_worker.checks.news.constants import (
    NEWS_ANSWER_MAX_TOKENS,
    NEWS_MAX_RESULTS,
    NEWS_PRIVACY,
    NEWS_SEARCH_CONTEXT,
    NEWS_SEARCH_ENGINE,
    NEWS_SEARCH_TIMEOUT_SECONDS,
    OPENROUTER_CHAT_PATH,
)


class _Citation(BaseModel):
    url: str


class _Annotation(BaseModel):
    url_citation: _Citation | None = None


class _Message(BaseModel):
    annotations: list[_Annotation] = []


class _Choice(BaseModel):
    message: _Message


class _Reply(BaseModel):
    choices: list[_Choice] = Field(min_length=1)


class OpenRouterNewsSearch:
    """WebSearchPort over one chat completion with the ``web`` plugin on Exa.

    Exa searches only the outlets' hosts (``include_domains``), and
    ``catalog_entry_for`` filters the reply again. Only the addresses of the
    ``url_citation`` annotations are read; the model's answer, the titles and
    the excerpts are dropped, so a citation can only come from the page the
    fetcher reads afterwards.

    Args:
        api_key: the OpenRouter key, sent as a bearer token.
        catalog: the outlets as catalogue entries (``news_catalog``).
        model: the model the completion runs on.
        base_url: the OpenRouter API base URL of the model's region.
        http_client: HTTP client to use; tests pass one with recorded replies.

    Features:
        US-KOR-04, F-13, ADR-07, ADR-14
    """

    def __init__(
        self,
        api_key: SecretStr,
        catalog: Sequence[CatalogEntry],
        *,
        model: str,
        base_url: str,
        http_client: AsyncClient | None = None,
    ) -> None:
        self._key = api_key
        self._catalog = tuple(catalog)
        self._model = model
        self._url = base_url.rstrip("/") + OPENROUTER_CHAT_PATH
        self._client = http_client or AsyncClient(timeout=NEWS_SEARCH_TIMEOUT_SECONDS)

    async def search(
        self, query: MaskedText, *, limit: int = NEWS_MAX_RESULTS
    ) -> list[WebSearchCandidate]:
        """Search the outlets once and return the addresses found on them.

        Args:
            query: the claim with personal data masked; only its text is sent.
            limit: most addresses to return; Exa is always asked for
                ``NEWS_MAX_RESULTS``.

        Returns:
            Candidates on listed outlets in the reply's order, each once.

        Raises:
            WebSearchTimeoutError: No answer within the HTTP timeout.
            WebSearchUnavailableError: A transport error, an error status or a
                reply that is not a chat completion.
        """
        body = {
            "model": self._model,
            "messages": [{"role": "user", "content": query.text}],
            "max_tokens": NEWS_ANSWER_MAX_TOKENS,
            "plugins": [
                {
                    "id": "web",
                    "engine": NEWS_SEARCH_ENGINE,
                    "max_results": NEWS_MAX_RESULTS,
                    "include_domains": [e.domain for e in self._catalog],
                }
            ],
            "web_search_options": {"search_context_size": NEWS_SEARCH_CONTEXT},
            "provider": dict(NEWS_PRIVACY),
        }
        headers = {"Authorization": f"Bearer {self._key.get_secret_value()}"}
        try:
            response = await self._client.post(self._url, json=body, headers=headers)
            response.raise_for_status()
            reply = _Reply.model_validate_json(response.content)
        except TimeoutException as exc:
            msg = "openrouter web search timed out"
            raise WebSearchTimeoutError(msg) from exc
        except (HTTPError, ValidationError) as exc:
            msg = f"openrouter web search failed: {type(exc).__name__}"
            raise WebSearchUnavailableError(msg) from exc
        cited = (a.url_citation for a in reply.choices[0].message.annotations)
        urls = dict.fromkeys(c.url for c in cited if c is not None)
        entries = ((url, catalog_entry_for(url, self._catalog)) for url in urls)
        return [
            WebSearchCandidate(url=url, domain=e.domain, publisher_id=e.publisher_id)
            for url, e in entries
            if e is not None
        ][:limit]
