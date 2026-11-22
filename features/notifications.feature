# language: pl
Funkcja: Pytania bez odpowiedzi są sprawdzane ponownie po nowej migawce korpusu

  Scenariusz: nowy dowód zmienia werdykt
    Zakładając twierdzenie z werdyktem "brak wystarczających dowodów" sprzed 3 dni
    Gdy nowa migawka zawiera podobny dokument urzędowy i ponowne sprawdzenie daje "fałszywe"
    Wtedy sesja dostaje powiadomienie new_evidence, a nowy wynik ma własny CheckRecord

  Scenariusz: werdykt bez zmian
    Zakładając twierdzenie z werdyktem "brak wystarczających dowodów" sprzed 3 dni
    Oraz ponowne sprawdzenie znowu daje "brak wystarczających dowodów"
    Gdy workflow kończy się
    Wtedy żadne powiadomienie nie jest wysyłane
