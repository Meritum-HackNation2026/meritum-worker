# Architektura i jej strażnicy

Zasady są w skillu `meritum-architecture` w monorepo (`.claude/skills/meritum-architecture/SKILL.md`). Tu jest tylko to, co je egzekwuje w tym repo. Wszystkie kontrole działają lokalnie i w CI (`.github/workflows/ci.yml`, job `lint` i `tests`).

| Zasada | Kontrola |
| --- | --- |
| pionowe wycinki, prywatne `_nazwy` | `tests/architecture/test_slices.py` (pytestarch: wycinek importuje inny tylko przez jego pakiet, prywatny moduł `_x` tylko we własnym pakiecie); `scripts/check_conventions.py` (import prywatnej nazwy albo modułu innego pakietu; pakiet z modułami `_x` deklaruje `__all__`) |
| heksagonalna | `tests/architecture/test_hexagonal.py` (pytestarch: treść workflowów, `jobs.py` i wycinki takie jak `checks/workflow.py`, nie importuje DBOS ani adapterów; DBOS rejestruje i uruchamia je tylko `main.py`, wskazany w `WIRING` w `tests/architecture/conftest.py`; tam są też `adapters`, `factory` i `fakes` wycinka, bo fałszywe serwery używają transportu klienta HTTP jak adaptery, które zastępują; kroki `check` biegną w DBOS przez adapter `checks/adapters/`) |
| lintery na pełną moc | ruff `select = ["ALL"]` z `preview`, wyłączone tylko reguły sprzeczne z formatterem i konwencją Google; `ty` z `all = "error"` |
| docstringi z funkcjami produktu | ruff `D` i `DOC` (Args, Returns, Raises); `scripts/check_conventions.py`: publiczna klasa i funkcja najwyższego poziomu w `src/` ma sekcję `Features:` z ID `US-XXX-00`, `F-00`, `ADR-00` albo `none (infrastructure)`, każdy parametr jest w `Args:` (parametry `__init__` w docstringu klasy), każde pole klasy w `Attributes:` |
| najwyżej 250 linii na plik | `scripts/check_conventions.py` (`src/`, `tests/`, `scripts/`, `features/`) |
| stałe | `scripts/check_conventions.py`: stała `UPPER_CASE` na poziomie modułu tylko w `constants.py`, z adnotacją `Final` i docstringiem atrybutu zaraz pod nią |
| typy | ruff `ANN`, `ty` strict |
| złożoność | ruff `C901` (`max-complexity = 10`) i `PLR09xx` (limity w `[tool.ruff.lint.pylint]`, najwyżej 3 części warunku i 3 poziomy zagnieżdżenia) |
| martwy kod | `vulture` (ścieżki w `[tool.vulture]`; workflowy DBOS pomija `ignore_decorators`) |
| bezpieczeństwo | ruff `S` (reguły bandita) i sam `bandit` (`[tool.bandit]`); bandit to linter bezpieczeństwa, nie szuka martwego kodu |

## Wyjątki

Wąsko i zawsze z powodem: `# noqa: XXX  # powód` w linii, per-file ignore w `[tool.ruff.lint.per-file-ignores]` z komentarzem, a dla `scripts/check_conventions.py` wpis `ścieżka = "powód"` w `[tool.meritum-conventions.*-exceptions]` w `pyproject.toml`.

Obecne wyjątki:

- `src/meritum_worker/checks/steps/_*.py`: `unused-async` (ruff). Kroki zastępcze workflowu `check` mają sygnaturę `async`, której workflow oczekuje; prawdziwe kroki dodadzą `await`.
- `src/meritum_worker/checks/adapters/_dbos.py`: `no-self-use` (ruff) w linii. `DbosCheckRuntime` spełnia protokół `CheckRuntime` z metodami instancji.
- `src/meritum_worker/security/adapters/_blobs.py`, `_dbos_workflows.py`, `_removed_checks.py`: `no-self-use` (ruff) w linii. Adaptery retencji spełniają protokoły `BlobCleaner`, `WorkflowStore` i `RemovedCaseChecks` z metodami instancji.
- `src/meritum_worker/main.py`: limit 250 linii (`line-limit-exceptions`). Plik rejestruje wszystkie workflowy DBOS; podział na pakiet `main/` w osobnym PR, żeby równoległe PR-y nie miały konfliktu przy przenosinach.
- `__call__` w `ignore_names` vulture'a: sygnatura wywołania w protokole `Step` nie jest martwym kodem.
