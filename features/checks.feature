# language: pl
Funkcja: Smoke test workera

  Scenariusz: ping odsyła wiadomość ze środowiskiem workera
    Zakładając wiadomość "hej" w bieżącej wersji kontraktu
    Gdy worker w środowisku "dev" wykona ping
    Wtedy odpowiedź zawiera wiadomość "hej" i środowisko "dev"

  Scenariusz: sprawdzenie tekstu przechodzi całą ścieżkę na stubie
    Zakładając worker działa z MERITUM_LLM_PROVIDER=stub
    Gdy workflow "check" dostaje CheckRequest z tekstem "Od 1 stycznia 2026 płaca minimalna wynosi 4806 zł"
    Wtedy workflow kończy się stanem done z CheckResult zgodnym z kontraktem
    Oraz CheckRecord ma question_masked, channel, received_at, answered_at, corpus_version, verdicts, source_ids, escalation i retention_until

  Scenariusz: wynik niezgodny z kontraktem nie jest pokazywany
    Zakładając stub zwraca wynik niezgodny z regułami kontraktu
    Gdy workflow buduje CheckResult
    Wtedy wynik ma stan technical_failure bez twierdzeń
    Oraz CheckRecord ma status technical_failure

  Scenariusz: twierdzenie i opinia w jednej wiadomości
    Zakładając tekst "Inflacja w październiku wyniosła 2,8%. Rząd kompletnie sobie nie radzi." z nagranymi odpowiedziami modelu "claims_fact_and_opinion.json"
    Gdy system wyodrębnia twierdzenia
    Wtedy wynik ma stan done i 2 wyniki
    Oraz opinia dostaje werdykt "nie podlega weryfikacji"

  Scenariusz: więcej niż 5 twierdzeń
    Zakładając tekst z 8 twierdzeniami o faktach z nagranymi odpowiedziami modelu "claims_eight_facts.json"
    Gdy system wyodrębnia twierdzenia
    Wtedy sprawdza 5 twierdzeń, a pozostałe 3 są wymienione w limitations

  Scenariusz: wejście bez twierdzenia
    Zakładając tekst "czy to prawda?" z nagranymi odpowiedziami modelu "claims_none.json"
    Gdy system wyodrębnia twierdzenia
    Wtedy wynik ma stan needs_clarification bez twierdzeń, tylko z komunikatem

  Scenariusz: data twierdzenia z tekstu
    Zakładając tekst "W marcu 2025 r. bezrobocie wynosiło 5,3%" z nagranymi odpowiedziami modelu "claims_dated.json"
    Gdy system wyodrębnia twierdzenia
    Wtedy twierdzenie ma claim_date 2025-03-01 i claim_date_source "text"
