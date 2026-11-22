import asyncio
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from meritum_core.checks import CheckRequest
from meritum_core.jobs.contracts import CheckInput

from meritum_worker.checks import CheckDeps, CheckState
from meritum_worker.checks.steps import sanctions_warning, write_answer
from meritum_worker.evidence import SanctionsList, load_sanctions, refresh_sanctions

LIST = (
    Path(__file__).resolve().parents[2]
    / "features"
    / "fixtures"
    / "sanctions_list.json"
)
RECEIVED_AT = datetime(2026, 1, 5, 12, 0, tzinfo=UTC)
BASIS = "https://eur-lex.europa.eu/eli/reg/2022/350/oj"

type MakeDeps = Callable[..., CheckDeps]


def _linked(state: CheckState, url: str) -> CheckState:
    request = CheckRequest(channel="web", url=url)
    job = CheckInput(request=request, received_at=RECEIVED_AT, session_id="session-1")
    return state.model_copy(update={"job": job})


def _run(state: CheckState, deps: CheckDeps) -> CheckState:
    answered = asyncio.run(write_answer(state, deps))
    return asyncio.run(sanctions_warning(answered, deps))


def _warning(state: CheckState, deps: CheckDeps) -> object:
    result = _run(state, deps).result
    assert result is not None
    return result.source_warning


@pytest.fixture
def listed(make_deps: MakeDeps) -> CheckDeps:
    return replace(make_deps(), sanctions=load_sanctions(LIST))


def test_link_to_a_listed_entity_adds_a_warning_and_keeps_the_verdict(
    state: CheckState, make_deps: MakeDeps, listed: CheckDeps
) -> None:
    linked = _linked(state, "https://www.agencja-sankcyjna.example/news/1")
    with_list = _run(linked, listed).result
    without = _run(linked, make_deps()).result
    assert with_list is not None
    assert without is not None
    warning = with_list.source_warning
    assert warning is not None
    assert (warning.code, warning.entity) == (
        "eu_sanctioned_entity",
        "Przykładowa Agencja Informacyjna",
    )
    assert str(warning.basis_url) == BASIS
    assert without.source_warning is None
    assert with_list.model_copy(update={"source_warning": None}) == without.model_copy(
        update={"ai_marker": with_list.ai_marker}
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://dawny-podmiot.example/a",  # delisted entry is not current
        "https://nie-ta-agencja-sankcyjna.example/a",  # not a subdomain
        "https://example.org/agencja-sankcyjna.example",  # the domain only in the path
    ],
)
def test_no_warning_without_a_current_entry_for_the_domain(
    state: CheckState, listed: CheckDeps, url: str
) -> None:
    assert _warning(_linked(state, url), listed) is None


def test_pasted_text_without_a_link_gets_no_warning(
    state: CheckState, listed: CheckDeps
) -> None:
    assert _warning(state, listed) is None


def test_an_entry_listed_in_the_future_is_not_current() -> None:
    entry = {
        "entity": "Podmiot",
        "domains": ["x.example"],
        "basis_url": BASIS,
        "listed_on": "2030-01-01",
    }
    sanctions = SanctionsList.model_validate({"entities": [entry]})
    assert sanctions.warning_for("https://x.example/", on=date(2026, 1, 5)) is None


def test_a_broken_list_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text(json.dumps({"entities": [{"entity": "X", "domains": []}]}))
    with pytest.raises(ValueError, match="basis_url"):
        load_sanctions(path)


def test_refresh_replaces_the_copy_only_with_a_valid_download(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    good = LIST.read_bytes()

    async def download_good() -> bytes:
        await asyncio.sleep(0)
        return good

    async def download_bad() -> bytes:
        await asyncio.sleep(0)
        return b'{"entities": [{"entity": "X"}]}'

    assert asyncio.run(refresh_sanctions(download_good, path)) == 2
    with pytest.raises(ValueError, match="entities"):
        asyncio.run(refresh_sanctions(download_bad, path))
    assert path.read_bytes() == good
