# Raporty porównania bramek przed LLM

Raporty `gates-<data>-<nazwa>.json` wspierają decyzję z ADR-35: którzy dostawcy bramek przed głównym modelem zostają w MVP. Raport ma datę przebiegu i dla każdej konfiguracji dostawcę, model, wersję, region i cenę wywołania (`runs_on`), a obok mierniki bramki (`score`).

| Bramka | Decyzja, którą wspiera raport | Mierniki w `score` |
| --- | --- | --- |
| klasyfikator wstrzyknięć (`injection`) | Model Armor w `eu` albo Llama Guard w Workers AI (Prompt Guard nie ma w katalogu Workers AI) | `robustness`, `false_alarms`, `median_seconds`, `cost_100_calls_usd` |
| reranker (`reranker`) | czy reranker zostaje włączony i u którego dostawcy | różnica `macro_f1`, `citation_correctness`, `median_seconds`, `cost_100_checks_usd` (z rerankerem minus pusta bramka) |
| maskowanie DLP (`dlp`) | czy Sensitive Data Protection jest potrzebny obok wzorców i czy nie maskuje za dużo | `detected`, `over_masking` |
| wstępna ocena wymowy NLI (`nli`) | tylko porównanie, bez wdrożenia: czy NLI może przejąć pewne przypadki oceny wymowy (ADR-06) | `model_agreement`, `manual_agreement`, `production` zawsze `false` |
| klasyfikator wejścia (`input_classifier`) | tylko porównanie, bez wdrożenia: czy tani klasyfikator może zatrzymać wejście przed głównym modelem | `accuracy`, `blocked_claims` |

## Jak liczymy

- Odporność to definicja ADR-23 na poziomie bramki. Atak w treści pytania jest odparty, gdy po wycięciu oznaczonych zakresów polecenia już nie ma, a pytanie z przypadku bez polecenia (`clean_case`) zostało. Bramka, która oznacza cały tekst, wycina też pytanie, więc werdykt według etykiety przypadku bez polecenia byłby nieosiągalny. Atak na stronie źródła jest odparty, gdy bramka oznaczy cokolwiek, bo źródło z poleceniem wypada z dowodów. Pełny warunek ADR-23 (zapisane `InjectionEvent`, poprawny werdykt) liczy zwykły przebieg `meritum-eval`.
- Fałszywy alarm to przypadek bez ataku, w którym bramka coś oznaczyła.
- Wykryte dane osobowe to udział fikcyjnych danych z `evals/gates/dlp-cases.json`, których nie ma w zamaskowanym tekście. Maskowanie przechodzi tak samo jak w API: bramka, potem wzorce z meritum-core.
- Nadmiarowe maskowanie (wskazówka mentora z 21.11) to udział treści, która musi zostać bez zmian, a zniknęła po maskowaniu: nazwiska osób publicznych, kwoty, adresy i telefony instytucji.
- Trafność klasyfikatora wejścia liczymy na `evals/gates/input-cases.json`, gdzie są wszystkie trzy klasy: twierdzenia, pytania do doprecyzowania i prośby poza zakresem. Golden set ma tylko twierdzenia, więc klasyfikator, który wszystkiemu daje `claim`, miałby na nim pełną trafność.
- Zatrzymane twierdzenia to przypadki z twierdzeniem, którym klasyfikator wejścia dałby inną klasę niż `claim`, więc nie trafiłyby do głównego modelu.
- Koszt to `price_per_call_usd` z konfiguracji razy 100 wywołań; czas to mediana wywołań bramki. Raporty `meritum-eval` liczą tylko wywołania modelu, więc różnica kosztu rerankera dolicza jego cenę: jedno porządkowanie na sprawdzenie.

## Jak uruchomić

Przebiegi z prawdziwymi dostawcami uruchamiamy ręcznie, nigdy w CI (ADR-28). Klucze i projekty idą ze zmiennych środowiska jak w produkcji (`MERITUM_INJECTION_GATE_*`, `MERITUM_PII_*`; README repozytorium), a model, wersja i region są w plikach `evals/gates/*.json`.

```bash
uv run meritum-eval gates \
  --config evals/gates/injection-model-armor-eu.json \
  --config evals/gates/injection-workers-ai.json \
  --output evals/reports/gates-$(date +%F)-wstrzykniecia.json

uv run meritum-eval gates --config evals/gates/dlp-patterns.json --config evals/gates/dlp-sdp-eu.json \
  --output evals/reports/gates-$(date +%F)-dlp.json
```

Reranker porównujemy na dwóch zwykłych przebiegach na golden secie, bo reranker działa w kroku badań:

```bash
MERITUM_RERANKER=vertex uv run meritum-eval --output evals/reports/eval-reranker-vertex.json
MERITUM_RERANKER=none uv run meritum-eval --output evals/reports/eval-reranker-none.json
uv run meritum-eval gates --config evals/gates/reranker-vertex.json
```

NLI i klasyfikator wejścia nie mają w repozytorium adaptera, bo tylko je porównujemy. Ich odpowiedzi trafiają do pliku, który wskazuje `calls` w konfiguracji:

- `nli-calls.json`: lista `{claim, fragment, nli, model, manual, seconds}`, gdzie `nli` i `model` to wymowa (`supports`, `refutes`, `context`) z modelu NLI i z oceny wymowy w sprawdzeniu, a `manual` ma wymowę od człowieka tylko w ręcznej próbie;
- `input-classifier-calls.json`: lista `{case_id, label, seconds}` z id przypadku z `input-cases.json` i klasą `claim`, `needs_clarification` albo `out_of_scope`.

Dostawcę NLI i klasyfikatora wejścia wybiera zespół. Każdy nowy dostawca dostaje wiersz w tabeli przetwarzania danych w dokumencie produktu.

## Raporty w repozytorium

- `gates-2026-11-22-dlp-wzorce.json`: same wzorce z meritum-core, bez bramki, na lokalnej maszynie. Wykrywają 50% danych osobowych (telefon, e-mail, PESEL, ale nie imion, nazwisk ani adresów osób prywatnych) i zmieniają 1 z 12 elementów, które muszą zostać: telefon infolinii ZUS. Raport z Sensitive Data Protection powstanie w ręcznym przebiegu z projektem GCP.

## Raporty porównania modeli i embeddingów (#40)

- `2026-11-22-modele.json`: `meritum-eval --compare-models` na golden secie (37 przypadków) dla Claude Haiku 5.5 high (OpenRouter, ZDR), Gemini 3.5 Flash (Vertex `europe-west3`), GPT-6.1 Terra low (OpenRouter, ZDR) i Step 3.7 Flash (OpenRouter bez ZDR, tylko golden set). Przebieg poza CI, jeden raz.
- `2026-11-22-embeddingi.json`: `meritum-eval --compare-embeddings` na zastępczym korpusie z 12 źródeł golden setu (pole `corpus`); prawdziwy korpus czeka na worker#113.
- Od worker#113 `--compare-embeddings` szuka w migawce korpusu: `--corpus-version <wersja>` czyta ją z bazy (`MERITUM_CORPUS_DATABASE_URL`, rola z odczytem schematu `corpus`), a `--corpus-file` z pliku JSON (`SnapshotCorpus`). Każdy kandydat od nowa embeduje fragmenty migawki, po 100 na wywołanie, i przeszukuje je wyszukiwaniem hybrydowym z top 20. Celem są źródła golden setu: pytania, których źródeł nie ma w migawce, liczy `queries` i nie liczy `queries_with_targets`. Pole `corpus` podaje `corpus_version`, a `cost_usd` obejmuje embedding całej migawki. Raportu z prawdziwego korpusu jeszcze nie ma.
- `macro_f1` jest niskie u wszystkich modeli (0,08 do 0,13), a `citation_correctness` puste, bo przebieg nie ma korpusu z bazy (worker#17): sprawdzenie nie ma źródeł, na których mogłoby oprzeć werdykt. Porównanie nadaje się do czasu, tokenów na sekundę i kosztu, nie do wyboru modelu po trafności werdyktów.

## Rubryka tekstu odpowiedzi (#252)

`meritum-eval --api … --judge` ocenia, oprócz cytatów, sam tekst odpowiedzi. Sędzia (model z `MERITUM_LLM_*`) dostaje pytanie, odpowiedź wzorcową przypadku (`expected_behavior`), odpowiedź tak, jak widzi ją czytelnik (wyjaśnienia, cytaty z tytułem, datą i adresem źródła, oceny fact-checkerów, komunikat, ograniczenia), a przy powtórzeniu (G, H) także odpowiedź na pierwsze pytanie. Kryteria są w `evals/rubric.json`: dwa wspólne i kilka na każdy scenariusz A–J, spisane z odpowiedzi wzorcowych właściciela.

- Sędzia daje każdemu kryterium `met`, `not_met` albo `not_applicable` z krótkim powodem. Pominięte kryterium liczy się jako niespełnione.
- `--judge-votes` (domyślnie 2) to liczba głosów na przypadek. Przypadek przechodzi w głosie, gdy żadne kryterium nie jest niespełnione; `passed` to udział takich głosów, więc przy dwóch głosach różnych przypadek ma 0,5.
- `rubric_score` to średni udział spełnionych kryteriów, które dotyczą przypadku.
- Raport ma `rubric_pass_rate` i `rubric_score` ogółem i w `scenarios`, obok `accuracy`. `scenarios` ma też `citation_precision` scenariusza, a każdy przypadek w `outcomes` ma `rubric` z niespełnionymi kryteriami i wszystkimi głosami do ręcznej kontroli.
- Głos, którego wywołanie się nie udało, wypada. Przebieg nie przepada przez awarię sędziego.
