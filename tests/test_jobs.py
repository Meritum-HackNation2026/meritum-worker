import pytest
from meritum_core.jobs.contracts import CONTRACT_VERSION

from meritum_worker import jobs


def test_ping_echoes_message_and_env() -> None:
    out = jobs.ping({"contract_version": CONTRACT_VERSION, "message": "hej"}, "dev")
    assert out == {
        "contract_version": CONTRACT_VERSION,
        "message": "hej",
        "worker_env": "dev",
    }


def test_ping_rejects_other_contract_version() -> None:
    with pytest.raises(ValueError, match="contract_version"):
        jobs.ping({"contract_version": CONTRACT_VERSION + 1}, "dev")
