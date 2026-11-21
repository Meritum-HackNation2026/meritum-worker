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
