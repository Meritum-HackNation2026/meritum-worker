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

  Scenariusz: twierdzenie z ponownego sprawdzenia trafia do moderatorów
    Zakładając wynik ponownego sprawdzenia z werdyktem "brak wystarczających dowodów"
    Gdy użytkownik przekazuje to twierdzenie moderatorom
    Wtedy powstaje sprawa z tym twierdzeniem

  Scenariusz: usunięcie osoby czyści plan ponownych sprawdzeń
    Zakładając plan ponownych sprawdzeń wymienia sesję "session-1"
    Gdy backend zleca delete_subject dla "session-1"
    Wtedy w DBOS nie zostaje żaden zapis z "session-1"
