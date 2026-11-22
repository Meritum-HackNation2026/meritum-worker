"""The incident match and the domain warning never change the verdict."""

from tests.evidence.incident_support import MATCHES, answered, supported


def test_incident_and_domain_warning_leave_the_verdict_unchanged() -> None:
    without = answered(supported())
    assert without.result is not None
    [before] = without.result.claims
    assert before.incident is None
    for match in MATCHES:
        with_match = answered(supported(), match)
        assert with_match.result is not None
        [after] = with_match.result.claims
        assert after.incident == match
        assert after.model_dump(exclude={"incident"}) == before.model_dump(
            exclude={"incident"}
        )
