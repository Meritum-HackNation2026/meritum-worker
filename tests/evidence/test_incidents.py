"""Incident matching: content by title, topic and date; domain by link and topic."""

from datetime import UTC, date, datetime

from meritum_worker.evidence import IncidentCandidate, IncidentProbe, match_incident

ON_TOPIC = (1.0, 0.0, 0.0)
OFF_TOPIC = (0.0, 1.0, 0.0)
DAY = date(2026, 11, 3)


def _candidate(
    *,
    description: tuple[float, ...] = ON_TOPIC,
    title: tuple[float, ...] | None = ON_TOPIC,
    day: date = DAY,
    domains: tuple[str, ...] = (),
    database: str = "euvsdisinfo",
) -> IncidentCandidate:
    return IncidentCandidate.model_validate(
        {
            "database": database,
            "incident_id": "case:1",
            "title": "Polish army deserts the border",
            "date": datetime(day.year, day.month, day.day, tzinfo=UTC),
            "url": "https://euvsdisinfo.eu/report/polish-army",
            "domains": domains,
            "description_vector": description,
            "title_vector": title,
        }
    )


def _probe(domain: str | None = None, on: date = DAY) -> IncidentProbe:
    return IncidentProbe(vector=ON_TOPIC, on=on, domain=domain)


def test_title_topic_and_date_make_a_content_match() -> None:
    match = match_incident(_probe(), [_candidate()])
    assert match is not None
    assert match.matched_on == "content"
    assert set(match.match_basis) == {"title", "topic", "date"}
    assert match.database == "euvsdisinfo"
    assert str(match.url) == "https://euvsdisinfo.eu/report/polish-army"


def test_a_different_title_is_no_content_match() -> None:
    assert match_incident(_probe(), [_candidate(title=OFF_TOPIC)]) is None


def test_a_distant_date_is_no_content_match() -> None:
    assert match_incident(_probe(on=date(2026, 6, 1)), [_candidate()]) is None


def test_the_domain_alone_is_no_match() -> None:
    off = _candidate(description=OFF_TOPIC, domains=("pap.pl",))
    assert match_incident(_probe("pap.pl"), [off]) is None


def test_a_listed_domain_on_topic_is_a_domain_match() -> None:
    other = _candidate(title=OFF_TOPIC, domains=("fake.example",))
    match = match_incident(_probe("fake.example"), [other])
    assert match is not None
    assert match.matched_on == "domain"
    assert {"domain", "topic"} <= set(match.match_basis)
    assert "title" not in match.match_basis


def test_organiser_incidents_match_through_the_same_function() -> None:
    match = match_incident(_probe(), [_candidate(database="organiser")])
    assert match is not None
    assert match.database == "organiser"
