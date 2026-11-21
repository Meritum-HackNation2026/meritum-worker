"""The EUvsDisinfo sync: a full scan by pages of 100, written as a difference.

The server has no "changed since" filter, so every run reads all cases and
articles and compares them with the local copy: new entries are added, changed
ones replaced, vanished ones marked deleted.

Features:
    US-KOR-08, F-11, ADR-26
"""

from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import UTC, datetime
from itertools import batched
from urllib.parse import urlsplit

from meritum_core.checks.contracts import CatalogEntry, Source
from meritum_core.shared.embeddings import EmbeddingsPort, Vector

from meritum_worker.corpus.constants import (
    ARTICLE_KEY_PREFIX,
    CASE_KEY_PREFIX,
    CATALOG_LICENSE,
    CATALOG_QUALIFIED_BECAUSE,
    PAGE_SIZE,
    PUBLISHER_ID,
    PUBLISHER_NAME,
    SOURCE_DOMAIN,
    SOURCE_LANGUAGE,
    SOURCE_TITLE_MAX,
    SOURCE_TITLE_MIN,
    TOKEN_ENV,
)
from meritum_worker.corpus.models import (
    Entry,
    EuvsArticle,
    EuvsCase,
    StoredEntry,
    SyncReport,
)
from meritum_worker.corpus.ports import EuvsCopyPort, EuvsDisinfoPort


def missing_env(env: Mapping[str, str]) -> list[str]:
    """Name the sync's unset environment variables for the readiness report.

    Args:
        env: The worker's environment, usually ``os.environ``.

    Returns:
        ``[TOKEN_ENV]`` without a token, else an empty list.

    Features:
        US-KOR-08, US-WDR-08, F-11
    """
    return [] if env.get(TOKEN_ENV, "") else [TOKEN_ENV]


def catalog_entry() -> CatalogEntry:
    """The catalogue entry of EUvsDisinfo: synced through MCP, secondary tier.

    Returns:
        The entry with ``ingest = mcp``.

    Features:
        US-KOR-08, US-KOR-01, F-11, ADR-26
    """
    return CatalogEntry(
        domain=SOURCE_DOMAIN,
        publisher=PUBLISHER_NAME,
        publisher_id=PUBLISHER_ID,
        kind="fact_check",
        tier="secondary",
        license=CATALOG_LICENSE,
        ingest="mcp",
        qualified_because=CATALOG_QUALIFIED_BECAUSE,
    )


async def sync_euvsdisinfo(
    client: EuvsDisinfoPort,
    store: EuvsCopyPort,
    embeddings: EmbeddingsPort,
    *,
    now: datetime,
) -> SyncReport:
    """Read every case and article and write the difference to the local copy.

    Every page is read and embedded before the first write, so a failure of
    the server (``EuvsDisinfoUnavailableError``) or of the embeddings leaves the
    copy as it was. An entry seen twice (pages shift while the source grows)
    counts once; one missed because the source shrank mid-scan is marked
    deleted and comes back on the next run.

    Args:
        client: The EUvsDisinfo MCP client.
        store: The local copy.
        embeddings: Multilingual embeddings for descriptions and fact texts.
        now: When the sync runs; marks deleted entries and fetched sources.

    Returns:
        How many entries were added, updated and marked deleted.

    Features:
        US-KOR-08, F-11, ADR-26
    """
    cases = await _all_pages(client.cases)
    articles = await _all_pages(client.articles)
    entries = [_case_entry(c) for c in cases] + [_article_entry(a) for a in articles]
    fetched = list({e.key: e for e in entries}.values())
    stored = {s.entry.key: s for s in await store.entries()}
    fresh = [e for e in fetched if _is_fresh(e, stored.get(e.key))]
    keys = {e.key for e in fetched}
    gone = [k for k, s in stored.items() if s.deleted_at is None and k not in keys]
    await store.upsert(await _embedded(fresh, embeddings, now))
    await store.mark_deleted(gone, now)
    await store.replace_flagged_domains(_flagged_domains(fetched))
    added = sum(e.key not in stored for e in fresh)
    return SyncReport(added=added, updated=len(fresh) - added, deleted=len(gone))


async def _all_pages[T](page: Callable[..., Awaitable[list[T]]]) -> list[T]:
    items: list[T] = []
    while True:
        batch = await page(limit=PAGE_SIZE, offset=len(items))
        items += batch
        if len(batch) < PAGE_SIZE:
            return items


def _is_fresh(entry: Entry, stored: StoredEntry | None) -> bool:
    return stored is None or stored.deleted_at is not None or stored.entry != entry


def _domain(link: str) -> str | None:
    host = urlsplit(link).hostname
    return None if host is None else host.removeprefix("www.")


def _case_entry(case: EuvsCase) -> Entry:
    domains = {d for d in map(_domain, case.links) if d is not None}
    return Entry(
        key=f"{CASE_KEY_PREFIX}{case.id}",
        kind="case",
        title=case.title,
        url=case.url,
        published_at=datetime.fromtimestamp(case.date, UTC),
        description=case.claim,
        fact=case.fact,
        domains=tuple(sorted(domains)),
    )


def _article_entry(article: EuvsArticle) -> Entry:
    published = article.date_gmt
    if published is not None and published.tzinfo is None:
        published = published.replace(tzinfo=UTC)  # dateGmt carries no offset
    return Entry(
        key=f"{ARTICLE_KEY_PREFIX}{article.id}",
        kind="article",
        title=article.title,
        url=article.url,
        published_at=published,
        description=article.content,
    )


async def _embedded(
    entries: Sequence[Entry], embeddings: EmbeddingsPort, now: datetime
) -> list[StoredEntry]:
    descriptions = await _embed([e.description for e in entries], embeddings)
    with_fact = [e for e in entries if e.fact is not None]
    facts = await _embed([e.fact or "" for e in with_fact], embeddings)
    fact_vectors = dict(zip((e.key for e in with_fact), facts, strict=True))
    return [
        StoredEntry(
            entry=entry,
            description_vector=vector,
            fact_vector=fact_vectors.get(entry.key),
            source=_fact_source(entry, now) if entry.fact is not None else None,
        )
        for entry, vector in zip(entries, descriptions, strict=True)
    ]


async def _embed(texts: Sequence[str], embeddings: EmbeddingsPort) -> list[Vector]:
    vectors: list[Vector] = []
    for chunk in batched(texts, PAGE_SIZE, strict=False):
        vectors += await embeddings.embed_documents(chunk)
    return vectors


def _fact_source(entry: Entry, fetched_at: datetime) -> Source:
    case_id = entry.key.removeprefix(CASE_KEY_PREFIX)
    too_short = len(entry.title) < SOURCE_TITLE_MIN
    title = f"EUvsDisinfo {case_id}" if too_short else entry.title
    return Source(
        id=f"euvsdisinfo-case-{case_id}",
        title=title[:SOURCE_TITLE_MAX],
        publisher=PUBLISHER_NAME,
        publisher_id=PUBLISHER_ID,
        url=entry.url,
        domain=SOURCE_DOMAIN,
        kind="fact_check",
        tier="secondary",
        published_at=entry.published_at,
        fetched_at=fetched_at,
        language=SOURCE_LANGUAGE,
        via="mcp",
    )


def _flagged_domains(entries: Sequence[Entry]) -> dict[str, tuple[str, ...]]:
    cases: defaultdict[str, list[str]] = defaultdict(list)
    for entry in entries:
        for domain in entry.domains:
            cases[domain].append(entry.key)
    return {domain: tuple(sorted(keys)) for domain, keys in sorted(cases.items())}
