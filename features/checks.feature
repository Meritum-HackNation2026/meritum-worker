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

  Scenariusz: post za logowaniem
    Zakładając link do posta na Facebooku wymagającego logowania
    Gdy workflow sprawdza link
    Wtedy wynik ma stan technical_failure z kodem "url_unavailable" i prośbą o wklejenie tekstu, bez werdyktu

  Scenariusz: sam tekst bez linku
    Zakładając wklejony tekst bez adresu
    Gdy workflow publikuje postęp
    Wtedy krok fetch_url ma stan skipped

  Scenariusz: awaria kroku kończy sprawdzenie od razu
    Zakładając krok workflowu sprawdzania rzuca wyjątek
    Gdy workflow kończy się błędem
    Wtedy strumień postępu dostaje ten krok jako failed i końcowy status technical_failure z kodem awarii z kontraktu v4

  Scenariusz: wyszukiwanie w sieci przekracza 10 s
    Zakładając sprawdzenie czeka na wynik wyszukiwania w sieci
    Gdy wyszukiwarka nie odpowiada przez 10 s
    Wtedy wynik ma stan technical_failure bez twierdzeń i bez werdyktu
    Oraz CheckRecord.retrieval_errors zapisuje przekroczenie czasu

  Scenariusz: model zawodzi po wyczerpaniu ponowień
    Zakładając adapter modelu zwraca błąd 503 przy każdej z 3 prób
    Gdy workflow kończy krok
    Wtedy wynik ma stan technical_failure, a komunikat nie zawiera nazwy klucza ani dostawcy
    Oraz CheckRecord ma status technical_failure
