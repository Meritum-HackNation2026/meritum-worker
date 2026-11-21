# language: pl
Funkcja: Golden set A–J

  Scenariusz: plik przypadków przechodzi walidację
    Zakładając plik golden setu w repozytorium
    Gdy skrypt waliduje przypadki
    Wtedy każdy przypadek ma wejście, kanał, oczekiwany stan albo werdykt głównego twierdzenia i scenariusz A–J

  Scenariusz: scenariusz H w dwóch wariantach
    Zakładając przypadki scenariusza H
    Wtedy istnieje wariant z powtórzeniem w tej samej sesji i wariant z powtórzeniem z innego kanału
