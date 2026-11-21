# meritum-worker

Workery Meritum: trwałe workflowy [DBOS](https://docs.dbos.dev/) do długich operacji w tle, na PostgreSQL. Zadania zleca [meritum-backend](https://github.com/Meritum-HackNation2026/meritum-backend) przez `DBOSClient`, a nazwy workflowów, kolejki i modele danych są w [meritum-core](https://github.com/Meritum-HackNation2026/meritum-core) (`meritum_core.jobs.contracts`).

| Środowisko | Gałąź | Kontener | Schemat aplikacji | Baza DBOS | Wersja aplikacji DBOS |
| --- | --- | --- | --- | --- | --- |
| dev | `develop` | `meritum-worker-dev` | `app_dev` (rola `meritum_worker_dev`) | `meritum_dbos_dev` | `dev` |
| prd | `main` | `meritum-worker-prd` | `app_prd` (rola `meritum_worker_prd`) | `meritum_dbos_prd` | `prd` |

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

Workflow `check` bierze model, repozytorium zapisów, fetcher stron (ochrona SSRF) i bramkę maskowania z fabryk meritum-core, a konfigurację ze zmiennych środowiska:

| Zmienna | Domyślnie | Znaczenie |
| --- | --- | --- |
| `MERITUM_LLM_PROVIDER` | `stub` | `stub` (bez kluczy i sieci) albo `vertex` |
| `MERITUM_LLM_STUB_FIXTURES` | brak | plik z odpowiedziami stuba; w obrazie `/app/features/fixtures/llm_stub_answer.json`. Bez niego stub nie ma odpowiedzi i każde sprawdzenie kończy się stanem `technical_failure`, więc dev na stubie musi go mieć |
| `MERITUM_DATABASE_PROVIDER` | `memory` | `memory` (fake'i w procesie: testy, CI, praca bez bazy; zapisy giną przy restarcie) albo `postgres` (dev i prd) |
| `MERITUM_DATABASE_URL` | brak | adres libpq z `search_path` schematu aplikacji (`app_dev`, `app_prd`); wymagany dla `postgres` |
| `MERITUM_PII_GATE` | `none` | bramka maskowania danych osobowych w tekście strony z linku: `none` (tylko wzorce telefonów, e-maili i PESEL; pominięcie bramki trafia do logu) albo `sdp` (Google Sensitive Data Protection) |
| `MERITUM_PII_PROJECT` | brak | projekt Google Cloud rozliczany za Sensitive Data Protection; wymagany dla `sdp` |
| `MERITUM_PII_LOCATION` | `europe-central2` | region UE punktu końcowego Sensitive Data Protection; sprawdzany tylko dla `sdp` |

Przy `technical_failure` wynik zawiera `failure_code` z kontraktu v4. Pole `message` w wynikach bez werdyktu zawiera tekst diagnostyczny do użytku wewnętrznego.

Tabele schematu aplikacji tworzy `meritum-migrate-app` z meritum-core, uruchamiany przez deploy (worker#32). Lokalny test z prawdziwym DBOS i PostgreSQL, także z restartem workera, potrzebuje dwóch adresów; `MERITUM_TEST_DATABASE_URL` wskazuje bazę, w której test tworzy i usuwa schemat `app_integration`:

```bash
MERITUM_DBOS_URL=postgresql://... MERITUM_TEST_DATABASE_URL=postgresql://... \
  uv run pytest -m integration tests/checks
```

Scenariusze Gherkin ze zgłoszeń trafiają do `features/<domena>.feature`, kroki do `features/steps/`; kroki wołają tylko publiczne API wycinka. Test na prawdziwej bazie albo u prawdziwego dostawcy dostaje `@pytest.mark.integration`: `uv run pytest` (także w CI) go pomija, `uv run pytest -m integration` uruchamia.

Zasady architektury i to, co je sprawdza: [docs/architecture.md](docs/architecture.md).

## Ewaluacja

Jedno polecenie uruchamia ewaluację na golden secie (`evals/golden/cases.json`) albo na własnym pliku przypadków w tym samym formacie, JSON albo CSV, z co najmniej 30 przypadkami (format: [evals/README.md](evals/README.md)). W CSV każda kolumna to pole przypadku, pusta komórka to brak pola, a `sources` i `injection` są w JSON.

```bash
uv run meritum-eval                                  # golden set, raport JSON na stdout
uv run meritum-eval --cases jury.csv --output raport.json --max-concurrency 4
```

Model wybiera konfiguracja `MERITUM_LLM_*` (tabela wyżej), więc jeden przebieg na model daje porównywalny raport. Na stubie (`MERITUM_LLM_PROVIDER=stub`) wystarczy `MERITUM_LLM_STUB_FIXTURES`; Vertex AI potrzebuje `MERITUM_LLM_MODEL`, `MERITUM_LLM_REGION` (region UE) i poświadczeń ADC (`gcloud auth application-default login`). Zapisy przebiegu zostają w pamięci procesu, więc ewaluacja nic nie pisze do bazy aplikacji. Pełny przebieg woła model, dlatego nie jest krokiem CI (ADR-28); w CI biegną tylko testy mierników i scenariusze behave na stubie.

Raport podaje modele z zapisów przebiegu i mierniki z US-OBS-04:

| Pole | Co liczy |
| --- | --- |
| `macro_f1` | werdykt głównego twierdzenia; każdy stan niebędący werdyktem to jedna osobna klasa błędu |
| `citation_coverage`, `citation_correctness` | twierdzenia z werdyktem rozstrzygającym, które mają cytat; cytaty, których host jest wśród `sources` przypadku |
| `abstention` | przypadki z oczekiwanym `insufficient_evidence` albo `not_verifiable`, które dostały ten werdykt |
| `robustness` | przypadki z `injection` z poprawnym wynikiem |
| `median_seconds`, `p95_seconds`, `max_seconds` | czas z CheckRecord (`received_at` → `answered_at`), z nieudanymi przypadkami |
| `input_tokens_per_check`, `output_tokens_per_check`, `cost_per_check_usd`, `cost_100_checks_usd` | tokeny i koszt modeli z CheckRecord; koszt jest zerowy, dopóki krok kosztu nie wycenia wywołań (worker#26) |
| `channel_consistency` | powtórzenia `other_channel`, których JSON z CheckResult ma ten sam stan, werdykty i cytowane źródła co pierwszy przypadek; sformułowania mogą się różnić |
| `information_loop` | odpowiedzi `insufficient_evidence` przekazane moderatorowi (`escalation`) |
| `scenarios`, `outcomes` | trafność per scenariusz A–J i wynik każdego przypadku |

Wynik przypadku liczy się według głównego twierdzenia. Gdy pasuje kilka twierdzeń, zostaje najgorszy wynik w kolejności: błędny werdykt rozstrzygający, stan niebędący werdyktem, błędne wstrzymanie się, wynik poprawny. Wyjątek w sprawdzeniu kończy przypadek stanem `technical_failure`, a przypadek zostaje w medianie czasu.

Czego przebieg jeszcze nie obsługuje:

- obrazy i zrzuty ekranu: bez OCR system odpowiada na nie `out_of_scope`. Przypadek z samym `image_text` dostaje więc `out_of_scope` bez wołania modelu, a przypadek z tekstem idzie bez `image_text`;
- atak z `injection.place = "source_page"`: strona z poleceniem czeka na kasety (ADR-27), więc przypadek biegnie na samym tekście;
- wymuszone awarie `fact_check_api` i `web_search`: kroki wyszukiwania są jeszcze zaślepkami; działa tylko `fault: llm` (model bez odpowiedzi);
- `--max-concurrency` większe niż domyślne 1 nie gwarantuje, że powtórzenie (`same_session`, `other_channel`) przyjdzie po przypadku, który powtarza, a współbieżne wywołania modelu zawyżają czas.

Polecenie uruchamiaj z katalogu repozytorium, bo domyślna ścieżka `evals/golden/cases.json` jest względna. Jeśli MSZ opublikuje jawną część zestawu referencyjnego, uruchom przebieg osobno na niej i na golden secie: każdy plik daje własny raport. Plik CSV rozdziela kolumny przecinkiem; znacznik BOM z arkusza kalkulacyjnego nie przeszkadza.

## Bramka klasyfikatora wstrzyknięć

Detektor wstrzyknięć z meritum-core (wzorce PL/EN, bramka, izolowany klasyfikator LLM) dostaje bramkę z `meritum_worker.security.build_detector`. Dostawcę wybiera `MERITUM_INJECTION_GATE_PROVIDER`; bez niego działa pusta bramka (`NullInjectionGate`), która nic nie oznacza i loguje pominięcie. Awaria dostawcy (brak odpowiedzi, błąd HTTP po ponowieniach, odrzucone poświadczenia, nieczytelna odpowiedź) też tylko pomija bramkę z wpisem w logu, bez treści tekstu; wzorce i klasyfikator LLM działają dalej. Który dostawca zostaje, rozstrzyga ewaluacja na golden secie ([worker#41](https://github.com/Meritum-HackNation2026/meritum-worker/issues/41)).

| Dostawca | Zmienne | Region | Koszt | Co wysyłamy |
| --- | --- | --- | --- | --- |
| `model_armor`: Model Armor, filtr `pi_and_jailbreak`, wykrywanie wielojęzyczne | `MERITUM_INJECTION_GATE_PROJECT`, `MERITUM_INJECTION_GATE_TEMPLATE` (szablon w lokalizacji `eu` z włączonym filtrem prompt injection); poświadczenia z ADC | multi-region `eu` (`modelarmor.eu.rep.googleapis.com`) | 2 mln tokenów miesięcznie bez opłat, potem 0,10 USD za 1 mln | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków |
| `workers_ai`: Llama Guard w Cloudflare Workers AI | `MERITUM_INJECTION_GATE_ACCOUNT_ID`, `MERITUM_INJECTION_GATE_API_TOKEN`, `MERITUM_INJECTION_GATE_MODEL` (np. `@cf/meta/llama-guard-3-8b`) | sieć Cloudflare, bez gwarancji regionu UE | `llama-guard-3-8b`: 0,484 USD za 1 mln tokenów wejścia, 0,03 USD za 1 mln wyjścia | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków, jako wiadomość `user` |

Obaj dostawcy nie podają, gdzie w tekście jest polecenie. Bramka wysyła więc tekst kawałkami po najwyżej 4000 znaków, zachodzącymi na siebie o 200 znaków, i oznacza każdy kawałek, który dostawca uznał za wstrzyknięcie. Żaden kawałek nie przekracza limitu dostawcy. Bramka sprawdza najwyżej 25 kawałków (ok. 95 tys. znaków); reszta dłuższej strony omija bramkę z wpisem w logu, a sprawdzają ją dalej wzorce i izolowany LLM z core. Pierwsze pominięcie (awaria, odrzucone poświadczenia) kończy sprawdzanie pozostałych kawałków. Filtr Model Armor, który się nie wykonał (np. dla nieobsługiwanego języka), daje pominięcie bramki z wpisem w logu. Llama Guard 3 to klasyfikator treści szkodliwych, a nie wstrzyknięć: bramka liczy tylko kategorię S14 (nadużycie interpretera kodu), bo pozostałe (przemoc, wybory, zniesławienie) to tematy, które obywatele zgłaszają do sprawdzenia. Llama Prompt Guard nie ma w katalogu Workers AI. Gdy zostanie wybrany `workers_ai`, token trafia do `worker_secrets` w `deploy/deploy.sh` i do kroku `Deploy` w CI (patrz wyżej).

Prawdziwe wywołanie: ustaw zmienne i uruchom `uv run pytest -m integration tests/security`.

## Retencja i usuwanie danych

Workflow `retention` (`src/meritum_worker/security/`) startuje co godzinę (o :15 UTC) z harmonogramu DBOS. Usuwa zapisy sprawdzeń po `retention_until` razem z ich powiadomieniami, miejscem w sprawach moderatora i workflowami DBOS (także eskalacjami), potem wygasłe powiadomienia, wszystkie workflowy DBOS starsze niż 30 dni (także zawieszone i niezwiązane z osobą, np. historia synchronizacji korpusu), pliki z wolumenu starsze niż 30 dni (w tym nagrania `audio_*`, których nie użyło żadne sprawdzenie) i wpisy `removed_case_checks` starsze niż 30 dni. Na GCS pliki usuwa reguła bucketu, więc tam workflow plików nie przegląda.

Workflow `delete_subject` (zleca go backend) usuwa wszystko o jednej sesji, użytkowniku albo `channel_user_hash`: workflowy sprawdzeń (działające najpierw anuluje), eskalacje tych sprawdzeń, zapisy, powiadomienia, miejsca w sprawach i nagrania. DBOS zatrzymuje anulowany workflow dopiero przed następnym krokiem, więc po minucie (`ERASURE_SETTLE`) usuwanie przechodzi drugi raz i kasuje zapis, który zdążył zapisać krok trwający w chwili anulowania. Jego własne wejście zawiera identyfikator osoby, więc przebieg `retention` usuwa go po godzinie od startu przebiegu, najpóźniej dwie godziny po nim. Backend musi odczytać wynik w tym czasie. W `removed_case_checks` zostaje sam losowy `check_id`, żeby zapis sprawy wczytanej przed usunięciem go nie przywrócił (core#74).

Retencja pełnych tekstów korpusu (90 dni) i wnioski wydawców czekają na model dokumentu z [worker#17](https://github.com/Meritum-HackNation2026/meritum-worker/issues/17).

Test na prawdziwym DBOS i PostgreSQL sprawdza, że po usunięciu żaden wiersz schematu aplikacji ani tabel DBOS nie zawiera `session_id`; tworzy i usuwa schematy `app_erasure` i `worker_erasure`:

```bash
MERITUM_TEST_DATABASE_URL=postgresql://... uv run pytest -m integration tests/security/test_erasure_integration.py
```

## Lokalna kopia EUvsDisinfo

Workflow `euvsdisinfo_sync` (`src/meritum_worker/corpus/`) czyta wszystkie przypadki i artykuły EUvsDisinfo przez serwer MCP, stronami po 100, i zapisuje różnicę: nowe wpisy dodaje, zmienione podmienia, a zniknięte ze źródła oznacza jako usunięte. Opisy przypadków i teksty fact dostają embeddingi z portu core, a teksty fact trafiają do kopii jako `Source` z `via = mcp`. Domeny z `linksToDisinformation` są zapisane w kopii (`flagged_domains()`) i czekają na ostrzeżenie o domenie z [worker#42](https://github.com/Meritum-HackNation2026/meritum-worker/issues/42). Bez `EUVSDISINFO_MCP_API_KEY` workflow nic nie pobiera i zwraca `missing_env`; tę samą listę daje `corpus.missing_env()` dla raportu gotowości.

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

Gdzie leży kopia, wybiera `build_euvsdisinfo_copy` z ustawień korpusu z meritum-core: `MERITUM_CORPUS_PROVIDER=postgres` i `MERITUM_CORPUS_DATABASE_URL` (baza ze schematem `corpus`) zapisują ją w tabelach `corpus.euvsdisinfo_entries` i `corpus.euvsdisinfo_flagged_domains`, więc przeżywa restart i deploy, a kolejny przebieg zapisuje tylko różnicę. Tabele tworzy migracja corpus `0002_euvsdisinfo_copy.sql` z meritum-core, uruchamiana tylko z `main` (worker#32). Te same zmienne wybierają w meritum-core bazę wyszukiwania w korpusie, więc jedno ustawienie przełącza oba. Prawo zapisu do schematu `corpus` ma tylko rola workera prd (`db.sh` w meritum-infra); na dev kopia w PostgreSQL działa tylko do odczytu, więc synchronizację uruchamiamy z prd. Domyślne `memory` trzyma kopię w pamięci procesu i gubi ją przy restarcie; wtedy nie uruchamiaj synchronizacji z `MERITUM_EMBEDDINGS_PROVIDER=vertex`, bo każdy przebieg embedduje całą bazę od nowa.

Test adaptera PostgreSQL uruchamiamy lokalnie na obrazie `meritum-postgres` z meritum-infra. Baza z `MERITUM_TEST_DATABASE_URL` musi mieć puste tabele kopii; test je potem czyści:

```bash
MERITUM_TEST_DATABASE_URL=postgresql://... uv run pytest -m integration tests/corpus
```

## CI/CD

`.github/workflows/ci.yml`: `lint` i `tests` na runnerach GCP, `deploy` na `dellpromaxgb10` tylko z `develop` i `main`, po zielonym CI. `deploy/deploy.sh` buduje obraz, robi migracje, podmienia kontener z `--stop-timeout 40` i czeka, aż worker zgłosi gotowość. Niedokończone workflowy wznawia nowy kontener.

### Migracje

Deploy robi je w obrazie nowej wersji, w tej kolejności, zanim ruszy stary kontener:

1. `dbos migrate` jako rola workera w osobnej bazie DBOS środowiska (`MERITUM_DBOS_URL`, baza `meritum_dbos_<env>`), z `-r meritum_api_<env>`, żeby API mogło zlecać zadania.
2. `meritum-worker-migrate`: migracje SQL z meritum-core dla schematu aplikacji `app_<env>` (`MERITUM_DATABASE_URL`). Z `main` z flagą `--corpus`, więc potem także migracje wspólnego schematu `corpus`.

Deploy z `develop` pomija migracje `corpus` i pisze w logu `corpus migrations run only from main`. Każdy zestaw (`app_<env>`, potem `corpus`) idzie w osobnej transakcji, a każdy plik raz (tabele `schema_migrations` w `app_<env>` i `corpus.schema_migrations`). Nieudana migracja kończy deploy błędem `::error title=Migration failed::migration <app_dev|app_prd|corpus> failed: …`, a stary kontener działa dalej. Przy `corpus` komunikat zaczyna się od nazwy pliku; przy `app_<env>` jest tylko błąd PostgreSQL, bo tak raportuje runner z core. Gdy padnie `corpus`, `app_prd` zostaje już zmigrowane, a stary kontener działa na nowym schemacie aplikacji; migracje są addytywne, więc to bezpieczne.

Schemat `corpus` czytają dev i prd, a dev może działać na starszym kodzie niż prd, więc migracje `corpus` muszą być zgodne wstecz: tylko nowe tabele, kolumny (z wartością domyślną albo dopuszczające `NULL`) i indeksy. Kolumnę albo tabelę usuwamy lub zmieniamy dopiero wtedy, gdy kod na `main` i na `develop` przestał jej używać, osobną migracją w kolejnym wdrożeniu (zasada z meritum-infra#13).

Lokalnie, na obrazie `meritum-postgres` z meritum-infra:

```bash
MERITUM_TEST_DATABASE_URL=postgresql://postgres:test@localhost:55432/meritum uv run pytest -m integration tests/corpus
MERITUM_ENV=local MERITUM_DATABASE_URL='postgresql://...?options=-csearch_path%3Dapp_local,public' uv run meritum-worker-migrate --corpus
```

Sekrety repozytorium (dziś `EUVSDISINFO_MCP_API_KEY`) trafiają do kontenera inną drogą niż plik środowiska. Ich lista jest w jednym miejscu, w tablicy `worker_secrets` w `deploy/deploy.sh`. Krok `Deploy` w jobie `deploy` (`.github/workflows/ci.yml`) podaje każdy z nich jako zmienną środowiska kroku z `${{ secrets.NAZWA }}`, a `deploy.sh` przekazuje go do `docker run` jako `-e NAZWA`, bez wartości. Wartość nie trafia więc do logu, linii poleceń ani pliku na serwerze. Nieustawiony sekret jest pomijany i kontener startuje bez niego. Nazwę brakującej zmiennej pokaże raport gotowości workera z [worker#28](https://github.com/Meritum-HackNation2026/meritum-worker/issues/28). Nowy sekret dopisz w obu miejscach; test `tests/test_deploy_secrets.py` pilnuje, żeby się zgadzały.

Plik `~/meritum/envs/worker-<env>.env` i rolę w bazie tworzy platforma z [meritum-infra](https://github.com/Meritum-HackNation2026/meritum-infra). Zasady gałęzi jak w backendzie: PR do `develop`, potem `develop` → `main`, bez bezpośrednich pushy.
