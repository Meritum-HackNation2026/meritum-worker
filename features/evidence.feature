# language: pl
Funkcja: Wiek i ważność dowodów w workerze

  Scenariusz: stary dowód nie przeważa nad świeżym
    Zakładając twierdzenie z datą i dwa dowody, stary z expires i świeży
    Gdy worker liczy siłę dowodów i werdykt
    Wtedy wiek i ważność dowodów liczone są od daty twierdzenia funkcjami z core#41