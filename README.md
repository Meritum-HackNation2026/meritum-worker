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
| `MERITUM_LLM_PROVIDER` | `openrouter` | `openrouter` (Claude Haiku 5.5, decyzja D9), `vertex` albo `stub` (bez kluczy i sieci; testy ustawiają go jawnie). Model, rozumowanie i pozostałe `MERITUM_LLM_*` opisuje README meritum-core |
| `OPENROUTER_API_KEY` | brak | klucz OpenRouter, wymagany dla `openrouter`; deploy podaje go z sekretu repozytorium (`OPENROUTER_API_KEY_DEV` z `develop`, `OPENROUTER_API_KEY_PRD` z `main`) |
| `MERITUM_LLM_STUB_FIXTURES` | brak | plik z odpowiedziami stuba; w obrazie `/app/features/fixtures/llm_stub_answer.json`. Bez niego stub nie ma odpowiedzi i każde sprawdzenie kończy się stanem `technical_failure`, więc środowisko na stubie musi go mieć |
| `MERITUM_DATABASE_PROVIDER` | `memory` | `memory` (fake'i w procesie: testy, CI, praca bez bazy; zapisy giną przy restarcie) albo `postgres` (dev i prd) |
| `MERITUM_DATABASE_URL` | brak | adres libpq z `search_path` schematu aplikacji (`app_dev`, `app_prd`); wymagany dla `postgres` |
| `MERITUM_PII_GATE` | `none` | bramka maskowania danych osobowych w tekście strony z linku: `none` (tylko wzorce telefonów, e-maili i PESEL; pominięcie bramki trafia do logu) albo `sdp` (Google Sensitive Data Protection) |
| `MERITUM_PII_PROJECT` | brak | projekt Google Cloud rozliczany za Sensitive Data Protection; wymagany dla `sdp` |
| `MERITUM_PII_LOCATION` | `europe-central2` | region UE punktu końcowego Sensitive Data Protection; sprawdzany tylko dla `sdp` |
| `MERITUM_WEB_SEARCH_PROVIDER` | `stub` | wyszukiwanie na żywo: `stub` (adresy z pliku, bez sieci) albo `vertex_search` (Vertex AI Search, lokalizacja `global`) |
| `MERITUM_WEB_SEARCH_PROJECT` | brak | projekt aplikacji Vertex AI Search (na dev `196419832223`); wymagany dla `vertex_search` |
| `MERITUM_WEB_SEARCH_ENGINE` | brak | id aplikacji (engine) nad website data store (na dev `meritum-live-search`, serving config `default_search`); wymagany dla `vertex_search` |
| `MERITUM_WEB_SEARCH_STUB_FIXTURE` | brak | plik JSON z listą adresów, które zwraca stub; bez niego stub nic nie znajduje |
| `MERITUM_CORPUS_VERSION` | `none` | migawka korpusu, którą przeszukuje krok `search_corpus` (przez `MERITUM_CORPUS_*` i `MERITUM_EMBEDDINGS_*`); przy `none` krok jest pomijany. Najwyżej 3 twierdzenia są badane naraz, w korpusie i w sieci |

Przy `technical_failure` wynik zawiera `failure_code` z kontraktu meritum-core. Pole `message` w wynikach bez werdyktu zawiera tekst diagnostyczny do użytku wewnętrznego.

Tabele schematu aplikacji tworzy `meritum-migrate-app` z meritum-core, uruchamiany przez deploy (worker#32). Lokalny test z prawdziwym DBOS i PostgreSQL, także z restartem workera, potrzebuje dwóch adresów; `MERITUM_TEST_DATABASE_URL` wskazuje bazę, w której test tworzy i usuwa schemat `app_integration`:

```bash
MERITUM_DBOS_URL=postgresql://... MERITUM_TEST_DATABASE_URL=postgresql://... \
  uv run pytest -m integration tests/checks
```

Scenariusze Gherkin ze zgłoszeń trafiają do `features/<domena>.feature`, kroki do `features/steps/`; kroki wołają tylko publiczne API wycinka. Test na prawdziwej bazie albo u prawdziwego dostawcy dostaje `@pytest.mark.integration`: `uv run pytest` (także w CI) go pomija, `uv run pytest -m integration` uruchamia.

Zasady architektury i to, co je sprawdza: [docs/architecture.md](docs/architecture.md).

## Gotowość przy starcie

Przy starcie worker sprawdza, czy ma wymagane zmienne i czy dostawcy odpowiadają, i zapisuje wynik w logu: same nazwy zmiennych i dostawców, nigdy wartości. API (`GET /api/v1/health`) zleca workflow `readiness`, który robi to samo sprawdzenie, zwraca `ReadinessReport` z meritum-core i ustawia go jako zdarzenie `readiness`. Brak zmiennej albo niedostępny dostawca nie zatrzymuje workera, tylko trafia do raportu.

Wymagane zmienne (lista w `src/meritum_worker/observability/constants.py`):

| Ścieżka | `MERITUM_ENV` | Zmienne |
| --- | --- | --- |
| lokalnie | `local` (domyślnie) | tylko zmienne modelu |
| publiczne demo | `dev`, `prd` | `MERITUM_DATABASE_URL` i zmienne modelu; `EUVSDISINFO_MCP_API_KEY` jest opcjonalny (bez niego `euvsdisinfo` jest w `unavailable_providers`, a sprawdzenia działają na lokalnej kopii) |

| `MERITUM_LLM_PROVIDER` | Zmienne modelu |
| --- | --- |
| `stub` | brak |
| `vertex` | `MERITUM_LLM_MODEL`, `MERITUM_LLM_REGION` |
| `openrouter` | `OPENROUTER_API_KEY` |

Dostawcy sprawdzani bezpłatnym zapytaniem: EUvsDisinfo (jedna strona przypadków przez MCP, tylko gdy token jest ustawiony). Model nie ma darmowego zapytania, więc sprawdzamy tylko jego zmienne. Fact Check API, wyszukiwarka i transkrypcja dostaną sondy razem ze swoimi portami (worker#43 i dalsze).

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
| `input_tokens_per_check`, `output_tokens_per_check`, `cost_per_check_usd`, `cost_100_checks_usd` | tokeny i koszt modeli z CheckRecord: koszt OpenRoutera z odpowiedzi API, koszt Vertex AI z cennika w meritum-core; wywołania wyszukiwarki wyceni worker#26 |
| `output_tokens_per_second` | tokeny odpowiedzi (z rozumowaniem, jeśli dostawca je liczy) podzielone przez cały czas sprawdzeń, które dostały jakąkolwiek odpowiedź modelu; to przepustowość całego sprawdzenia, nie sama szybkość generowania |
| `channel_consistency` | powtórzenia `other_channel`, których JSON z CheckResult ma ten sam stan, werdykty i cytowane źródła co pierwszy przypadek; sformułowania mogą się różnić |
| `information_loop` | odpowiedzi `insufficient_evidence` przekazane moderatorowi (`escalation`) |
| `corpus_versions` | migawki korpusu, do których przypięto sprawdzenia; `none` dla przypadków zakończonych przed korpusem |
| `scenarios`, `outcomes` | trafność per scenariusz A–J i wynik każdego przypadku |

Wynik przypadku liczy się według głównego twierdzenia. Gdy pasuje kilka twierdzeń, zostaje najgorszy wynik w kolejności: błędny werdykt rozstrzygający, stan niebędący werdyktem, błędne wstrzymanie się, wynik poprawny. Wyjątek w sprawdzeniu kończy przypadek stanem `technical_failure`, a przypadek zostaje w medianie czasu.

Czego przebieg jeszcze nie obsługuje:

- obrazy i zrzuty ekranu: bez OCR system odpowiada na nie `out_of_scope`. Przypadek z samym `image_text` dostaje więc `out_of_scope` bez wołania modelu, a przypadek z tekstem idzie bez `image_text`;
- atak z `injection.place = "source_page"`: przypadek biegnie na samym tekście, bo golden set nie ma jeszcze nagranej strony z poleceniem;
- wymuszone awarie `fact_check_api` i `web_search`: kroki wyszukiwania są jeszcze zaślepkami; działa tylko `fault: llm` (model bez odpowiedzi);
- `--max-concurrency` większe niż domyślne 1 nie gwarantuje, że powtórzenie (`same_session`, `other_channel`) przyjdzie po przypadku, który powtarza, a współbieżne wywołania modelu zawyżają czas.

Polecenie uruchamiaj z katalogu repozytorium, bo domyślna ścieżka `evals/golden/cases.json` jest względna. Jeśli MSZ opublikuje jawną część zestawu referencyjnego, uruchom przebieg osobno na niej i na golden secie: każdy plik daje własny raport. Plik CSV rozdziela kolumny przecinkiem; znacznik BOM z arkusza kalkulacyjnego nie przeszkadza.

`uv run meritum-eval gates --config evals/gates/<plik>.json` porównuje bramki przed LLM (ADR-35): klasyfikator wstrzyknięć, reranker, maskowanie DLP z nadmiarowym maskowaniem, a bez wdrożenia także wstępną ocenę wymowy NLI i klasyfikator wejścia. Konfiguracje, mierniki i decyzję, którą wspiera raport, opisuje [evals/reports/README.md](evals/reports/README.md). Przebiegi z prawdziwymi dostawcami uruchamiamy ręcznie, poza CI.

### Porównanie modeli

Model główny i model embeddingów wybieramy konfiguracją, więc kandydaci żyją w plikach TOML, nie w kodzie: modele językowe w `evals/models/`, embeddingi w `evals/embeddings/`. Porównanie odpala każdy plik na tym samym pliku przypadków, po kolei, i zapisuje jeden raport JSON z datą (`generated_at`), plikiem przypadków oraz dostawcą, modelem i regionem każdego kandydata.

```bash
set -a; source ../.env; set +a                       # OPENROUTER_API_KEY, nigdy w repozytorium
uv run meritum-eval --compare-models evals/models/*.toml --output evals/reports/$(date +%F)-modele.json
uv run meritum-eval --compare-embeddings evals/embeddings/*.toml --output evals/reports/$(date +%F)-embeddingi.json
```

- `--compare-models`: przy każdym kandydacie pełny raport z tabeli wyżej (`macro_f1`, `citation_correctness`, `median_seconds`, `output_tokens_per_second`, `cost_100_checks_usd` i reszta).
- `--compare-embeddings`: porównanie na zastępczym korpusie (w raporcie `corpus`), bo pełny korpus z bazy jeszcze nie powstał (worker#17). Korpusem są źródła z golden setu, tytuł i cytat, każdy adres raz. Zapytaniem jest każde różne główne twierdzenie przypadków ze źródłami, więc powtórzenia tego samego twierdzenia liczą się raz. `hit_rate` to odsetek zapytań, w których własne źródło trafiło na pierwsze miejsce, a `mean_reciprocal_rank` to średnia z 1/pozycja pierwszego własnego źródła. Koszt liczymy z `usd_per_million_chars` w pliku kandydata; przy cenniku za tokeny to przybliżenie opisane w komentarzu pliku. Kilkanaście dokumentów wystarcza, żeby porównać kandydatów między sobą, ale nie mówi, jak trafne będzie wyszukiwanie w pełnym korpusie.

Jak dodać kandydata: skopiuj plik z katalogu, zmień `name` (nazwa pliku bez `.toml`, sprawdza to test) i tabelę `[llm]` albo `[embeddings]`. Pola tabeli to pola `LlmSettings` albo `EmbeddingsSettings` z meritum-core. Nieznane pole kończy się błędem, a klucze API przychodzą wyłącznie ze środowiska. Model bez endpointu ZDR na OpenRouterze dostaje `openrouter_zdr = false` i wolno go uruchamiać tylko na golden secie, nigdy na danych użytkowników. Raporty z przebiegów z prawdziwymi modelami trafiają do `evals/reports/`. Te przebiegi robimy ręcznie, poza CI (ADR-28).

### Ręczna ocena cytatów

Wymowę każdego cytatu ocenia osobne wywołanie modelu, które widzi tylko parę twierdzenie i źródło (`meritum_worker.evidence`), a werdykt i siłę liczą reguły z meritum-core. Mierniki ewaluacji nie sprawdzają, czy model dobrze ocenił wymowę, dlatego po każdym przebiegu ewaluacji osoba z zespołu ocenia ręcznie losową próbę cytatów: co najmniej 20 cytatów z różnych przypadków, wylosowanych z wyników przebiegu. Przy każdym cytacie zapisuje, czy fragment rzeczywiście wspiera, obala albo daje kontekst twierdzeniu i czy różne miary tego samego zjawiska (szacunek a pozycja budżetu, inny rok) nie zostały uznane za sprzeczność. Wynik (liczba ocenionych cytatów, liczba błędnych wymów, przykłady) trafia do raportu w `evals/reports/` obok raportu przebiegu.

## Wyszukiwanie na żywo

Krok `search_web` biegnie równolegle z `search_corpus` (jeden etap workflow, dwa kroki DBOS). Dla każdego faktu, najwyżej 5, wysyła jedno zapytanie przez `WebSearchPort` z meritum-core, który przepuszcza tylko adresy z domen katalogu. Każdy adres pobiera fetcher z meritum-core z kontrolą `robots.txt` i Content-Signal; strona, której końcowy adres po przekierowaniu wyszedł poza katalog, odpada. Pobrana strona czeka w kwarantannie na skan detektorem wstrzyknięć: czysta jest dowodem w tym sprawdzeniu (`Source.via = web_search`, trafia do `CheckRecord.source_ids`), a strona z poleceniem wypada z `InjectionEvent(action=source_dropped)` i jej adresem w `limitations`. Sprawdzenie nie zmienia wspólnego korpusu; stronę do następnej migawki przekaże [worker#90](https://github.com/Meritum-HackNation2026/meritum-worker/issues/90). Cały krok ma jeden limit 10 s (`WEB_SEARCH_TIMEOUT` w `corpus/constants.py`) na wyszukiwanie, pobranie i skan. Wyszukiwanie, które nie skończy się w tym czasie, albo jego awaria dają `technical_failure` z kodem `web_search_unavailable`. Strona, której nie zdążyliśmy zeskanować albo której detektor nie zeskanował, nie jest dowodem, trafia tylko do logu, a sprawdzenie biegnie dalej.

### Kasety, przypięta migawka i paczka do odtworzenia

Przebieg w trybie `record` woła dostawców jak zwykle i zapisuje w kasecie każdą odpowiedź modelu i każdą pobraną stronę, razem z przypiętą migawką korpusu (`--corpus-version`). Tryb `replay` odpowiada wyłącznie z kasety: nie woła modelu, stron ani bramki maskującej, więc nie potrzebuje ich kluczy ani sieci, i przypina migawkę z kasety. Fabryka czyta jednak `MERITUM_PII_*`, `MERITUM_TRANSCRIPTION_*`, `MERITUM_WEB_SEARCH_*` i `MERITUM_INJECTION_GATE_*`, więc przy odtwarzaniu bez sekretów zostaw je puste albo ustaw na `stub`/`none`. Wywołanie, któremu w nagraniu skończył się czas, w `replay` też kończy się przekroczeniem czasu. Zapytanie, którego kaseta nie zna (inny plik przypadków, prompt albo kod), kończy przypadek stanem `technical_failure` zamiast wołać dostawcę. Kaseta nagrywa też odpowiedzi bramki maskującej (`MERITUM_PII_*`), tylko zamaskowany tekst pod skrótem oryginału, więc `replay` maskuje tak jak nagranie bez kluczy bramki. Nagranie wymaga `--corpus-version`, bo paczka podaje migawkę.

Kaseta nagrywa model, pobieranie stron, wyszukiwanie w sieci, bramkę maskującą i detektor wstrzyknięć (sam wynik skanu, bez skanowanego tekstu). Wyszukiwanie w korpusie i w bazach fact-checkerów to jeszcze zaślepki (worker#43), więc nie ma czego nagrywać; ich adaptery owiną się tak samo, gdy powstaną. Do tego czasu przypięta migawka trafia do `corpus_version` każdego wyniku i do `corpus_versions` raportu, a przeszuka ją krok `search_corpus`, gdy zastąpi zaślepkę.

```bash
uv run meritum-eval --mode record --cassette evals/cassettes/run.json \
  --corpus-version 2026-11-20T10:00Z --output raport.json
uv run meritum-eval --mode replay --cassette evals/cassettes/run.json --output raport-replay.json
uv run meritum-eval-bundle --cassette evals/cassettes/run.json --output paczka/   # te same --cases co przy nagraniu
```

Raport z `replay` ma te same wyniki i mierniki co raport nagrania; różnią się tylko czasy. Żaden przebieg z prawdziwymi dostawcami, także `replay` nagrania, nie jest krokiem CI. W CI biegną testy jednostkowe adapterów kaset i paczki oraz scenariusze behave na stubie modelu, tak jak scenariusz pliku jury. Pełny przebieg uruchamia się ręcznie albo ze strony ewaluacji.

Kaseta ma pełne teksty stron, więc nie trafia do repozytorium (`evals/cassettes/` jest w `.gitignore`) ani do paczki. `meritum-eval-bundle` zapisuje w folderze trzy pliki do publikacji:

- `cases.json`: przypadki;
- `sources.json`: adresy źródeł przypadków z cytowanymi fragmentami;
- `manifest.json`: przypięta migawka i każda strona, którą przebieg przeczytał: `document_id`, adres końcowy, `sha256` tekstu głównego (UTF-8) i `fetched_at`.

Odtworzenie migawki bez kasety: pobierz ponownie każdą stronę z `manifest.json` fetcherem z meritum-core (`build_page_fetcher`, ten sam ekstraktor tekstu głównego), policz SHA-256 jej `untrusted_text` w UTF-8 i porównaj z `sha256` z manifestu. Strona o tej samej sumie jest tą samą stroną, którą widział przebieg. Strona zmieniona od `fetched_at` ma inną sumę i wypada z porównania: wynik przypadku, który na niej polegał, nie jest już odtwarzalny z sieci.

## Bramka klasyfikatora wstrzyknięć

Detektor wstrzyknięć z meritum-core (wzorce PL/EN, bramka, izolowany klasyfikator LLM) dostaje bramkę z `meritum_worker.security.build_detector`. Dostawcę wybiera `MERITUM_INJECTION_GATE_PROVIDER`; bez niego działa pusta bramka (`NullInjectionGate`), która nic nie oznacza i loguje pominięcie. Awaria dostawcy (brak odpowiedzi, błąd HTTP po ponowieniach, odrzucone poświadczenia, nieczytelna odpowiedź) też tylko pomija bramkę z wpisem w logu, bez treści tekstu; wzorce i klasyfikator LLM działają dalej. Który dostawca zostaje, rozstrzyga ewaluacja na golden secie ([worker#41](https://github.com/Meritum-HackNation2026/meritum-worker/issues/41)).

| Dostawca | Zmienne | Region | Koszt | Co wysyłamy |
| --- | --- | --- | --- | --- |
| `model_armor`: Model Armor, filtr `pi_and_jailbreak`, wykrywanie wielojęzyczne | `MERITUM_INJECTION_GATE_PROJECT`, `MERITUM_INJECTION_GATE_TEMPLATE` (szablon w lokalizacji `eu` z włączonym filtrem prompt injection); poświadczenia z ADC | multi-region `eu` (`modelarmor.eu.rep.googleapis.com`) | 2 mln tokenów miesięcznie bez opłat, potem 0,10 USD za 1 mln | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków |
| `workers_ai`: Llama Guard w Cloudflare Workers AI | `MERITUM_INJECTION_GATE_ACCOUNT_ID`, `MERITUM_INJECTION_GATE_API_TOKEN`, `MERITUM_INJECTION_GATE_MODEL` (np. `@cf/meta/llama-guard-3-8b`) | sieć Cloudflare, bez gwarancji regionu UE | `llama-guard-3-8b`: 0,484 USD za 1 mln tokenów wejścia, 0,03 USD za 1 mln wyjścia | tekst użytkownika albo pobranej strony, kawałkami, najwyżej pierwsze ok. 95 tys. znaków, jako wiadomość `user` |

Obaj dostawcy nie podają, gdzie w tekście jest polecenie. Bramka wysyła więc tekst kawałkami po najwyżej 4000 znaków, zachodzącymi na siebie o 200 znaków, i oznacza każdy kawałek, który dostawca uznał za wstrzyknięcie. Żaden kawałek nie przekracza limitu dostawcy. Bramka sprawdza najwyżej 25 kawałków (ok. 95 tys. znaków); reszta dłuższej strony omija bramkę z wpisem w logu, a sprawdzają ją dalej wzorce i izolowany LLM z core. Pierwsze pominięcie (awaria, odrzucone poświadczenia) kończy sprawdzanie pozostałych kawałków. Filtr Model Armor, który się nie wykonał (np. dla nieobsługiwanego języka), daje pominięcie bramki z wpisem w logu. Llama Guard 3 to klasyfikator treści szkodliwych, a nie wstrzyknięć: bramka liczy tylko kategorię S14 (nadużycie interpretera kodu), bo pozostałe (przemoc, wybory, zniesławienie) to tematy, które obywatele zgłaszają do sprawdzenia. Llama Prompt Guard nie ma w katalogu Workers AI. Gdy zostanie wybrany `workers_ai`, token trafia do `worker_secrets` w `deploy/deploy.sh` i do kroku `Deploy` w CI (patrz wyżej).

Prawdziwe wywołanie: ustaw zmienne i uruchom `uv run pytest -m integration tests/security`.

## Oceny fact-checkerów (Google Fact Check Tools API)

Krok `search_fact_checks` szuka ocen ClaimReview dla każdego twierdzenia, które jest faktem (zamaskowane, jedno proste zapytanie). Dostawcę wybiera `MERITUM_FACT_CHECK_PROVIDER` (`stub` domyślnie: bez ocen; `google`), klucz to `MERITUM_FACT_CHECK_API_KEY`, wysyłany w nagłówku `X-Goog-Api-Key`, nigdy w adresie. Wydawcę rozpoznajemy po domenie z katalogu (Demagog też, choć jego stron nie pobieramy). Ocena sygnatariusza IFCN/EFCSN jest przesłanką tylko wtedy, gdy model uzna, że oceniane twierdzenie ma ten sam temat, liczby i datę; inaczej zostaje kontekstem z linkiem. Awaria, limit albo brak klucza kończy krok stanem `failed` i daje ograniczenie `fact_check_unavailable`; pusty wynik to brak oceny. API dopasowuje frazy dosłownie, więc trafianie poprawia [worker#84](https://github.com/Meritum-HackNation2026/meritum-worker/issues/84). Raport gotowości o braku klucza dodaje worker#27.

## Reranker fragmentów

Krok badań porządkuje fragmenty z wyszukiwania rerankerem typu cross-encoder (ADR-35) przez `meritum_worker.corpus.rerank_passages`, a reranker buduje `build_reranker`. Dostawcę wybiera `MERITUM_RERANKER`; bez niego działa pusta bramka z meritum-core (`NullReranker`), która zostawia kolejność z wyszukiwania i loguje pominięcie. Awaria dostawcy (brak odpowiedzi, błąd HTTP po ponowieniach, odrzucone poświadczenia, nieczytelna odpowiedź) nie jest awarią sprawdzenia: fragmenty zostają w kolejności z wyszukiwania, a do `retrieval_errors` trafia `search_corpus: reranker_unavailable`. Ranking nie jest źródłem dowodu. Który dostawca zostaje, rozstrzyga ewaluacja na golden secie ([worker#41](https://github.com/Meritum-HackNation2026/meritum-worker/issues/41)).

| Dostawca | Zmienne | Region | Koszt | Co wysyłamy |
| --- | --- | --- | --- | --- |
| `vertex`: Vertex AI ranking API, model `semantic-ranker-default-005` (25 języków, 1024 tokeny na fragment) | `MERITUM_RERANKER_PROJECT`, opcjonalnie `MERITUM_RERANKER_LOCATION` (domyślnie `global`) i `MERITUM_RERANKER_MODEL`; poświadczenia z ADC | `global` (poza UE); przewodnik po ranking API podaje tylko tę lokalizację | około 1 USD za 1000 zapytań po najwyżej 100 fragmentów, do potwierdzenia w cenniku AI Applications przed wyborem | zamaskowane twierdzenie i tekst fragmentów z korpusu (najwyżej 20 na zapytanie) |
| `workers_ai`: `@cf/baai/bge-reranker-base` w Cloudflare Workers AI | `MERITUM_RERANKER_ACCOUNT_ID`, `MERITUM_RERANKER_API_TOKEN`, opcjonalnie `MERITUM_RERANKER_MODEL` | sieć Cloudflare, bez gwarancji regionu UE; Cloudflare deklaruje brak retencji danych | 0,00311 USD za 1 mln tokenów wejścia | zamaskowane twierdzenie i tekst fragmentów (512 tokenów na fragment) |
| `openrouter`: `cohere/rerank-v3.5` (wielojęzyczny, także polski) przez OpenRouter | `MERITUM_RERANKER_API_TOKEN` (klucz OpenRouter), opcjonalnie `MERITUM_RERANKER_MODEL` (np. `cohere/rerank-4-pro`) | dostawca z ZDR wybrany przez OpenRouter; dla `cohere/rerank-v3.5` to Amazon Bedrock (`eu-central-1` albo `us-east-1`, wg [listy endpointów ZDR](https://openrouter.ai/api/v1/endpoints/zdr)) | 0,002 USD za zapytanie, czyli 2 USD za 1000 zapytań ([cennik OpenRouter](https://openrouter.ai/cohere/rerank-v3.5), listopad 2026) | zamaskowane twierdzenie i tekst fragmentów (najwyżej 20 na zapytanie) |

Adapter OpenRouter wysyła w każdym zapytaniu `provider: {"zdr": true, "data_collection": "deny"}`, jak adapter LLM z meritum-core. Jeśli model nie ma dostawcy z ZDR, OpenRouter odrzuca zapytanie i nie przekazuje tekstu dalej (sam OpenRouter go dostaje), a do `retrieval_errors` trafia `search_corpus: reranker_unavailable`.

`MERITUM_RERANKER_RETRIES` (domyślnie 2) to liczba prób HTTP na jedno porządkowanie. Rejestr podmiotów przetwarzających (`copy/privacy.json` w meritum-design-system) dostaje wybranego dostawcę w [meritum-design-system#68](https://github.com/Meritum-HackNation2026/meritum-design-system/issues/68).

Prawdziwe wywołanie: ustaw zmienne i uruchom `uv run pytest -m integration tests/corpus/test_reranker_integration.py`.

## Nagrania głosowe

Krok `transcribe_audio` czyta nagranie z `BlobStore` (`MERITUM_BLOB_*`; bez `MERITUM_BLOB_PROVIDER` magazyn w pamięci), transkrybuje je portem z meritum-core (`MERITUM_TRANSCRIPTION_*`, domyślnie stub; `speech_v2` to Chirp 3 w multi-regionie `eu`), maskuje dane osobowe i sprawdza transkrypcję jak wklejony tekst. Nieobsługiwany format albo nagranie ponad 10 min kończy się stanem `out_of_scope` z komunikatem, co wysłać zamiast; awaria dostawcy albo brak pliku: `technical_failure` z kodem `transcription_failed`. Po nagraniu dłuższym niż 55 s (tryb batch) worker zapisuje w skrzynce powiadomienie `check_done`. Plik usuwa retencja razem z zapisem sprawdzenia (osierocone nagrania po 30 dniach), a transkrypcja żyje tylko w wyniku i zapisie.

Ręczny test, czy Chirp 3 dekoduje OGG z Opus 48 kHz z Discorda bez konwersji (poza CI):

```bash
MERITUM_TRANSCRIPTION_PROVIDER=speech_v2 MERITUM_TRANSCRIPTION_PROJECT=... \
MERITUM_BLOB_PROVIDER=gcs MERITUM_BLOB_BUCKET=... \
MERITUM_TEST_AUDIO_FILE=wiadomosc.ogg uv run pytest -m integration tests/checks/test_transcription_integration.py
```

Wynik: jeszcze nie uruchomiony, bo wymaga poświadczeń GCP. Przebieg i wpisanie wyniku śledzi [worker#92](https://github.com/Meritum-HackNation2026/meritum-worker/issues/92).

## Retencja i usuwanie danych

Sprawy moderatora (`src/meritum_worker/moderation/`): workflow `escalate_claim` (przycisk „Przekaż moderatorom”, „Zgłoś błąd”, trafienie w pamięć wyników) i krok `moderator_cases` po werdykcie tworzą sprawę albo dołączają twierdzenie do otwartej (podobieństwo embeddingów od 0,85 przy zgodnych liczbach, miesiącach i nazwach własnych, okno 14 dni). Pojedynczy brak dowodów w zwykłym temacie to tylko `recommended`; sprawę otwiera temat wysokiego ryzyka (embeddingi, zapasowo słowa kluczowe), powtórka albo kliknięcie. Sprawy z kroku sprawdzenia worker ogłasza sam: `case_assigned` do skrzynek moderatorów i administratorów z `MERITUM_ADMIN_EMAILS` (link `/panel`); sprawy z `escalate_claim` ogłasza backend po odpowiedzi.

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

## Wczytywanie katalogu i migawki korpusu

Dwa zaplanowane workflowy DBOS z `src/meritum_worker/corpus/` budują korpus z katalogu źródeł z meritum-core (`load_catalog()`, `catalog.yaml`):

- `corpus_ingest` co 15 minut bierze pozycje z `role: evidence` i `ingest` równym `static`, `rss` albo `sitemap`, pomija wykluczone (`excluded`) i z `tdm_reservation: reserved`, a z pozostałych tylko te, którym od ostatniej próby (`corpus.ingest_attempts`, także nieudanej) minęło `refresh_minutes` (domyślnie raz na dobę). Pozycje `live`, `web_search`, `mcp` i `source_status` nie trafiają do korpusu. Pozycje `api` czekają na własne adaptery ([worker#82](https://github.com/Meritum-HackNation2026/meritum-worker/issues/82)), bo API odpowiadają JSON-em, którego fetcher z core nie przyjmuje. Wybór pozycji to pierwszy krok DBOS, a każda pozycja to osobny krok z ponowieniami, więc ponowiony krok pobiera wszystkie strony pozycji od nowa. Strony pobiera fetcher z core z celem `SOURCE` (ochrona SSRF, `robots.txt`, Content-Signal, znaczniki TDM w stronie), dzieli je na fragmenty do 1200 znaków (`chunk_text`), wektoryzuje portem embeddingów i zapisuje. Błąd jednej strony (także niedostępne embeddingi) trafia do raportu kroku z adresem i powodem, a przebieg idzie dalej. Raport kroku zostaje w historii workflowu DBOS.
- `corpus_snapshot` co godzinę zapisuje `corpus_version` nazwaną od godziny (`2026-11-20T10:00Z`) z manifestem: identyfikatory dokumentów, sumy kontrolne i `fetched_at`. Strona zapisana między migawkami, także strona z wyszukiwania na żywo po skanie (`corpus.store_page`), wchodzi do następnej. `store_page` odrzuca strony pozycji wykluczonych i zastrzeżonych dla TDM także na tej drodze.

Na razie każda pozycja ma jedną stronę: adres `https://<domena>` (`EntryPageDiscovery`). Wpisy z kanałów RSS i map stron dołoży [worker#22](https://github.com/Meritum-HackNation2026/meritum-worker/issues/22) jako kolejną implementację `DocumentDiscoveryPort`, więc dopiero wtedy prawdziwy korpus przekroczy 100 dokumentów.

Dokumenty leżą w `corpus.documents` (adres, domena, `publisher_id` i licencja z katalogu, `fetched_at`, suma kontrolna, pełny tekst), fragmenty w `corpus.passages`, manifesty w `corpus.snapshot_manifest` (migracje corpus 0001 i 0003 z meritum-core; 0003 dodaje też `corpus.ingest_attempts`). Pełny tekst czyta tylko system; wyszukiwanie zwraca fragmenty. Zmieniona strona dostaje nowe fragmenty, a stare dostają `retired_at`, więc sprawdzenie z poprzednią wersją widzi to samo co wcześniej. Retencję pełnych tekstów buduje [worker#77](https://github.com/Meritum-HackNation2026/meritum-worker/issues/77) na tym modelu: wyczyści `full_text` po 90 dniach od `fetched_at` (`FULL_TEXT_RETENTION_DAYS` w core) i zostawi wiersz.

| Zmienna | Domyślnie | Opis |
|---|---|---|
| `MERITUM_CORPUS_INGEST` | brak | `enabled` tworzy oba harmonogramy przy starcie workera. Ustawiamy ją tylko tam, gdzie rola może pisać do schematu `corpus` (prd); bez niej harmonogramów nie ma, a uruchomiony ręcznie workflow nic nie robi |
| `MERITUM_CORPUS_PROVIDER`, `MERITUM_CORPUS_DATABASE_URL` | `memory` | gdzie zapisywać dokumenty i migawki (te same ustawienia co kopia EUvsDisinfo) |
| `MERITUM_EMBEDDINGS_*` | `stub` | model embeddingów z meritum-core; korpus i wyszukiwanie muszą używać tego samego |

Testy na prawdziwym PostgreSQL i DBOS, poza CI (baza z `MERITUM_TEST_DATABASE_URL` bez dokumentów i migawek; test ją potem czyści):

```bash
MERITUM_TEST_DATABASE_URL=postgresql://... MERITUM_DBOS_URL=postgresql://... \
  uv run pytest -m integration tests/corpus
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

Sekrety repozytorium (dziś `EUVSDISINFO_MCP_API_KEY`) trafiają do kontenera inną drogą niż plik środowiska. Ich lista jest w jednym miejscu, w tablicy `worker_secrets` w `deploy/deploy.sh`. Krok `Deploy` w jobie `deploy` (`.github/workflows/ci.yml`) podaje każdy z nich jako zmienną środowiska kroku z `${{ secrets.NAZWA }}`, a `deploy.sh` przekazuje go do `docker run` jako `-e NAZWA`, bez wartości. Wartość nie trafia więc do logu, linii poleceń ani pliku na serwerze. Nieustawiony sekret jest pomijany i kontener startuje bez niego. Brak `EUVSDISINFO_MCP_API_KEY` raport gotowości workera ([worker#28](https://github.com/Meritum-HackNation2026/meritum-worker/issues/28)) pokaże jako niedostępnego dostawcę `euvsdisinfo`, a log sondy jako `MissingTokenError`. Nowy sekret dopisz w obu miejscach; test `tests/test_deploy_secrets.py` pilnuje, żeby się zgadzały.

Plik `~/meritum/envs/worker-<env>.env` i rolę w bazie tworzy platforma z [meritum-infra](https://github.com/Meritum-HackNation2026/meritum-infra). Zasady gałęzi jak w backendzie: PR do `develop`, potem `develop` → `main`, bez bezpośrednich pushy.
