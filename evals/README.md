# Ewaluacja: golden set

`golden/cases.json` to nasz jawny zestaw deweloperski (golden set). Pokrywa scenariusze A–J z treści zadania i zawiera polski zestaw ataków prompt injection. Progi stroimy tylko na nim; zestaw referencyjny MSZ jest dla nas ukryty (US-OBS-04, F-27).

Plik jury ma ten sam format: lista przypadków w JSON. Model walidacji to `GoldenSet` z `meritum_worker.observability`, a wczytuje go `load_golden_set(path)`.

## Skąd są przypadki

- `origin: "organizer"`: każde przykładowe pytanie z materiału organizatora „wymogi pytań i odpowiedzi (scenariusze A–J)”, z oczekiwanym zachowaniem z tego materiału. Miejsca w nawiasach kwadratowych wypełniliśmy prawdziwymi przykładami, które da się sprawdzić.
- `origin: "own"`: nasze przypadki dla każdego scenariusza, w tym scenariusz C z dowodem zastąpionym (ADR-25) i polski zestaw ataków (scenariusz E).

## Pola przypadku

| Pole | Wymagane | Znaczenie |
| --- | --- | --- |
| `id` | tak | unikalne, zaczyna się literą scenariusza, np. `C-own-placa-zastapiona` |
| `scenario` | tak | `A`–`J` |
| `origin` | tak | `organizer` albo `own` |
| `channel` | tak | `web`, `extension`, `discord`, `sms`, `mcp` (jak `Channel` w meritum-core) |
| `text`, `url`, `image_text` | co najmniej jedno | pytanie, link, tekst i data widoczne na przygotowanym zrzucie (scenariusz F) |
| `session` | nie | etykieta sesji; powtórzenia w tej samej sesji mają tę samą |
| `main_claim` | tak | główne twierdzenie; werdykt przypadku to jego werdykt |
| `expected_status` | tak | `done`, `needs_clarification`, `out_of_scope`, `technical_failure` |
| `expected_verdict` | gdy `done` | werdykt głównego twierdzenia (`confirmed`, `false`, `misleading`, `insufficient_evidence`, `not_verifiable`) |
| `acceptable_verdicts` | nie | inne werdykty, których rzetelny sprawdzający może bronić (np. `misleading` obok `false` przy brakującym „brutto”); liczą się jako poprawne; tylko obok `expected_verdict`, bez jego powtórzenia i bez duplikatów |
| `category` | nie | rodzaj przypadku w benchmarku sprawdzania faktów: `true`, `false`, `partial`, `misleading`, `numbers`, `public_figure`, `opinion`, `fact_checked`, `out_of_scope` |
| `expected_behavior` | tak | co odpowiedź musi powiedzieć, po polsku |
| `sources` | nie | `url`, `publisher`, `title`, `quote` (najwyżej 300 znaków), opcjonalnie `validity` (`superseded` dla dowodu zastąpionego) |
| `variant`, `related_case` | nie | powtórzenie (`same_session`, `other_channel`) wskazuje w `related_case` pierwszy przypadek; scenariusz I ma `same_material` albo `other_material` bez `related_case` |
| `injection` | nie | atak: `place` (`user_text` albo `source_page`), `payload` i `clean_case`, czyli ten sam przypadek bez polecenia |
| `fault` | nie | wymuszona awaria dostawcy (`fact_check_api`, `web_search`, `llm`); oczekiwany stan to wtedy `technical_failure` |
| `checked_at` | nie | dzień, w którym ostatnio sprawdziliśmy źródła przypadku, w formacie ISO, np. `2026-11-22` |

Walidacja odrzuca plik, gdy:

- id się powtarza albo nie zaczyna się literą scenariusza,
- odwołanie wskazuje nieistniejący przypadek,
- powtórzenie stoi w pliku przed przypadkiem, który powtarza, albo wskazuje samo siebie,
- atak ma inne główne twierdzenie albo inną etykietę niż jego `clean_case`, albo `clean_case` sam jest atakiem (ADR-23),
- powtórzenie `same_session` ma inny kanał albo sesję, a `other_channel` ten sam kanał,
- `acceptable_verdicts` stoi bez `expected_verdict`, powtarza go albo wymienia ten sam werdykt dwa razy,
- `checked_at` nie jest datą ISO.

Werdykt z `acceptable_verdicts` liczy się w ocenie przypadku jako `correct`, a w macro-F1 i we wstrzymaniu jako trafienie oczekiwanej klasy. W raporcie przy przypadku zostaje werdykt, który system faktycznie zwrócił. W zapisanym przebiegu (`EvalRun` z kontraktu core) taki przypadek ma w `expected` trafioną alternatywę, bo kontrakt wylicza wynik z `expected` i `predicted`. W pliku CSV kolumna `acceptable_verdicts` trzyma listę w JSON, tak jak `sources`. Id przypadków nie powtarzają się między `golden/cases.json` a `golden/fact-checks.json`.

Przypadek `B-org-nagranie-moskwa` nie ma `url`: film z analizy Demagoga wrzuciła na Facebooka osoba prywatna, a do repozytorium nie trafiają linki do profili osób prywatnych. Pytanie opisuje nagranie słowami, a źródłem jest analiza Demagoga.

Przy `injection.place = "source_page"` skrypt ewaluacji podaje `payload` jako treść strony pod kontrolowanym adresem, odtwarzaną z kasety. Dlatego tekst pytania kończy się wtedy „Sprawdź też tę stronę.” bez adresu.

## Oceny fact-checkerów w `golden/cases.json` (worker#181)

Przypadki `A-fc-…` w `golden/cases.json` to twierdzenia ocenione przez Demagog, AFP Sprawdzam i Fakenews.pl, z `category: "fact_checked"`. Pierwsze źródło to zawsze link do oceny, a jego `quote` to ocena dosłownie (Demagog, Fakenews.pl) albo krótkie zdanie z tekstu oceny (AFP pokazuje ocenę tylko w danych ClaimReview strony). Kolejne źródła to dokumenty, na które wskazuje ocena (Eurostat, GUS, ZUS, gov.pl, NASA, WHO, Komisja Europejska). `checked_at` to dzień, w którym otworzyliśmy każdą stronę i znaleźliśmy na niej ocenę i cytat.

Ocenę fact-checkera tłumaczymy na nasz werdykt tak:

| Ocena | `expected_verdict` | typowe `acceptable_verdicts` |
|---|---|---|
| Prawda | `confirmed` | brak |
| Fałsz | `false` | `misleading`, gdy prawdziwe nagranie pokazano w złym kontekście |
| Manipulacja, Mylące, Brak kontekstu | `misleading` | `false`, gdy twierdzenie po odjęciu kontekstu jest po prostu nieprawdziwe |
| Częściowa prawda | `misleading` | `insufficient_evidence` |
| Nieweryfikowalne | `not_verifiable` | `insufficient_evidence` |

## Benchmark sprawdzania faktów (`golden/fact-checks.json`)

64 przypadki po polsku do pomiaru jakości werdyktów (worker#170): twierdzenia prawdziwe i fałszywe, częściowo prawdziwe (brakujące „brutto”, „miesięcznie”), wprowadzające w błąd kontekstem, liczby i daty (płaca minimalna, PIT, VAT, deficyt, inflacja), wypowiedzi i wyniki osób publicznych, opinie i prognozy, oceny Demagogu oraz prośby poza zakresem. Każdy cytat z dokumentu urzędowego (ELI Kancelarii Sejmu, komunikat GUS, strona NATO) sprawdziliśmy skryptem: występuje dosłownie na stronie albo w PDF. Przy ocenach Demagogu `quote` to ocena, a adres prowadzi do analizy. Przypadki bez `sources` to wiedza powszechna (stolica, wejście do UE) albo twierdzenia, których źródła nie ma w katalogu; benchmark sprawdza, czy system sam je znajdzie. Przebieg i raporty: `evals/reports/fact-checks.md`.

## Jak dodać przypadek

1. Dopisz obiekt do listy w `golden/cases.json`. Id zacznij literą scenariusza i nadaj mu `origin: "own"`.
2. Wskaż główne twierdzenie i oczekiwany stan albo werdykt.
3. Źródła muszą być prawdziwe i sprawdzalne. Do repozytorium trafia adres i krótki cytowany fragment, nigdy pełny tekst (ADR-27). Przy ocenach fact-checkerów, których stron nie pobieramy (np. Demagog), `quote` to ocena dosłownie, np. „Fałsz” (ADR-34).
4. Atak dopisz jako osobny przypadek scenariusza E z `injection.clean_case` wskazującym ten sam przypadek bez polecenia i z tą samą etykietą.
5. Nie wpisuj danych osobowych osób prywatnych ani linków do ich profili.
6. Sprawdź plik: `uv run pytest tests/observability && uv run behave features/observability.feature`.

Przebieg uruchamia `uv run meritum-eval` (README repozytorium, sekcja „Ewaluacja”). Ewaluacja nie biegnie w CI (ADR-28). CI waliduje tylko sam plik przypadków i testuje mierniki.
