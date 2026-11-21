# meritum-worker

Workery Meritum: trwałe workflowy [DBOS](https://docs.dbos.dev/) do długich operacji w tle, na PostgreSQL. Zadania zleca [meritum-backend](https://github.com/Meritum-HackNation2026/meritum-backend) przez `DBOSClient`, a nazwy workflowów, kolejki i modele danych są w [meritum-core](https://github.com/Meritum-HackNation2026/meritum-core) (`meritum_core.jobs.contracts`).

| Środowisko | Gałąź | Kontener | Schemat (tabele DBOS i workera) | Wersja aplikacji DBOS |
| --- | --- | --- | --- | --- |
| dev | `develop` | `meritum-worker-dev` | `worker_dev` (rola `meritum_worker_dev`) | `dev` |
| prd | `main` | `meritum-worker-prd` | `worker_prd` (rola `meritum_worker_prd`) | `prd` |

Worker wykonuje tylko zadania zlecone z jego `application_version`, więc dev i prd nie podbierają sobie pracy, nawet gdyby trafiły do jednej kolejki.

## Nowy workflow

1. W meritum-core dodaj modele wejścia i wyjścia oraz `WorkflowSpec` do `WORKFLOWS`.
2. Tutaj: logika jako zwykła funkcja w wycinku swojej domeny, `src/meritum_worker/<domena>/` (np. `checks/`), z publicznym API w `__init__.py` i testami bez DBOS. `jobs.py` trzyma tylko smoke test `ping`. W `main.py` zostaje sama rejestracja: workflow z `name=spec.name` i `serialization_type=WorkflowSerializationFormat.PORTABLE`, który woła funkcję z wycinka. DBOS importuje tylko `main.py` i adaptery (`tests/architecture/`).
3. Nowa kolejka: `DBOS.register_queue(...)` w `main()` po `DBOS.launch()`.

## Praca lokalna

Baza z `docker compose up -d --wait db` w repo backendu.

```bash
uv sync
uv run meritum-worker        # MERITUM_ENV=local, schemat worker_local
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run python scripts/check_conventions.py && uv run vulture && uv run bandit -c pyproject.toml -r src scripts
uv run pytest            # z testami architektury (tests/architecture/), bez integracyjnych
uv run pytest -m integration  # tylko lokalnie: prawdziwy PostgreSQL albo dostawca
uv run behave            # scenariusze z features/
```

Workflow `check` bierze model i repozytorium zapisów z fabryk meritum-core, a konfigurację ze zmiennych środowiska:

| Zmienna | Domyślnie | Znaczenie |
| --- | --- | --- |
| `MERITUM_LLM_PROVIDER` | `stub` | `stub` (bez kluczy i sieci) albo `vertex` |
| `MERITUM_LLM_STUB_FIXTURES` | brak | plik z odpowiedziami stuba; w obrazie `/app/features/fixtures/llm_stub_answer.json`. Bez niego stub nie ma odpowiedzi i każde sprawdzenie kończy się stanem `technical_failure`, więc dev na stubie musi go mieć |
| `MERITUM_DATABASE_PROVIDER` | `memory` | `memory` (fake'i w procesie: testy, CI, praca bez bazy; zapisy giną przy restarcie) albo `postgres` (dev i prd) |
| `MERITUM_DATABASE_URL` | brak | adres libpq z `search_path` schematu aplikacji (`app_dev`, `app_prd`); wymagany dla `postgres` |

Tabele schematu aplikacji tworzy `meritum-migrate-app` z meritum-core, uruchamiany przez deploy (worker#32). Lokalny test z prawdziwym DBOS i PostgreSQL, także z restartem workera, potrzebuje dwóch adresów; `MERITUM_TEST_DATABASE_URL` wskazuje bazę, w której test tworzy i usuwa schemat `app_integration`:

```bash
MERITUM_DBOS_URL=postgresql://... MERITUM_TEST_DATABASE_URL=postgresql://... \
  uv run pytest -m integration tests/checks
```

Scenariusze Gherkin ze zgłoszeń trafiają do `features/<domena>.feature`, kroki do `features/steps/`; kroki wołają tylko publiczne API wycinka. Test na prawdziwej bazie albo u prawdziwego dostawcy dostaje `@pytest.mark.integration`: `uv run pytest` (także w CI) go pomija, `uv run pytest -m integration` uruchamia.

Zasady architektury i to, co je sprawdza: [docs/architecture.md](docs/architecture.md).

## Bramka klasyfikatora wstrzyknięć

Detektor wstrzyknięć z meritum-core (wzorce PL/EN, bramka, izolowany klasyfikator LLM) dostaje bramkę z `meritum_worker.security.build_detector`. Dostawcę wybiera `MERITUM_INJECTION_GATE_PROVIDER`; bez niego działa pusta bramka (`NullInjectionGate`), która nic nie oznacza i loguje pominięcie. Awaria dostawcy (brak odpowiedzi, błąd HTTP po ponowieniach, odrzucone poświadczenia, nieczytelna odpowiedź) też tylko pomija bramkę z wpisem w logu, bez treści tekstu; wzorce i klasyfikator LLM działają dalej. Który dostawca zostaje, rozstrzyga ewaluacja na golden secie ([worker#41](https://github.com/Meritum-HackNation2026/meritum-worker/issues/41)).

| Dostawca | Zmienne | Region | Koszt | Co wysyłamy |
| --- | --- | --- | --- | --- |
| `model_armor`: Model Armor, filtr `pi_and_jailbreak`, wykrywanie wielojęzyczne | `MERITUM_INJECTION_GATE_PROJECT`, `MERITUM_INJECTION_GATE_TEMPLATE` (szablon w lokalizacji `eu` z włączonym filtrem prompt injection); poświadczenia z ADC | multi-region `eu` (`modelarmor.eu.rep.googleapis.com`) | 2 mln tokenów miesięcznie bez opłat, potem 0,10 USD za 1 mln | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków |
| `workers_ai`: Llama Guard w Cloudflare Workers AI | `MERITUM_INJECTION_GATE_ACCOUNT_ID`, `MERITUM_INJECTION_GATE_API_TOKEN`, `MERITUM_INJECTION_GATE_MODEL` (np. `@cf/meta/llama-guard-3-8b`) | sieć Cloudflare, bez gwarancji regionu UE | `llama-guard-3-8b`: 0,484 USD za 1 mln tokenów wejścia, 0,03 USD za 1 mln wyjścia | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków, jako wiadomość `user` |

Obaj dostawcy nie podają, gdzie w tekście jest polecenie. Bramka wysyła więc tekst kawałkami po najwyżej 4000 znaków, zachodzącymi na siebie o 200 znaków, i oznacza każdy kawałek, który dostawca uznał za wstrzyknięcie. Żaden kawałek nie przekracza limitu dostawcy. Bramka sprawdza najwyżej 25 kawałków (ok. 95 tys. znaków); reszta dłuższej strony omija bramkę z wpisem w logu, a sprawdzają ją dalej wzorce i izolowany LLM z core. Pierwsze pominięcie (awaria, odrzucone poświadczenia) kończy sprawdzanie pozostałych kawałków. Filtr Model Armor, który się nie wykonał (np. dla nieobsługiwanego języka), daje pominięcie bramki z wpisem w logu. Llama Guard 3 to klasyfikator treści szkodliwych, a nie wstrzyknięć: bramka liczy tylko kategorię S14 (nadużycie interpretera kodu), bo pozostałe (przemoc, wybory, zniesławienie) to tematy, które obywatele zgłaszają do sprawdzenia. Llama Prompt Guard nie ma w katalogu Workers AI. Gdy zostanie wybrany `workers_ai`, token trafia do `worker_secrets` w `deploy/deploy.sh` i do kroku `Deploy` w CI (patrz wyżej).

Prawdziwe wywołanie: ustaw zmienne i uruchom `uv run pytest -m integration tests/security`.

## Lokalna kopia EUvsDisinfo

Workflow `euvsdisinfo_sync` (`src/meritum_worker/corpus/`) czyta wszystkie przypadki i artykuły EUvsDisinfo przez serwer MCP, stronami po 100, i zapisuje różnicę: nowe wpisy dodaje, zmienione podmienia, a zniknięte ze źródła oznacza jako usunięte. Opisy przypadków i teksty fact dostają embeddingi z portu core, a teksty fact trafiają do kopii jako `Source` z `via = mcp`. Domeny z `linksToDisinformation` idą do ostrzeżenia o domenie. Bez `EUVSDISINFO_MCP_API_KEY` workflow nic nie pobiera i zwraca `missing_env`; tę samą listę daje `corpus.missing_env()` dla raportu gotowości.

Synchronizację z prawdziwym serwerem uruchamiamy ręcznie, poza CI, w środowisku z prawem zapisu do schematu `corpus`:

```python
from dbos import DBOSClient

client = DBOSClient(
    system_database_url=URL,
    dbos_system_schema="worker_dev",
    application_name="meritum-worker",
)
client.enqueue(
    {"workflow_name": "euvsdisinfo_sync", "queue_name": "default", "app_version": "dev"}
)
```

Na razie kopia żyje w pamięci procesu workera. Trwały zapis w PostgreSQL czeka na tabele w schemacie `corpus`.

## CI/CD

`.github/workflows/ci.yml`: `lint` i `tests` na runnerach GCP, `deploy` na `dellpromaxgb10` tylko z `develop` i `main`, po zielonym CI. `deploy/deploy.sh` buduje obraz, uruchamia `dbos migrate` jako rola workera (z `-r meritum_api_<env>`, żeby API mogło zlecać zadania), podmienia kontener z `--stop-timeout 40` i czeka, aż worker zgłosi gotowość. Niedokończone workflowy wznawia nowy kontener.

Sekrety repozytorium (dziś `EUVSDISINFO_MCP_API_KEY`) trafiają do kontenera inną drogą niż plik środowiska. Ich lista jest w jednym miejscu, w tablicy `worker_secrets` w `deploy/deploy.sh`. Krok `Deploy` w jobie `deploy` (`.github/workflows/ci.yml`) podaje każdy z nich jako zmienną środowiska kroku z `${{ secrets.NAZWA }}`, a `deploy.sh` przekazuje go do `docker run` jako `-e NAZWA`, bez wartości. Wartość nie trafia więc do logu, linii poleceń ani pliku na serwerze. Nieustawiony sekret jest pomijany i kontener startuje bez niego. Nazwę brakującej zmiennej pokaże raport gotowości workera z [worker#28](https://github.com/Meritum-HackNation2026/meritum-worker/issues/28). Nowy sekret dopisz w obu miejscach; test `tests/test_deploy_secrets.py` pilnuje, żeby się zgadzały.

Plik `~/meritum/envs/worker-<env>.env` i rolę w bazie tworzy platforma z [meritum-infra](https://github.com/Meritum-HackNation2026/meritum-infra). Zasady gałęzi jak w backendzie: PR do `develop`, potem `develop` → `main`, bez bezpośrednich pushy.
