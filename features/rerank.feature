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
