# language: pl
Funkcja: Wymowa cytatów i werdykt z reguły core

  Scenariusz: cytat, którego nie ma w źródle, nie trafia do odpowiedzi
    Zakładając model wskazał jedyny fragment, którego nie ma dosłownie w tekście źródła
    Gdy system weryfikuje cytaty
    Wtedy fragment nie trafia do odpowiedzi
    Oraz twierdzenie bez cytatu dostaje werdykt "insufficient_evidence" z opisem braków i bez siły

  Scenariusz: szacunek i pozycja budżetu to nie sprzeczność (scenariusz C)
    Zakładając przesłanka, że 650 mln zł to wydatki na transport zbiorowy w 2023 r., a 700 mln zł to przybliżenie z wypowiedzi polityka
    Gdy system ustala wymowę i werdykt
    Wtedy wynik nie jest "insufficient_evidence" z powodu sprzecznych źródeł
    Oraz wyjaśnienie mówi, że jedna liczba to szacunek z wypowiedzi, a druga konkretna pozycja i rok

  Scenariusz: brak dowodów nazywa potrzebne źródło (scenariusz D)
    Zakładając pytanie o bilety w Pcimiu i brak dowodów w korpusie, sieci i indeksie fact-checkerów
    Gdy system pisze odpowiedź
    Wtedy werdykt to "insufficient_evidence", a unresolved nazywa komunikat lokalnego organizatora transportu
    Oraz odpowiedź mówi, że brak wyniku w bazie nie oznacza, że zmiany nie było
    Oraz "co zmieniłoby werdykt" nie powtarza ogólnej formułki o podpisanej wypowiedzi

  Scenariusz: zapowiedź o nieznanym wyniku (scenariusz A)
    Zakładając strona o strajku zapowiedzianym na 20 listopada 2026 r.
    Gdy system ustala werdykt
    Wtedy werdykt to "insufficient_evidence", a unresolved mówi, że nie wiadomo, czy strajk się odbył
    Oraz zapowiedź nie jest potwierdzeniem, że wydarzenie się odbyło

  Scenariusz: sprzeczne wiarygodne źródła
    Zakładając ważne w dacie twierdzenia cytaty wspierające i obalające od różnych publisher_id
    Gdy system ustala werdykt
    Wtedy werdykt to "insufficient_evidence" bez siły
    Oraz wynik ma cytaty obu stron

  Scenariusz: starszy dowód zastąpiony nowszym urzędowym
    Zakładając twierdzenie z claim_date 2026-11-01 i starszy dowód wspierający z 2025 roku oraz nowszy urzędowy dowód obalający z 2026-03-01 od tego samego wydawcy
    Gdy system ustala ważność dowodów
    Wtedy starszy dowód ma validity superseded i nie liczy się do siły ani rozbieżności
    Oraz werdykt to "false" z techniką outdated

  Scenariusz: źródło potwierdza tylko część twierdzenia
    Zakładając źródło z kwotą 4806 zł, które nie mówi, że jest to kwota brutto, i twierdzenie o 4806 zł brutto
    Gdy system pisze odpowiedź
    Wtedy werdykt to "insufficient_evidence" bez siły
    Oraz ograniczenie wskazuje, że nie potwierdzono kwalifikatora "brutto"

  Scenariusz: link do podmiotu z listy sankcji UE dostaje neutralne ostrzeżenie
    Zakładając sprawdzany link prowadzi do domeny podmiotu z aktualnym wpisem na liście sankcji UE
    Gdy system buduje wynik
    Wtedy source_warning ma code "eu_sanctioned_entity", nazwę podmiotu i basis_url do wpisu
    Oraz werdykt jest taki sam jak bez ostrzeżenia
  Scenariusz: polskie twierdzenie pasuje do angielskiego opisu przypadku
    Zakładając w lokalnej kopii EUvsDisinfo przypadek opisany po angielsku
    Gdy obywatel sprawdza podobne twierdzenie po polsku
    Wtedy wynik zawiera IncidentMatch z database "euvsdisinfo", matched_on "content", tytułem, datą i linkiem do opisu przypadku
    Oraz tekst fact jest dowodem wtórnym wydawcy "EUvsDisinfo, EEAS East StratCom Task Force"

  Scenariusz: niezmienność werdyktu
    Zakładając to samo sprawdzenie z dopasowaniem i ostrzeżeniem o domenie oraz bez nich
    Gdy system liczy werdykt
    Wtedy werdykt jest identyczny w obu przypadkach

  Scenariusz: ten sam materiał co w sprawdzeniu fact-checkera (scenariusz I)
    Zakładając wpis z pap.pl z tym samym tytułem, tematem i datą depeszy co publikacja oceniona przez Demagoga
    Gdy system dopasowuje wpis do znanych incydentów
    Wtedy IncidentMatch ma matched_on "content" i podstawę dopasowania: tytuł, temat i data

  Scenariusz: sama domena nie wystarcza (scenariusz I)
    Zakładając wpis z pap.pl o podobnym temacie, ale o innej depeszy
    Gdy system dopasowuje wpis do znanych incydentów
    Wtedy wynik nie ma dopasowania treści

  Scenariusz: ostrzeżenie o domenie
    Zakładając sprawdzany link do domeny z linksToDisinformation i wpis o temacie twierdzenia
    Gdy obywatel sprawdza podobne twierdzenie po polsku
    Wtedy wynik ma IncidentMatch z matched_on "domain"

  Scenariusz: fragment z migawki korpusu przeczy twierdzeniu
    Zakładając w migawce korpusu fragment komunikatu RCB, który przeczy twierdzeniu
    Gdy system ocenia dowody z korpusu i pisze odpowiedź
    Wtedy werdykt to "false" z cytatem z tego fragmentu
    Oraz cytat ma wydawcę i domenę z katalogu
