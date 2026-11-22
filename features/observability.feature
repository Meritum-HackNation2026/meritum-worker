# language: pl
Funkcja: Golden set A–J i ewaluacja

  Scenariusz: plik przypadków przechodzi walidację
    Zakładając plik golden setu w repozytorium
    Gdy skrypt waliduje przypadki
    Wtedy każdy przypadek ma wejście, kanał, oczekiwany stan albo werdykt głównego twierdzenia i scenariusz A–J

  Scenariusz: scenariusz H w dwóch wariantach
    Zakładając przypadki scenariusza H
    Wtedy istnieje wariant z powtórzeniem w tej samej sesji i wariant z powtórzeniem z innego kanału

  Scenariusz: przebieg na pliku jury
    Zakładając plik CSV z 30 przypadkami w formacie przypadków
    Gdy członek jury uruchamia "uv run meritum-eval --cases jury.csv"
    Wtedy raport podaje macro-F1, pokrycie i poprawność cytowań, wstrzymanie, odporność, medianę i maksimum czasu, koszt 100 testów, spójność kanałów i pętlę informacji

  Scenariusz: nieudany przypadek zostaje w medianie
    Zakładając przypadek kończy się stanem technical_failure
    Gdy skrypt liczy czas
    Wtedy czas przypadku z CheckRecord liczy się do mediany
    I stan niebędący werdyktem jest w macro-F1 osobną klasą błędu

  Scenariusz: za mały plik
    Zakładając plik z 12 przypadkami
    Gdy skrypt waliduje wejście
    Wtedy kończy się błędem z liczbą wymaganych przypadków

  Scenariusz: porównanie dwóch modeli
    Zakładając golden set i dwie konfiguracje modelu głównego
    Gdy zespół uruchamia "uv run meritum-eval --compare-models config-a.toml config-b.toml"
    Wtedy raport podaje dla każdej konfiguracji macro-F1, poprawność cytowań, medianę czasu, tokeny na sekundę i koszt 100 testów

  Scenariusz: porównanie embeddingów na prawdziwym korpusie
    Zakładając korpus wczytany z migawki i dwie konfiguracje modelu embeddingów
    Gdy zespół uruchamia porównanie
    Wtedy raport podaje trafność wyszukiwania w korpusie na przypadkach z golden setu, z top 20 jak w wyszukiwaniu hybrydowym, i koszt
    I pole corpus w raporcie wskazuje migawkę corpus_version zamiast korpusu zastępczego

  Scenariusz: powtórzenie przebiegu bez kluczy
    Zakładając nagrane kasety i migawka 2026-11-20T10:00Z
    Gdy ktoś uruchamia ewaluację w trybie replay bez kluczy dostawców
    Wtedy wyniki są identyczne z przebiegiem nagrania

  Scenariusz: paczka do publikacji
    Gdy zespół tworzy paczkę do odtworzenia
    Wtedy paczka zawiera przypadki, adresy źródeł, cytowane fragmenty i manifest z identyfikatorami dokumentów, sumami kontrolnymi i fetched_at
    I nie zawiera pełnych tekstów ani kaset


  # --- przebieg ewaluacji jako workflow (worker#38) ---

  Scenariusz: przebieg uruchomiony ze strony
    Zakładając backend zleca workflow przebiegu ewaluacji dla golden setu
    Gdy przebieg się kończy
    Wtedy w bazie jest EvalRun z miernikami, datą, corpus_version i wynikami każdego przypadku
    I emitowane jest zdarzenie powiadomienia o końcu przebiegu dla analityka, który go uruchomił

  Scenariusz: własny zestaw
    Zakładając zestaw z pliku CSV zapisany przez backend
    Gdy backend zleca przebieg na tym zestawie
    Wtedy przebieg liczy te same mierniki co na golden secie

  Scenariusz: porównanie dwóch przebiegów
    Zakładając dwa zapisane przebiegi
    Gdy backend prosi o porównanie
    Wtedy wynik podaje różnice mierników i przypadki, które zmieniły wynik


  # --- rubryka tekstu odpowiedzi (worker#252) ---

  Scenariusz: sędzia rubryki ocenia tekst odpowiedzi według scenariusza
    Zakładając przypadek scenariusza D z odpowiedzią wzorcową i wynik sprawdzenia, który mówi, że zmiany nie było
    Gdy meritum-eval ocenia przebieg z flagą --judge
    Wtedy kryterium „nie twierdzi, że zdarzenia nie było” jest niespełnione
    I przypadek nie przechodzi rubryki, a raport podaje to kryterium przy id przypadku

  Scenariusz: raport podaje zdawalność rubryki per scenariusz
    Zakładając przebieg z przypadkami scenariuszy A i J ocenionymi przez sędziego dwoma głosami
    Gdy powstaje raport
    Wtedy każdy scenariusz ma rubric_pass_rate i rubric_score obok accuracy
    I przypadek, w którym głosy się różnią, liczy się jako pół zaliczenia
