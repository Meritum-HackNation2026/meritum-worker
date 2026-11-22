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
    Oraz CheckResult ma znacznik AI z dostawcą i modelem wywołania, które napisało odpowiedź

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

  Scenariusz: link do artykułu
    Zakładając link do publicznego artykułu z datą publikacji 2026-11-18
    Gdy workflow sprawdza link
    Wtedy krok fetch_url kończy się stanem done, a twierdzenia z tekstu artykułu mają claim_date_source "input_published_at", gdy tekst nie podaje innej daty

  Scenariusz: względna data liczy się od dnia publikacji
    Zakładając artykuł opublikowany 2026-11-20 mówi „wczoraj rząd przyjął ustawę”
    Gdy workflow sprawdza link
    Wtedy prompt ekstrakcji podaje datę 2026-11-20, a twierdzenie ma claim_date 2026-11-19

  Scenariusz: data publikacji z przyszłości jest pomijana
    Zakładając metadane strony podają datę publikacji 2026-01-06, późniejszą niż chwila pobrania
    Gdy workflow sprawdza link
    Wtedy twierdzenie bez daty w tekście nie dostaje daty 2026-01-06

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

  Scenariusz: techniczna porażka niesie kod, a nie klucz kopii
    Zakładając worker działa z MERITUM_LLM_PROVIDER=stub
    Gdy model nie odpowiada w kroku write_answer
    Wtedy wynik ma stan technical_failure bez twierdzeń
    Oraz failure_code wynosi "provider_unavailable"
    Oraz message nie zaczyna się od "status_hint."

  Scenariusz: wiadomość głosowa z twierdzeniem
    Zakładając plik OGG z Opus z nagraniem "Od jutra pociągi do Gdańska nie jeżdżą"
    Gdy workflow sprawdzania działa
    Wtedy krok transcribe_audio kończy się stanem done, a twierdzenie z transkrypcji dostaje werdykt
    Oraz wynik zawiera transkrypcję oznaczoną jako automatyczna

  Scenariusz: awaria transkrypcji
    Zakładając dostawca transkrypcji zwraca błąd
    Gdy workflow sprawdzania działa
    Wtedy wynik ma stan technical_failure

  Scenariusz: nieobsługiwany format
    Zakładając plik w formacie, którego port nie obsługuje
    Gdy workflow sprawdzania działa
    Wtedy wynik ma stan out_of_scope z komunikatem, co można wysłać zamiast

  Scenariusz: zrzut ekranu z twierdzeniem
    Zakładając zdjęcie z tekstem "Od 1 grudnia zakaz wjazdu aut spalinowych do Warszawy. Opublikowano 12.11.2026."
    Gdy workflow sprawdza obraz
    Wtedy twierdzenie z OCR dostaje werdykt
    Oraz wynik zawiera tekst odczytany z obrazu
    Oraz odpowiedź mówi, że nie szukano wcześniejszych wystąpień obrazu
    Oraz odpowiedź mówi, że data na obrazie nie potwierdza daty publikacji

  Scenariusz: awaria OCR
    Zakładając dostawca OCR zwraca błąd
    Gdy workflow sprawdza obraz
    Wtedy wynik obrazu ma stan technical_failure

  Scenariusz: nieobsługiwany obraz
    Zakładając plik, który nie jest obrazem PNG, JPEG ani WebP
    Gdy workflow sprawdza obraz
    Wtedy wynik obrazu ma stan out_of_scope z kodem image i kodem ograniczenia

  Scenariusz: trzy twierdzenia sprawdzane równolegle
    Zakładając tekst z 4 twierdzeniami
    Gdy workflow uruchamia agenty badawcze
    Wtedy najwyżej 3 twierdzenia są badane jednocześnie
    Oraz AnalysisStatus pokazuje kilka kroków w stanie active naraz

  Scenariusz: wersja wstępna bez werdyktu
    Zakładając agent główny strumieniuje wstępną odpowiedź
    Gdy cytaty nie przeszły jeszcze weryfikacji
    Wtedy wersja wstępna nie zawiera werdyktu

  Scenariusz: zamaskowany szkic podczas pisania odpowiedzi
    Zakładając stub zwraca długie wyjaśnienie z adresem e-mail
    Gdy workflow buduje CheckResult
    Wtedy krok write_answer pokazuje zamaskowany szkic do 4000 znaków
    Oraz końcowy wynik zastępuje szkic

  Scenariusz: tekst dla obywatela nie zawiera kodów
    Zakładając model zwraca wyjaśnienie z nazwą kodu werdyktu albo ograniczenia
    Gdy workflow buduje CheckResult
    Wtedy wyjaśnienie i ograniczenia nie zawierają nazw kodów
