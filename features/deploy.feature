# language: pl
Funkcja: Migracje w deployu workera

  Scenariusz: deploy z develop
    Zakładając nową migrację tabel aplikacji i nową migrację schematu corpus
    Gdy deploy workera "dev" startuje
    Wtedy migracja app jest uruchomiona, a migracja corpus nie
    I log deployu mówi, że migracje corpus uruchamia tylko main

  Scenariusz: deploy z main
    Zakładając nową migrację tabel aplikacji i nową migrację schematu corpus
    Gdy deploy workera "prd" startuje
    Wtedy migracje app i corpus są uruchomione, zanim wystartuje nowy kontener

  Scenariusz: nieudana migracja
    Zakładając migrację app_dev, która kończy się błędem
    Gdy deploy workera "dev" startuje
    Wtedy stary kontener działa dalej, a deploy kończy się błędem z nazwą migracji "app_dev"

  Scenariusz: brak tokenu EUvsDisinfo
    Zakładając worker startuje bez zmiennej z tokenem EUvsDisinfo
    Gdy kończy sprawdzanie gotowości
    Wtedy raport nie ma braków zmiennych, euvsdisinfo jest niedostępny, a log mówi degraded bez wartości sekretów

  Scenariusz: korpus EUvsDisinfo nie blokuje sprawdzeń na dev
    Zakładając worker dev z tokenem EUvsDisinfo, którego serwer nie odpowiada
    Gdy kończy sprawdzanie gotowości
    Wtedy raport nie ma braków zmiennych, euvsdisinfo jest niedostępny, a log mówi degraded bez wartości sekretów

  Scenariusz: wszystko ustawione
    Zakładając wszystkie wymagane zmienne i dostępni dostawcy
    Gdy worker publikuje raport
    Wtedy raport nie ma braków i ma czas sprawdzenia
