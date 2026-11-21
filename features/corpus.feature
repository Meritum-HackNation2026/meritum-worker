# language: pl
Funkcja: Lokalna kopia EUvsDisinfo odświeżana przez serwer MCP

  Scenariusz: pierwsze pełne skanowanie
    Zakładając ważny token EUvsDisinfo
    I w źródle 230 przypadków i 120 artykułów
    Gdy workflow synchronizacji EUvsDisinfo kończy przebieg
    Wtedy lokalna kopia ma wszystkie artykuły i przypadki pobrane stronami po 100
    I opisy przypadków i teksty fact mają embeddingi wielojęzyczne

  Scenariusz: kolejne skanowanie jako różnica
    Zakładając ważny token EUvsDisinfo
    I kopia z poprzedniego przebiegu
    I w źródle 5 nowych wpisów, 2 zmienione i 1 usunięty
    Gdy workflow synchronizacji kończy przebieg
    Wtedy 5 wpisów jest dodanych, 2 zaktualizowane, a 1 oznaczony jako usunięty

  Scenariusz: brak tokenu trafia do raportu gotowości
    Zakładając brak tokenu EUvsDisinfo
    Wtedy raport gotowości workera wskazuje brak "EUVSDISINFO_MCP_API_KEY"
