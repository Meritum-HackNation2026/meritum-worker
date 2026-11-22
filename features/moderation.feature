# language: pl
Funkcja: Sprawy moderatora powstają same i grupują podobne twierdzenia

  Scenariusz: powtórzone pytanie z innego kanału
    Zakładając twierdzenie bez odpowiedzi zadane przez formularz WWW
    Gdy podobne twierdzenie bez odpowiedzi przychodzi z Discorda
    Wtedy powstaje jedna sprawa z powodem "repeated_unanswered" i oboma sprawdzeniami
    Oraz Escalation ma state "created" i numer sprawy

  Scenariusz: temat wysokiego ryzyka
    Zakładając lista tematów administratora zawiera "zdrowie"
    Gdy twierdzenie bez odpowiedzi dotyczy szczepionek
    Wtedy powstaje sprawa z powodem "high_risk", high_risk_topic "zdrowie" i high_risk_classified_by "embeddings"

  Scenariusz: parafraza trafia do tej samej sprawy (scenariusz H)
    Zakładając pytanie bez odpowiedzi "Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?"
    Gdy przychodzi parafraza "Czy Pcim wprowadza zakaz wjazdu diesli do centrum?"
    Wtedy oba zgłoszenia są w jednej sprawie, a Escalation ma numer sprawy dopiero po potwierdzonym zapisie

  Scenariusz: parafraza, gdy sprawa już istnieje po kliknięciu (scenariusz H, workflow escalate_claim)
    Zakładając pytanie bez odpowiedzi "Czy od przyszłego tygodnia diesle nie będą mogły wjechać do centrum Pcimia?"
    Oraz użytkownik przekazał to pytanie moderatorom
    Gdy przychodzi parafraza "Czy Pcim wprowadza zakaz wjazdu diesli do centrum?"
    Wtedy oba zgłoszenia są w jednej sprawie, a Escalation ma numer sprawy dopiero po potwierdzonym zapisie
    Oraz Escalation ma state "updated" i numer sprawy

  Scenariusz: różne liczby to różne sprawy
    Zakładając otwarta sprawa o "inflacja wynosi 5%"
    Gdy przychodzi twierdzenie bez odpowiedzi "inflacja wynosi 15%"
    Wtedy nie dołącza do tej sprawy

  Scenariusz: pojedynczy brak dowodów tylko rekomenduje
    Zakładając moderator z kontem w panelu
    Gdy sprawdzenie kończy się brakiem dowodów w zwykłym temacie
    Wtedy Escalation ma state "recommended" bez numeru sprawy
    Oraz moderatorzy nie dostają powiadomienia

  Scenariusz: sprawa z kroku sprawdzenia trafia do skrzynek moderatorów
    Zakładając moderator z kontem w panelu
    Oraz to samo pytanie bez odpowiedzi zadała już inna sesja
    Gdy sprawdzenie kończy się brakiem dowodów w zwykłym temacie
    Wtedy Escalation ma state "created" i numer sprawy
    Oraz moderator dostaje powiadomienie "case_assigned" z linkiem "/panel"

  Scenariusz: moderator odpowiada na sprawę, pytający dostaje powiadomienie
    Zakładając sprawa "#S-1" z jednym sprawdzeniem, na którą moderator odpowiedział
    Gdy worker rozsyła odpowiedzi moderatorów
    Wtedy pytający dostaje powiadomienie "moderator_answer" z numerem sprawy "#S-1"
    Oraz drugie rozesłanie nie dodaje następnego
