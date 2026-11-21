"""Model comparison on hand-made runs and config files, no model or network (#40)."""

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import pytest
from meritum_core.checks import CheckResult
from meritum_core.checks.contracts import ClaimResult
from pydantic import ValidationError

from meritum_worker.observability import (
    CaseRun,
    GoldenCase,
    compare_models,
    load_model_config,
    meritum_eval,
)

type Make[T] = Callable[..., T]

AT = datetime(2026, 11, 22, tzinfo=UTC)
CONFIG = """
name = "{name}"

[llm]
provider = "stub"
model = "{model}"
reasoning = "low"
"""


def _config(tmp_path: Path, name: str, model: str = "stub-model") -> Path:
    path = tmp_path / f"{name}.toml"
    path.write_text(CONFIG.format(name=name, model=model), encoding="utf-8")
    return path


def test_config_file_names_the_model_and_its_settings(tmp_path: Path) -> None:
    config = load_model_config(_config(tmp_path, "a", model="vendor/model-x"))
    assert config.name == "a"
    assert config.llm.model == "vendor/model-x"
    assert config.llm.reasoning == "low"


def test_openrouter_key_comes_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "or.toml"
    path.write_text('name = "or"\n[llm]\nprovider = "openrouter"\n', encoding="utf-8")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValidationError):
        load_model_config(path)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    assert load_model_config(path).llm.openrouter_api_key is not None


def test_config_file_without_llm_table_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text('name = "bad"\n', encoding="utf-8")
    with pytest.raises(ValidationError):
        load_model_config(path)


@pytest.mark.parametrize("key", ["openrouter_api_key", "OPENROUTER_API_KEY"])
def test_config_file_with_an_api_key_is_rejected(tmp_path: Path, key: str) -> None:
    path = tmp_path / "key.toml"
    path.write_text(
        f'name = "key"\n[llm]\nprovider = "stub"\n{key} = "sk-in-file"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError, match="environment"):
        load_model_config(path)


def test_zero_data_retention_is_reported_only_for_openrouter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    path = tmp_path / "or.toml"
    path.write_text(
        'name = "or"\n[llm]\nprovider = "openrouter"\nopenrouter_zdr = false\n',
        encoding="utf-8",
    )
    configs = [load_model_config(path), load_model_config(_config(tmp_path, "s"))]
    compared = compare_models([(c, []) for c in configs], "cases.json", AT).models
    assert [m.zero_data_retention for m in compared] == [False, None]


def test_config_file_with_unknown_setting_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "typo.toml"
    path.write_text(
        'name = "typo"\n[llm]\nprovider = "stub"\nreasonig = "low"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_model_config(path)


def test_comparison_reports_each_config_with_its_metrics(
    tmp_path: Path,
    case: Make[GoldenCase],
    claim: Make[ClaimResult],
    result: Make[CheckResult],
    run: Make[CaseRun],
) -> None:
    right = result(claims=(claim("insufficient_evidence"),))
    wrong = result(claims=(claim("confirmed"),))
    fast = [
        run(case(), right, seconds=2.0, output_tokens=40, cost_usd=0.01),
        run(case(), right, seconds=4.0, output_tokens=60, cost_usd=0.03),
    ]
    slow = [run(case(), wrong, seconds=10.0, output_tokens=50, cost_usd=0.1)]
    a = load_model_config(_config(tmp_path, "a", model="model-a"))
    b = load_model_config(_config(tmp_path, "b", model="model-b"))

    comparison = compare_models([(a, fast), (b, slow)], "cases.json", AT)

    assert comparison.generated_at == AT
    assert comparison.cases_file == "cases.json"
    first, second = comparison.models
    assert (first.name, first.model, first.region) == ("a", "model-a", "global")
    assert first.reasoning == "low"
    assert first.report.macro_f1 == pytest.approx(1.0)
    assert first.report.median_seconds == pytest.approx(3.0)
    assert first.report.output_tokens_per_second == pytest.approx(100 / 6, abs=1e-4)
    assert first.report.cost_100_checks_usd == pytest.approx(2.0)
    assert second.name == "b"
    assert second.report.macro_f1 == pytest.approx(0.0)
    assert second.report.cost_100_checks_usd == pytest.approx(10.0)


def test_comparison_never_carries_the_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret-value")
    config = load_model_config(_config(tmp_path, "a"))
    dumped = compare_models([(config, [])], "cases.json", AT).model_dump_json()
    assert "sk-secret-value" not in dumped


@pytest.mark.parametrize(
    "path", sorted(Path(__file__).parents[2].glob("evals/models/*.toml")), ids=str
)
def test_repo_model_configs_are_valid(
    path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    assert load_model_config(path).name == path.stem


def test_cli_rejects_a_bad_config_before_any_model_runs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.toml"
    bad.write_text('name = "bad"\n', encoding="utf-8")
    golden = Path(__file__).parents[2] / "evals" / "golden" / "cases.json"
    with pytest.raises(SystemExit):
        meritum_eval(["--cases", str(golden), "--compare-models", str(bad)])
    assert "config:" in capsys.readouterr().err
