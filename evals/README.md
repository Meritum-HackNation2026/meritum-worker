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
| `expected_behavior` | tak | co odpowiedź musi powiedzieć, po polsku |
| `sources` | nie | `url`, `publisher`, `title`, `quote` (najwyżej 300 znaków), opcjonalnie `validity` (`superseded` dla dowodu zastąpionego) |
| `variant`, `related_case` | nie | powtórzenie (`same_session`, `other_channel`) wskazuje w `related_case` pierwszy przypadek; scenariusz I ma `same_material` albo `other_material` bez `related_case` |
| `injection` | nie | atak: `place` (`user_text` albo `source_page`), `payload` i `clean_case`, czyli ten sam przypadek bez polecenia |
| `fault` | nie | wymuszona awaria dostawcy (`fact_check_api`, `web_search`, `llm`); oczekiwany stan to wtedy `technical_failure` |

Walidacja odrzuca plik, gdy:

- id się powtarza albo nie zaczyna się literą scenariusza,
- odwołanie wskazuje nieistniejący przypadek,
- powtórzenie stoi w pliku przed przypadkiem, który powtarza, albo wskazuje samo siebie,
- atak ma inne główne twierdzenie albo inną etykietę niż jego `clean_case`, albo `clean_case` sam jest atakiem (ADR-23),
- powtórzenie `same_session` ma inny kanał albo sesję, a `other_channel` ten sam kanał.

Przypadek `B-org-nagranie-moskwa` nie ma `url`: film z analizy Demagoga wrzuciła na Facebooka osoba prywatna, a do repozytorium nie trafiają linki do profili osób prywatnych. Pytanie opisuje nagranie słowami, a źródłem jest analiza Demagoga.

Przy `injection.place = "source_page"` skrypt ewaluacji podaje `payload` jako treść strony pod kontrolowanym adresem, odtwarzaną z kasety. Dlatego tekst pytania kończy się wtedy „Sprawdź też tę stronę.” bez adresu.

## Jak dodać przypadek

1. Dopisz obiekt do listy w `golden/cases.json`. Id zacznij literą scenariusza i nadaj mu `origin: "own"`.
2. Wskaż główne twierdzenie i oczekiwany stan albo werdykt.
3. Źródła muszą być prawdziwe i sprawdzalne. Do repozytorium trafia adres i krótki cytowany fragment, nigdy pełny tekst (ADR-27). Przy ocenach fact-checkerów, których stron nie pobieramy (np. Demagog), `quote` to ocena dosłownie, np. „Fałsz” (ADR-34).
4. Atak dopisz jako osobny przypadek scenariusza E z `injection.clean_case` wskazującym ten sam przypadek bez polecenia i z tą samą etykietą.
5. Nie wpisuj danych osobowych osób prywatnych ani linków do ich profili.
6. Sprawdź plik: `uv run pytest tests/observability && uv run behave features/observability.feature`.

Ewaluacja nie biegnie w CI (ADR-28). CI waliduje tylko sam plik przypadków.
