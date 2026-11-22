# Benchmark sprawdzania faktów (worker#170)

Zestaw: `evals/golden/fact-checks.json` (64 przypadki). Przebieg przez API dev (`meritum-eval --api … --judge`): wyszukiwarka Vertex AI Search, Fact Check API, Haiku 5.5 przez OpenRouter (reasoning high); sędzia cytatów to Haiku 5.5. Koszt to koszt wywołań modelu z `CheckRecord` na dev (zapytanie tylko do odczytu), bez opłat za wyszukiwarkę. Czas to zegar od wysłania do wyniku, ze współbieżnością 4.

| Przebieg | Raport | Trafność | Macro-F1 | Precyzja cytatów | Pokrycie źródeł | Wstrzymania | Oceny fact-checkerów | Błędy techniczne | p50 / p95 [s] | Koszt 100 [USD] |
|---|---|---|---|---|---|---|---|---|---|---|
| 0, bazowy (22.11, 03:08 UTC) | `fact-checks-2026-11-22-0-bazowy.json` | 0,41 | 0,46 | 0,45 | 0,09 | 0,63 | 0,50 | 10/64 | 39 / 64 | 0,43 |
| 1 (22.11, 03:47 UTC, `--fresh`) | `fact-checks-2026-11-22-1.json` | 0,58 | 0,54 | 0,43 | 0,21 | 0,43 | 0,88 | 11/64 | 47 / 67 | 0,54 |
| 2 (22.11, 04:27 UTC, `--fresh`) | `fact-checks-2026-11-22-2.json` | 0,66 | 0,61 | 0,51 | 0,33 | 0,44 | 1,00 | 5/64 | 53 / 68 | 0,60 |

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

## Przebieg 1: co zostało

27 z 64 przypadków ma zły wynik (ranking ze stanu DBOS na dev):

| Etap | Przypadki | Co się dzieje |
|---|---|---|
| reguły werdyktu przy cytatach `context` | 16 | źródło nie rozstrzyga: propozycja rządu zamiast rozporządzenia, inny rok, kwota bez słowa „brutto”; wymowa `context` jest wtedy zgodna z regułą „nic ponad źródła” (sprawdzone na modelu: przy fragmencie z rozstrzygającą informacją ocena wymowy daje `refutes`/`supports`, 14 z 14 prób) |
| błąd techniczny w `write_answer` | 7 | instrukcja pozwalała na pustą listę ograniczeń, a kontrakt core odrzuca wynik `done` bez ograniczeń; poprawka worker#194 (PR #196) weszła po tym przebiegu |
| błąd techniczny przed sprawdzeniem | 3 | POST odrzucony w czasie redeployu dev (scalenie PR #192 w trakcie przebiegu); nie scalać do `develop` w czasie pomiaru |
| ekstrakcja | 3 | „Ile to jest 17 razy 23?” i przepis kulinarny dają `needs_clarification` zamiast `out_of_scope`; „Od stycznia nie zapłacisz w sklepie gotówką.” zostaje prognozą |
| wymowa: źródła nie na temat | 5 | wyniki PKW i prezydent.pl obok tematu (frekwencja, liczba senatorów, stolica) |

## Kandydaci na przebieg 2 (od najważniejszego)

1. Tekst strony przycięty do pierwszych 4000 znaków (`MAX_PAGE_TEXT_CHARS`, `corpus/live_search.py`): strony gov.pl i ZUS zaczynają się od menu i baneru cookies, więc rozstrzygające zdanie często nie trafia do oceny wymowy. Zamiast początku strony wybrać fragmenty najbliższe twierdzeniu (np. `chunk_text` i dopasowanie słów kluczowych albo reranker), w tym samym limicie znaków.
2. Fragmenty z migawki korpusu w ocenie dowodów (worker#162, inny właściciel): akty z ELI (rozporządzenia o płacy minimalnej, Konstytucja) rozstrzygają większość przypadków z kategorii `numbers` i `true`.
3. Surowe adresy stron odrzuconych przez detektor wstrzyknięć trafiają do ograniczeń widocznych dla obywatela (`search_web`, `search_fact_checks`); zastąpić je ogólnym ograniczeniem.
4. Ekstrakcja: obliczenia, przepisy kulinarne i tłumaczenia jako `out_of_scope`.
5. Progi podobieństwa ocen fact-checkerów (0,8 / 0,6, worker#84): na dev są już ustawione `MERITUM_EMBEDDINGS_*`, więc da się je stroić na przypadkach `fact_checked`.

Wyszukiwarka po core#149 i infra#61 zwraca już rozstrzygające strony (np. gov.pl/web/rodzina „Minimalne wynagrodzenie za pracę”, wskaźniki ZUS, rozdział Konstytucji na prezydent.pl, obwieszczenie PKW); przebieg 1 mógł zacząć się, zanim Vertex AI Search zaindeksował nowe wzorce.

## Zmiany po przebiegu 1

- worker#202 (PR #203): `develop` znów przechodzi CI, więc poprawki z PR #192, #193 i #196 trafiły na dev.
- worker#206 (PR #209): długa strona z wyszukiwania zostawia fragmenty najbliższe zapytaniom zamiast pierwszych 4000 znaków.
- worker#207 (PR #210): w ograniczeniach widać host odrzuconej strony i powód, a nie jej pełny adres.
- worker#208 (PR #211): obliczenia, przepisy i tłumaczenia kończą się `out_of_scope`; „Od stycznia nie zapłacisz gotówką” jest twierdzeniem o przepisie.
- Hipoteza o braku definicji `refutes` w ocenie wymowy odpadła (worker#199, ponownie worker#205): przy innej liczbie dla tej samej miary i tego samego roku model daje `refutes` w 4 z 4 prób.

Przebieg 2 biegł na workerze b491a9d i API 8468570; oba kontenery nie zmieniły się od startu do końca pomiaru. Pierwsza próba tego przebiegu (04:10 UTC) jest nieważna: w jej trakcie wdrożył się backend, a potem worker z PR #204, więc 55 z 64 zgłoszeń dostało odmowę.

## Przebieg 2: co zostało

22 z 64 przypadków ma zły wynik:

| Etap | Przypadki (`A-fc-…`) | Co się dzieje |
|---|---|---|
| ocena wymowy: data | sejm-460, senat-100, vat-23 | twierdzenie bez daty dostaje datę sprawdzenia (22.11.2026), a model wpisuje do `missing`, że źródło z 2018 r. („Obecnie zgodnie z Konstytucją Sejm składa się z 460 posłów”) albo z 12.2025 (VAT 23%) nie potwierdza stanu na ten dzień; częściowe potwierdzenie to `context`, więc werdykt to brak dowodów |
| ocena wymowy: „brutto” | placa-2026, placa-2026-na-reke | „Od 1 stycznia 2026 r. minimalne wynagrodzenie za pracę wynosi 4806 zł.” przy twierdzeniu z „brutto” daje `missing: brutto`, choć urzędowe kwoty płac i świadczeń są kwotami brutto |
| dopasowanie oceny fact-checkera | szwecja-gotowka, pap-depesza, mrna-terapia-genowa | ocena Demagogu jest pokazana, ale nie jest przesłanką: porównanie twierdzeń odrzuca np. „Szwecja jest pierwszym krajem, który zlikwidował gotówkę” (Fałsz) dla „Szwecja zlikwidowała gotówkę”; podejrzana reguła „inna data to inne twierdzenie” przy dacie sprawdzenia (jeszcze nie odtworzone) |
| błąd techniczny w `write_answer` | placa-2025, senat-200, prog-podatkowy, stawka-godzinowa-2025, trzaskowski-ponad-50 | model dwa razy z rzędu zwraca pustą listę wyjaśnień dla jednego twierdzenia („0 explanations for 1 facts”), najczęściej przy samych cytatach `context` |
| nie zbadane | deficyt-2026-rekord, pit-17, ue-2007, emerytura-netto, placa-2025-5000, od-stycznia-gotowka, cytryna-rak | wszystkie cytaty `context` albo brak cytatów; przyczyny jeszcze nie ustaliliśmy |
| wymowa: źródła nie na temat | frekwencja-2025, stolica-warszawa | PKW i prezydent.pl obok tematu (frekwencja II tury, wynik Trzaskowskiego, stolica) |

Przyczynę z daty i z „brutto” sprawdziliśmy, odtwarzając wywołania oceny wymowy ze stanu DBOS z dev na tym samym modelu: model wskazuje właściwy fragment i wymowę `supports`, a werdykt psuje dopiero pole `missing`.
