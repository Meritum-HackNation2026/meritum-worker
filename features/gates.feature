# language: pl
Funkcja: Porównanie bramek przed LLM (ADR-35)

  Scenariusz: wybór klasyfikatora wstrzyknięć
    Zakładając polski zestaw ataków z golden setu i dwie konfiguracje klasyfikatora (Model Armor w eu, Prompt Guard na Workers AI)
    Gdy zespół uruchamia porównanie bramek
    Wtedy raport podaje dla każdej odporność według definicji z ADR-23, fałszywe alarmy na przypadkach bez ataku, czas i koszt

  Scenariusz: reranker włączony i wyłączony
    Zakładając golden set
    Gdy porównanie uruchamia przebieg z rerankerem i z pustą bramką
    Wtedy raport podaje różnicę macro-F1, poprawności cytowań, mediany czasu i kosztu 100 testów

  Scenariusz: tylko porównanie NLI
    Zakładając konfiguracja z wstępną oceną wymowy NLI
    Gdy porównanie się kończy
    Wtedy raport podaje zgodność NLI z oceną modelu i ręczną próbą, a żaden przebieg produkcyjny nie używa NLI

  Scenariusz: maskowanie DLP bez nadmiarowego maskowania
    Zakładając przypadki DLP z fikcyjnymi danymi osobowymi, nazwiskami osób publicznych, kwotami i adresami instytucji
    Gdy porównanie uruchamia bramkę DLP
    Wtedy raport podaje wykryte dane osobowe i nadmiarowe maskowanie treści, która musi zostać bez zmian

  Scenariusz: klasyfikator wejścia
    Zakładając zapisane odpowiedzi klasyfikatora wejścia na przypadkach z trzema klasami
    Gdy porównanie się kończy
    Wtedy raport podaje trafność i udział twierdzeń, które klasyfikator zatrzymałby przed głównym modelem
