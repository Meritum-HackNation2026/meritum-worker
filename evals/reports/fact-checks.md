# Benchmark sprawdzania faktów (worker#170)

Zestaw: `evals/golden/fact-checks.json` (64 przypadki). Przebieg przez API dev (`meritum-eval --api … --judge`): wyszukiwarka Vertex AI Search, Fact Check API, Haiku 5.5 przez OpenRouter (reasoning high); sędzia cytatów to Haiku 5.5. Koszt to koszt wywołań modelu z `CheckRecord` na dev (zapytanie tylko do odczytu), bez opłat za wyszukiwarkę. Czas to zegar od wysłania do wyniku, ze współbieżnością 4.

| Przebieg | Raport | Trafność | Macro-F1 | Precyzja cytatów | Pokrycie źródeł | Wstrzymania | Oceny fact-checkerów | Błędy techniczne | p50 / p95 [s] | Koszt 100 [USD] |
|---|---|---|---|---|---|---|---|---|---|---|
| 0, bazowy (22.11, 03:08 UTC) | `fact-checks-2026-11-22-0-bazowy.json` | 0,41 | 0,46 | 0,45 | 0,09 | 0,63 | 0,50 | 10/64 | 39 / 64 | 0,43 |

## Przebieg 0: gdzie gubią się werdykty

38 z 64 przypadków ma zły wynik. Przyczynę każdego ustaliliśmy ze stanu DBOS sprawdzenia na dev:

| Etap | Przypadki | Co się dzieje |
|---|---|---|
| reguły werdyktu i oceny fact-checkerów | 19 | Oceny Demagogu przychodzą jako `Fałsz.` albo `Fałsz. <uzasadnienie>` (30 z ~90 ocen) i nie trafiają do tabeli wymów, więc nie są przesłanką; cytaty z KPRM o płacy minimalnej mają wymowę `context` (to propozycja rządu, a rozporządzenia ELI wyszukiwarka nie znalazła) |
| ekstrakcja twierdzeń | 10 | pytania „Czy X?” kończą się `needs_clarification` („Claim extraction found no claims”); prośby poza zakresem („Ile to jest 17 razy 23?”) też; część tekstów z testu QA przyszła z pamięci podręcznej API (2 h) |
| błąd techniczny w `write_answer` | 7 | wynik `technical_failure` bez wyjątku; lokalnie na tych samych stanach i z tym samym modelem 12/12 prób kończy się `done`, a logi sprzed redeployu 03:18 zniknęły |
| błąd techniczny w `assess_evidence` | 3 | ocena fact-checkera dłuższa niż 120 znaków rzuca `ValidationError` z `ClaimReviewContext.rating` |
| wymowa: wszystkie źródła nie na temat | 4 | wyszukiwarka zwraca strony PKW i EUR-Lex obok tematu (np. frekwencja II tury, liczba senatorów) |
| wyszukiwanie: nic | 2 | brak stron z katalogu dla Konstytucji i kwoty zmniejszającej podatek |

## Zmiany po przebiegu 0

- worker#177 (PR #179): długa ocena fact-checkera jest skracana na granicy słowa i nie wywraca sprawdzenia.
- core#154 (PR #155): ocena z kropką albo z uzasadnieniem trafia do tabeli wymów.
- core#149 (PR #151) i infra#61 (PR #62, apply 22.11): katalog i Vertex AI Search obejmują gov.pl/web/rodzina, gov.pl/web/finanse, podatki.gov.pl, zus.pl, stat.gov.pl i prezydent.pl; wzorce gov.pl/web wspólne, 41 z 50.
- worker#187 (PR #189): pytanie tak/nie niesie twierdzenie, o które pyta.
- worker#190 (PR #191): worker na core z katalogiem i regułą ocen.
