# language: pl
Funkcja: Smoke test workera

  Scenariusz: ping odsyła wiadomość ze środowiskiem workera
    Zakładając wiadomość "hej" w bieżącej wersji kontraktu
    Gdy worker w środowisku "dev" wykona ping
    Wtedy odpowiedź zawiera wiadomość "hej" i środowisko "dev"
