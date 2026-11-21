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
