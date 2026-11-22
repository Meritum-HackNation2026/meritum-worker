# language: pl
Funkcja: Reranker fragmentów przed oceną stanowiska

  Scenariusz: Vertex AI ranking API
    Zakładając MERITUM_RERANKER=vertex i twierdzenie z 20 fragmentami
    Gdy krok badań woła reranker
    Wtedy dostaje fragmenty z oceną w kolejności trafności

  Scenariusz: awaria dostawcy rerankera
    Zakładając MERITUM_RERANKER=vertex i twierdzenie z 20 fragmentami
    I dostawca rerankera nie odpowiada
    Gdy krok badań woła reranker
    Wtedy dostaje fragmenty w kolejności z wyszukiwania, a błąd trafia do retrieval_errors

  Scenariusz: reranker z OpenRouter sortuje fragmenty
    Zakładając MERITUM_RERANKER=openrouter i twierdzenie z 20 fragmentami
    Gdy krok badań woła reranker
    Wtedy dostaje fragmenty z oceną w kolejności trafności

  Scenariusz: awaria OpenRouter nie zatrzymuje sprawdzenia
    Zakładając MERITUM_RERANKER=openrouter i twierdzenie z 20 fragmentami
    I dostawca rerankera nie odpowiada
    Gdy krok badań woła reranker
    Wtedy dostaje fragmenty w kolejności z wyszukiwania, a błąd trafia do retrieval_errors

  Scenariusz: reranker dostaje 30 kandydatów z korpusu na zapytanie
    Zakładając migawkę korpusu z 40 fragmentami pasującymi do twierdzenia
    Gdy krok search_corpus szuka dowodów dla twierdzenia
    Wtedy każde zapytanie do korpusu prosi o 30 fragmentów
    I reranker zostawia 5 fragmentów

  Scenariusz: reranker OpenRouter używa klucza modelu
    Zakładając MERITUM_RERANKER=openrouter bez własnego tokenu i z kluczem OPENROUTER_API_KEY
    Gdy krok badań woła reranker
    Wtedy reranker wysyła klucz modelu w nagłówku Authorization
