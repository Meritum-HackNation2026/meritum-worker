# language: pl
Funkcja: Warstwa corpus_ready (silver i gold) przygotowuje korpus dla agentów

  Scenariusz: budowa gold dzieli Konstytucję na artykuły z nagłówkiem
    Zakładając dokument bronze Konstytucji z ELI DU/1997/483 w korpusie
    Gdy workflow corpus_ready_build buduje warstwę gold
    Wtedy jest fragment "Art. 29." z nagłówkiem zawierającym "Dz.U. 1997 nr 78 poz. 483" i rodzaj "act"
    I tekst fragmentu jest równy znakom full_text bronze od start_offset do end_offset

  Scenariusz: przy wyłączonej fladze nic się nie buduje
    Zakładając MERITUM_CORPUS_READY nie jest ustawione
    Gdy worker startuje
    Wtedy workflow corpus_ready_build nie jest zaplanowany
