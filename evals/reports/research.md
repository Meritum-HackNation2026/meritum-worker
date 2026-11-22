# Techniki podnoszące trafność werdyktów: przegląd i eksperymenty (worker#170)

Stan na 22.11.2026. Punkt wyjścia to przebiegi 0–2 z `fact-checks.md` (trafność 0,41 → 0,66, macro-F1 0,46 → 0,61, precyzja cytatów 0,51, pokrycie źródeł 0,33). Przebiegi 0–2 biegły bez korpusu; od 04:00 UTC dev czyta migawkę korpusu, więc eksperymenty porównujemy z nowym pomiarem bazowym (przebieg 3).

## Progi przyjęcia zmiany

Zmiana zostaje, gdy na pełnym zestawie:

- trafność albo macro-F1 rośnie o co najmniej 2 p.p. (64 przypadki: 1 przypadek to 1,6 p.p., więc mniejsza różnica to szum),
- precyzja cytatów nie spada o więcej niż 3 p.p.,
- p50 czasu nie rośnie o więcej niż 15%, a koszt 100 sprawdzeń o więcej niż 25%,
- nie przybywa błędów technicznych.

Zmiany po wyszukiwaniu (ocena wymowy, dopasowanie ocen, odpowiedź) sprawdzamy najpierw na powtórce: stan sprawdzeń z dev (`dbos.operation_outputs`, tylko odczyt) po krokach wyszukiwania idzie lokalnie przez `assess_evidence` → `verify_citations` → `write_answer` na tym samym modelu (Haiku 5.5, OpenRouter). Wyszukiwanie jest wtedy zamrożone, więc różnica pochodzi tylko ze zmiany. Zmiany w wyszukiwaniu mierzymy pełnym przebiegiem przez API dev.

## Co mówi literatura

| Obszar | Wniosek | Źródło |
|---|---|---|
| Kształt potoku | Najlepsze systemy AVeriTeC 2024 to potoki LLM: interpretacja twierdzenia, pytania weryfikujące, wyszukiwanie per pytanie, werdykt z uzasadnieniem. InFact (GPT-4o) wygrał z 63%, baseline 11%. Wszystkie systemy są wyraźnie słabsze na „sprzeczne dowody” i „za mało dowodów” niż na potwierdzeniu i obaleniu. | [AVeriTeC 2024](https://arxiv.org/abs/2410.23850), [InFact](https://aclanthology.org/2024.fever-1.12.pdf) |
| Prosty RAG | AIC CTU: jeden krok wyszukiwania i jedno wywołanie LLM z całym kontekstem dało 50% (3. miejsce 2024) i wygraną w edycji 2025 z limitem minuty na twierdzenie. Prosty potok z dobrym wyszukiwaniem bije złożone łańcuchy. | [AIC CTU](https://arxiv.org/abs/2410.11446), [AVeriTeC 2025](https://aclanthology.org/2025.fever-1.15) |
| Zapytania | HerO (2. miejsce 2024, modele otwarte): hipotetyczne dokumenty fact-checkingowe (HyDE-FC) jako rozszerzenie zapytania, potem BM25 i wyszukiwanie gęste. HerO 2 dodał streszczanie stron do bloków dowodowych. Ostrzeżenie: część zysku HyDE to wiedza modelu, nie wyszukiwanie. | [HerO](https://arxiv.org/abs/2410.12377), [HerO 2](https://arxiv.org/abs/2507.11004), [HyDE czy wyciek wiedzy](https://arxiv.org/abs/2504.14175) |
| Dekompozycja twierdzeń | Nie pomaga konsekwentnie: zysk zależy od dekompozytora i siły weryfikatora, a rozbite twierdzenia potrafią zgubić sens oryginału. VeriScore: wyciągać tylko twierdzenia weryfikowalne, z kontekstem zdania. | [Decomposition Dilemmas](https://arxiv.org/abs/2411.02400), [VeriScore](https://arxiv.org/abs/2406.19276), [DecMetrics](https://arxiv.org/abs/2509.04483) |
| Liczby | QuanTemp: twierdzenia liczbowe są najtrudniejsze (najlepszy baseline macro-F1 58), pomaga dekompozycja na pytania o wartość, jednostkę i okres. CheckThat! 2025 ma osobne zadanie na liczby i daty. | [QuanTemp](https://arxiv.org/abs/2403.17169), [QuanTemp++](https://arxiv.org/abs/2510.22055), [CheckThat! 2025](https://arxiv.org/abs/2503.14828) |
| Wyszukiwanie hybrydowe i reranking | Contextual Retrieval: kontekstowe embeddingi −35% chybień w top-20, z kontekstowym BM25 −49%, z rerankerem −67%. PIRB (polski): hybryda z BM25/SPLADE dodaje ok. 1 pkt NDCG@10 do najlepszego modelu gęstego; polskie rerankery biją modele wielokrotnie większe. | [Contextual Retrieval](https://www.anthropic.com/news/contextual-retrieval), [PIRB](https://arxiv.org/abs/2402.13350), [polskie rerankery](https://arxiv.org/abs/2402.14318) |
| Wystarczalność dowodów i wstrzymanie | „Sufficient context”: prompt ocenia wystarczalność kontekstu z trafnością ≥93%; dodatkowy, niewystarczający kontekst zwiększa pewność modelu i halucynacje zamiast wstrzymań. Wstrzymanie warto opierać na sygnale wystarczalności, nie na samej pewności modelu. | [Sufficient Context](https://arxiv.org/abs/2411.06037), [blog Google](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/) |
| NLI czy LLM | MiniCheck dorównuje GPT-4 na prostym ugruntowaniu przy ułamku kosztu, ale odstaje na przykładach wymagających wnioskowania wieloetapowego. Dla polskiego nie ma gotowego odpowiednika. | [MiniCheck](https://arxiv.org/abs/2404.10774) |
| Czas | Ograniczenie dowodów do opublikowanych przed twierdzeniem obniża wynik AVeriTeC z 0,844 do 0,782, ale większość różnicy to brak dowodów sprzed twierdzenia, a nie „wiedza z przyszłości” (górna granica 3,1 p.p.). | [No Hindsight](https://arxiv.org/abs/2610.04888), [Temporal Fact Verification](https://arxiv.org/abs/2407.15291) |
| Oceny fact-checkerów | SemEval-2025 Task 7 (MultiClaim, 39 języków): dostrojone wielojęzyczne embeddingi dają success@10 0,92 w jednym języku i 0,85 między językami; tłumaczenie na angielski pomaga, TF-IDF pozostaje mocnym tanim baseline'em. | [Word2winners](https://arxiv.org/abs/2503.09011), [przegląd zadania](https://arxiv.org/abs/2505.10740) |
| Ekstrakcja stron | trafilatura w trybie domyślnym ma najlepsze F1 (0,909); tryb precyzji traci pokrycie (0,874), oba tryby dziwnie traktują tabele. | [ewaluacja trafilatura](https://trafilatura.readthedocs.io/en/latest/evaluation.html), [porównanie Marin](https://wandb.ai/marin-community/marin/reports/246-Web-Extraction-Method-Comparison--Vmlldzo5OTg4MTAw) |
| Ocena etapami | Factcheck-Bench i OpenFactCheck mierzą osobno ekstrakcję, wyszukiwanie i weryfikację; najlepsze gotowe systemy mają F1 0,63 na wykrywaniu fałszu. Ocena całego potoku jedną liczbą ukrywa, który etap psuje wynik. | [Factcheck-Bench](https://arxiv.org/abs/2311.09000), [OpenFactCheck](https://arxiv.org/abs/2405.05583), [Loki](https://arxiv.org/abs/2410.01794) |

## Co Meritum już ma

Ekstrakcja twierdzeń z zapytaniami po polsku i angielsku (1–3 na twierdzenie), wyszukiwanie hybrydowe w migawce korpusu z bramką rerankera, wyszukiwanie na żywo w domenach katalogu, Fact Check API z progami podobieństwa embeddingów, wybór fragmentów długiej strony po wspólnych słowach (worker#206), ocena wymowy osobnym wywołaniem na parę twierdzenie–źródło (ADR-05/06), werdykt regułą z cytatów w meritum-core.

## Ranking pomysłów

Zysk to szacunek zmiany trafności na 64 przypadkach, oparty na rankingu przyczyn z przebiegu 2.

| # | Pomysł | Skąd | Oczekiwany zysk | Koszt i czas | Nakład | Ryzyko |
|---|---|---|---|---|---|---|
| 1 | Twierdzenie bez daty to twierdzenie o teraźniejszości; źródło obowiązujące je potwierdza. „Brutto” przy urzędowej kwocie nie jest brakiem (worker#218) | przebieg 2: 5 przypadków; „za mało dowodów” to najsłabsza klasa także w AVeriTeC | +5 do +8 p.p. | bez zmian | S | nieaktualne źródło potwierdzi stan, który się zmienił; ogranicza to ważność wpisu katalogu |
| 2 | Dopasowanie oceny fact-checkera: twierdzenie ocenione może być mocniejszą albo dokładniejszą wersją naszego; starsza ocena pasuje do twierdzenia bez daty (worker#218) | przebieg 2: 3 przypadki; MultiClaim | +3 do +5 p.p. | bez zmian | S | ocena innego twierdzenia stanie się przesłanką; pilnują tego progi podobieństwa |
| 3 | `write_answer`: pusta lista wyjaśnień nie kończy sprawdzenia błędem technicznym | przebieg 2: 5 przypadków | +5 do +8 p.p. | bez zmian | S | słabsze wyjaśnienie zamiast błędu |
| 4 | Fragmenty z migawki korpusu jako dowody w ocenie wymowy (worker#162, inny właściciel) | Contextual Retrieval, PIRB; akty z ELI rozstrzygają liczby i przepisy | +5 do +10 p.p., pokrycie źródeł w górę | +20–40% wywołań oceny wymowy | M | więcej cytatów `context`, dłuższy czas |
| 5 | Druga runda wyszukiwania, gdy żadne źródło nie rozstrzyga: model dostaje twierdzenie i tytuły znalezionych stron, pisze pytania weryfikujące | InFact (pytania i iteracyjne wyszukiwanie), HerO | +3 do +6 p.p. w przypadkach „źródła obok tematu” | +1 wywołanie modelu i wyszukiwarki w ok. 40% sprawdzeń, +10–15 s | M | czas p95; limit kroku |
| 6 | Wspólna ocena wystarczalności: gdy wszystkie cytaty to `context`, jedno wywołanie widzi twierdzenie i wszystkie zacytowane fragmenty i mówi, czy razem rozstrzygają | Sufficient Context; AIC CTU (jeden kontekst, jedno wywołanie) | +3 do +5 p.p. | +1 wywołanie w ok. 40% sprawdzeń | M | łamie izolację pary z ADR-05/06 (fragment ze wstrzykniętym poleceniem zobaczyłby inne źródła); wymaga decyzji |
| 7 | Reranker modelem krzyżowym na fragmentach stron z wyszukiwania na żywo zamiast wspólnych słów | Contextual Retrieval (−67% chybień z rerankerem), polskie rerankery | +2 do +4 p.p. | +1 wywołanie rerankera na stronę | M | nowy dostawca na ścieżce krytycznej |
| 8 | Samospójność oceny wymowy: 3 wywołania i głos większości dla par, w których model waha się między `supports` a `context` | SAFE, praktyka LLM-as-judge | +1 do +3 p.p., mniejszy rozrzut między przebiegami | koszt oceny wymowy ×2–3 | S | koszt; próg 25% |
| 9 | Dekompozycja twierdzeń liczbowych na wartość, jednostkę i okres | QuanTemp | +1 do +3 p.p. w kategorii liczb | +1 wywołanie na twierdzenie | M | Decomposition Dilemmas: bywa, że szkodzi |
| 10 | HyDE-FC: hipotetyczny akapit fact-checkera jako zapytanie do korpusu | HerO | +1 do +3 p.p. pokrycia | +1 wywołanie | S | wyciek wiedzy modelu do zapytania |
| 11 | Ekstrakcja: tabele i PDF (ELI) w tekście strony, tryb `favor_recall` | ewaluacja trafilatura | zależy od udziału tabel; do zmierzenia | bez zmian | M | szum z menu wraca do tekstu |
| 12 | NLI zamiast LLM w ocenie wymowy | MiniCheck | 0 (tylko koszt) | −koszt | L | brak polskiego modelu; ADR-06 już to odkłada |

Kolejność eksperymentów: 1+2 (jedno zgłoszenie), 3, pomiar 4 po scaleniu worker#162, potem 5, 8 i 6 na powtórce. Pomysły 9–12 zostają na liście bez eksperymentu, dopóki ranking przyczyn nie wskaże ich etapu.

## Wyniki eksperymentów

Tabela rośnie po każdej partii.

Powtórka to 64 sprawdzenia z zamrożonym wyszukiwaniem. Do #228 włącznie stan pochodzi z przebiegu 2 albo 3, od #234 z przebiegu 5. Koszt 100 sprawdzeń na powtórce obejmuje tylko kroki po wyszukiwaniu; API dev kosztu nie zwraca.

| Eksperyment | Zgłoszenie / PR | Powtórka | Pełny przebieg na dev | Decyzja |
|---|---|---|---|---|
| 1+2: twierdzenie bez daty to teraźniejszość, kwota urzędowa jest brutto, cytat obejmuje dalszą część zdania | worker#218 / #219 | 52/64 wobec 42/64 (stan przebiegu 2) | przebieg 4: trafność 0,73, macro-F1 0,63, precyzja 0,68 | scalone |
| 3: werdykt w instrukcji `write_answer`, nie w danych (osłona wycinała linię `verdict:`) | worker#221 / #224 | błędy techniczne 5 → 0 | przebieg 5: trafność 0,83, macro-F1 0,82, precyzja 0,58, p50 51 s | scalone |
| Dopasowanie oceny fact-checkera do twierdzenia ogólniejszego albo z dodatkowym szczegółem | worker#227 / #228 | „Szwecja” i depesza PAP pasują 3/3 zamiast 1/3, bez nowych fałszywych dopasowań na 59 parach | w przebiegach 6b i 7 | scalone |
| 4: fragmenty korpusu w ocenie wymowy | worker#162 (inny właściciel) | nie mierzone: 1530 z 2167 dokumentów migawki to same tytuły aktów | | czeka na pełne teksty aktów (worker#235) |
| Zapytania nazywające rodzaj dokumentu (pomysł pokrewny 5 i 10) | bez zgłoszenia | 49/64 wobec 50/64 (powtórka z wyszukiwaniem na żywo) | | odrzucone: bez zysku |
| Cytat na temat i zrozumiały samodzielnie; propozycja i prognoza to kontekst | worker#233 / #234 | trafność 52, 53, 54/64 (develop: 54), precyzja 0,78, 0,81, 0,77 (develop: 0,61), koszt 0,32 wobec 0,30 | przebieg 7: 0,80 / 0,81 / 0,84 / 53 s; przebieg 7b: 0,83 / 0,82 / 0,83 / 50 s | scalone, zostaje |
| Dodatkowe wywołanie, które sprawdza cytat rozstrzygający i zamienia odrzucony na kontekst | bez zgłoszenia | 50/64, macro-F1 0,65, precyzja 0,84 | | odrzucone: traci 4 poprawne werdykty |
| Najwyżej 1 cytat kontekstowy przy twierdzeniu z cytatem rozstrzygającym | bez zgłoszenia | 52/64, precyzja 0,79 | | odrzucone: szum |
| V6: osobna definicja „obala” w instrukcji (fragment sam pokazuje sprzeczność, zdanie z rokiem albo ze słowem brutto) | bez zgłoszenia | 51 i 53/64, precyzja 0,77 i 0,75 | | odrzucone: bez zysku; odrzucone „obala” przechodzą w kontekst, który sędzia też odrzuca |
| V7: pole `fragment_kind` w odpowiedzi oceny wymowy; propozycja albo prognoza staje się kontekstem w kodzie, nagłówek i wiersz tabeli odpadają | bez zgłoszenia | 53, 50, 52/64, precyzja 0,79, 0,76, 0,77 | | odrzucone: bez zysku |
| Klient ewaluacji ponawia żądania po błędzie transportu i po 502/503/504 | worker#242 / #243 | | przebiegi 7 i 7b bez błędów technicznych | do scalenia |
| Sędzia cytatów widzi tytuł, datę i adres źródła i zna regułę brutto; raport podaje `macro_f1_strict` | worker#247 | zgodność z sędzią GPT: kappa 0,20 → 0,52, „obala” 0,31 → 0,63 | cytaty przebiegu 7 ocenione ponownie: 0,94 (stary sędzia 0,84) | w PR |

### Pełne przebiegi po zmianach

| Przebieg | Kod | Trafność | Macro-F1 | Macro-F1 ścisłe | Precyzja cytatów | Pokrycie źródeł | Wstrzymania | Błędy techniczne | p50 [s] |
|---|---|---|---|---|---|---|---|---|---|
| 3 | develop z korpusem | 0,73 | 0,73 | | 0,60 | 0,30 | 0,40 | 0 | 53 |
| 4 | + #219 | 0,73 | 0,63 | | 0,68 | 0,28 | 0,39 | 1 | 50 |
| 5 | + #224 | 0,83 (53/64) | 0,82 | 0,62 | 0,58 | 0,35 | 0,28 | 0 | 51 |
| 6b | + #228; API zrestartowane w trakcie | 0,58 | 0,46 | 0,31 | 0,62 | 0,14 | 0,27 | 16 (wszystkie po stronie klienta) | 50 |
| 6b bez 16 błędów infrastruktury | 48 przypadków | 0,77 (37/48) | 0,77 | 0,56 | | | | 0 | |
| 7 | + #234 | 0,80 (51/64) | 0,81 | 0,64 | 0,84 | 0,26 | 0,33 | 0 | 53 |
| 7b | + #234, powtórzenie (i podbicie meritum-core z #245) | 0,83 (53/64) | 0,82 | 0,65 | 0,83 | 0,28 | 0,30 | 0 | 50 |

Przebieg 6 jest nieważny (deploy API w trakcie). „Macro-F1 ścisłe” liczy etykiety, które potok naprawdę zwrócił; zwykłe macro-F1 zamienia dozwoloną alternatywę na etykietę oczekiwaną i daje klasie `misleading` F1 = 1,0, chociaż potok nigdy tak nie odpowiada. Pokrycie źródeł porównuje tylko hosty: na poziomie aktu wynosi 0/33.

Przebieg 7 wypadł 2 przypadki poniżej przebiegu 5, więc powtórzyłem go jako 7b: 53/64, tyle samo co przed #234. Na 48 przypadkach, które ukończył przebieg 6b, kolejne przebiegi mają 39 (5), 37 (6b), 36 (7) i 38 (7b) poprawnych. #234 nie kosztuje więc mierzalnie trafności, a precyzja cytatów rośnie z 0,58 do 0,83–0,84 (ten sam, stary sędzia). Pokrycie źródeł spada z 0,35 do 0,26–0,28, bo ubyło luźnych cytatów kontekstowych z hostów złotych źródeł. W czasie przebiegów 7 i 7b żaden kontener się nie restartował (znaczniki obrazów i czas startu sprawdzone przed i po).

### Ile jest szumu

- Trzy powtórki tego samego kodu (develop z #234) na tym samym zamrożonym wyszukiwaniu dają 52, 53 i 54 poprawne przypadki, macro-F1 0,77–0,83 i precyzję cytatów 0,77–0,81. Najmniejsza różnica, którą powtórka pokaże, to około 2 przypadków trafności i 4 p.p. precyzji.
- Pełne przebiegi różnią się bardziej, bo wyszukiwarka zwraca inne strony. Przebiegi 5 i 7 mają 12 przypadków o innej poprawności (5 na plus, 7 na minus). Różnicę do 3 przypadków traktujemy jako szum.
- Test McNemara na 64 przypadkach wymaga co najmniej 6 naprawionych przypadków przy 0 zepsutych (p = 0,031). Żadna pojedyncza zmiana po #219 nie jest istotna statystycznie; przyjmujemy je na podstawie mechanizmu i braku regresji.
- Próg „+2 p.p. trafności” z początku tego dokumentu leży poniżej szumu pełnego przebiegu. Zmiany po wyszukiwaniu oceniamy na co najmniej 3 powtórkach, a przedział precyzji cytatów liczymy bootstrapem po twierdzeniach (cytaty jednego twierdzenia nie są niezależne). Dla przebiegu 7 i nowego sędziego to 0,94 z przedziałem 0,90–0,97.

### Czy sędzia cytatów mierzy to, co trzeba

Sędzia (Haiku 5.5, ten sam model co potok) dostawał tylko twierdzenie, wymowę i fragment. Na 87 cytatach z jednej powtórki porównałem go z sędzią z innej rodziny modeli (GPT-6.1-terra, ta sama instrukcja):

| Sędzia | Co widzi | Haiku przyjmuje | GPT przyjmuje | Kappa ogółem | Kappa „obala” |
|---|---|---|---|---|---|
| dotychczasowy | twierdzenie, wymowa, fragment | 0,80 | 0,52 | 0,20 | 0,31 |
| nowy (worker#247) | to samo oraz tytuł, data i adres źródła; reguła brutto; inny rok to poprawne tło | 0,88 | 0,84 | 0,52 | 0,63 |

Stary sędzia zgadzał się z drugim modelem niewiele lepiej niż losowo, więc skok precyzji z 0,61 do 0,78–0,81 po #234 był mierzony narzędziem o nieznanej trafności. Nowy sędzia jest spójniejszy między rodzinami modeli, ale przyjmuje też więcej cytatów (cytaty przebiegu 7: 0,94 zamiast 0,84). Zgodność dwóch modeli nie dowodzi trafności, dlatego potrzebna jest próbka z etykietami ludzi: 60 cytatów (po 20 na wymowę, w tym wszystkie „obala” odrzucone przez któregokolwiek sędziego) czeka w arkuszu `labels-cit-60.csv`, a głosy sędziów są w osobnym pliku klucza. Sędzia zostaje progiem przyjęcia, jeśli kappa z człowiekiem wyniesie co najmniej 0,6 dla „obala” i 0,7 ogółem.

Precyzji cytatów z przebiegów 0–7b (stary sędzia) nie wolno porównywać z przebiegami po worker#247.

### Odłożony zestaw twierdzeń

33 z 43 złotych źródeł zestawu to te same 8 aktów, a poprawki z tej tabeli powstały na błędach z tych 64 przypadków. Zanim scalimy kolejną zmianę celującą w znane błędy (pola w cytacie obalającym, pełne teksty aktów, reranker), potrzebny jest zestaw, którego nikt nie oglądał przy strojeniu. Propozycja: `evals/golden/fact-checks-heldout.json`, 18 twierdzeń, ten sam format i `--cases`.

| Grupa | Liczba | Skąd | Po co |
|---|---|---|---|
| Liczby z aktów spoza 8 znanych (zasiłek pielęgnacyjny, kwota wolna od podatku, wiek emerytalny, stawka VAT na książki, limit kadencji wójta) | 5 | ISAP / ELI, akty obowiązujące | czy pełne teksty aktów i ocena wymowy działają poza przypiętą listą |
| Dane GUS i NBP z innego okresu niż w zestawie (bezrobocie rejestrowane, stopa referencyjna, PKB za 2023) | 3 | komunikaty GUS, NBP | twierdzenia liczbowe z rokiem; cytat musi nieść okres |
| Kwota netto podana jako urzędowa i kwota brutto podana poprawnie (zasiłek dla bezrobotnych, 800+) | 2 | gov.pl | reguła brutto/netto poza płacą minimalną i emeryturą |
| Propozycja albo projekt przedstawiony jako obowiązujące prawo i twierdzenie o samym projekcie | 2 | komunikaty KPRM | reguła propozycji w obie strony |
| Twierdzenia z oceną fact-checkera spoza Demagogu (AFP Sprawdzam, Konkret24), w tym jedno sformułowane ogólniej niż ocena | 3 | ClaimReview | dopasowanie ocen bez przykładów z instrukcji |
| Twierdzenia porównawcze dwóch lat albo dwóch krajów | 2 | Eurostat, ustawy budżetowe | znana słabość oceny parami |
| Twierdzenie o zdarzeniu, które nie zaszło, bez źródła, które by temu przeczyło | 1 | własne | oczekiwane wstrzymanie; klasa `insufficient_evidence` ma dziś 1 przypadek |

Zasady: twierdzenia i etykiety pisze osoba, która nie pracowała nad potokiem; każda etykieta ma `checked_at` i źródło z adresem aktu, a nie hosta; dwie etykiety `misleading` zostają tylko wtedy, gdy potok może taką odpowiedź dać. Zestawu nie uruchamiamy przy strojeniu, tylko raz przed scaleniem zmiany, i raportujemy go obok 64 przypadków. Przy 18 przypadkach to test dymny na regresję, a nie pomiar: 1 przypadek to 5,6 p.p.

### Co dalej po stronie oceny wymowy

Dwa eksperymenty z rzędu (V6, V7) nie dały zysku, więc instrukcja oceny wymowy jest wysycona. Pozostałe odrzucone cytaty „obala” to w około 40% błędy sędziego (naprawia je worker#247), a reszta wymaga lepszych źródeł: pełnych tekstów aktów (worker#235) i stron wyników PKW (worker#236, infra#68). Błędne werdykty z przebiegu 7 to 13 wstrzymań; 9 z nich ma przyczynę w wyszukiwaniu albo pobieraniu. Kolejne kroki mają sens dopiero po nowej migawce korpusu i po etykietach ludzi dla sędziego.
