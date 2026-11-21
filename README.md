# meritum-worker

Workery Meritum: trwałe workflowy [DBOS](https://docs.dbos.dev/) do długich operacji w tle, na PostgreSQL. Zadania zleca [meritum-backend](https://github.com/Meritum-HackNation2026/meritum-backend) przez `DBOSClient`, a nazwy workflowów, kolejki i modele danych są w [meritum-core](https://github.com/Meritum-HackNation2026/meritum-core) (`meritum_core.jobs.contracts`).

| Środowisko | Gałąź | Kontener | Schemat (tabele DBOS i workera) | Wersja aplikacji DBOS |
| --- | --- | --- | --- | --- |
| dev | `develop` | `meritum-worker-dev` | `worker_dev` (rola `meritum_worker_dev`) | `dev` |
| prd | `main` | `meritum-worker-prd` | `worker_prd` (rola `meritum_worker_prd`) | `prd` |

Worker wykonuje tylko zadania zlecone z jego `application_version`, więc dev i prd nie podbierają sobie pracy, nawet gdyby trafiły do jednej kolejki.

## Nowy workflow

1. W meritum-core dodaj modele wejścia i wyjścia oraz `WorkflowSpec` do `WORKFLOWS`.
2. Tutaj: logika jako zwykła funkcja w `src/meritum_worker/jobs.py` (testy bez DBOS), workflow w `main.py` z `name=spec.name` i `serialization_type=WorkflowSerializationFormat.PORTABLE`.
3. Nowa kolejka: `DBOS.register_queue(...)` w `main()` po `DBOS.launch()`.

## Praca lokalna

Baza z `docker compose up -d --wait db` w repo backendu.

```bash
uv sync
uv run meritum-worker        # MERITUM_ENV=local, schemat worker_local
uv run ruff check . && uv run ruff format --check . && uv run ty check && uv run pytest
```

## CI/CD

`.github/workflows/ci.yml`: `lint` i `tests` na runnerach GCP, `deploy` na `dellpromaxgb10` tylko z `develop` i `main`, po zielonym CI. `deploy/deploy.sh` buduje obraz, uruchamia `dbos migrate` jako rola workera (z `-r meritum_api_<env>`, żeby API mogło zlecać zadania), podmienia kontener z `--stop-timeout 40` i czeka, aż worker zgłosi gotowość. Niedokończone workflowy wznawia nowy kontener.

Plik `~/meritum/envs/worker-<env>.env` i rolę w bazie tworzy platforma z [meritum-infra](https://github.com/Meritum-HackNation2026/meritum-infra). Zasady gałęzi jak w backendzie: PR do `develop`, potem `develop` → `main`, bez bezpośrednich pushy.
