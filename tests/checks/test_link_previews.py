import asyncio
import dataclasses
from collections.abc import Callable
from pathlib import Path

from meritum_core.checks import CheckRequest
from meritum_core.corpus.fetching import FetchedPage, FetchPurpose
from meritum_core.jobs.contracts import CheckInput
from tests.link_pages import recorded_pages

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.constants import FETCH_URL_STEP
from meritum_worker.checks.steps import fetch_url

LINKS = Path(__file__).resolve().parents[2] / "features" / "fixtures" / "links"
YOUTUBE = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
X_POST = "https://x.com/jack/status/20"
FACEBOOK = "https://www.facebook.com/facebook/videos/10153231379946729/"
TIKTOK = "https://www.tiktok.com/@bbcnews/video/7438029934817946912"
ARTICLE = "https://example.com/artykul"
ARTICLE_HTML = (
    "<html><head><meta property='og:title' content='Tytuł z metadanych'>"
    "<meta property='og:description' content='Opis z metadanych'></head><body>"
    "<article><h1>Inflacja spada</h1><p>Inflacja w październiku wyniosła 2,8%"
    " i była najniższa od trzech lat, podał urząd statystyczny.</p></article>"
    "</body></html>"
)
PAGES = {
    YOUTUBE: (LINKS / "youtube-watch.html").read_bytes(),
    X_POST: (LINKS / "x-status.html").read_bytes(),
    FACEBOOK: (LINKS / "facebook-video.html").read_bytes(),
    TIKTOK: (LINKS / "tiktok-video.html").read_bytes(),
    ARTICLE: ARTICLE_HTML.encode(),
}


def _fetch(url: str) -> FetchedPage:
    pages = recorded_pages(PAGES)
    return asyncio.run(pages.fetch(url, purpose=FetchPurpose.USER_LINK))


def _fetched(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps], url: str
) -> CheckState:
    request = CheckRequest(channel="web", url=url)
    state = CheckState(
        check_id="check-1", job=make_job().model_copy(update={"request": request})
    )
    deps = dataclasses.replace(make_deps(), pages=recorded_pages(PAGES))
    return asyncio.run(fetch_url(state, deps))


def test_youtube_link_gives_the_title_and_the_whole_description() -> None:
    text = _fetch(YOUTUBE).untrusted_text
    assert text.startswith("Me at the zoo\n\nMicroplastics are accumulating")
    assert text.endswith("00:17 End")
    assert "Centrum prasowe" not in text


def test_x_link_gives_the_post_without_the_replies() -> None:
    assert _fetch(X_POST).untrusted_text == (
        "jack (@jack) on X\n\njust setting up my twttr"
    )


def test_facebook_link_gives_the_public_description() -> None:
    assert _fetch(FACEBOOK).untrusted_text.endswith("How to share with just friends.")


def test_an_ordinary_page_is_still_read_by_its_main_text() -> None:
    page = _fetch(ARTICLE)
    assert "Inflacja w październiku wyniosła 2,8%" in page.untrusted_text
    assert "Opis z metadanych" not in page.untrusted_text


def test_a_video_link_says_the_recording_was_not_watched(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _fetched(make_job, make_deps, YOUTUBE)
    assert (out.page_text or "").startswith("Me at the zoo")
    (note,) = out.limitations
    assert "www.youtube.com" in note
    assert "nagrania" in note


def test_an_ordinary_page_gets_no_video_note(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    assert _fetched(make_job, make_deps, ARTICLE).limitations == []


def test_a_service_that_publishes_no_preview_is_an_unread_link(
    make_job: Callable[..., CheckInput], make_deps: Callable[..., CheckDeps]
) -> None:
    out = _fetched(make_job, make_deps, TIKTOK)
    assert out.page_text is None
    assert out.failed_steps == [FETCH_URL_STEP]
    (note,) = out.limitations
    assert note.startswith("Nie udało się otworzyć strony www.tiktok.com")
