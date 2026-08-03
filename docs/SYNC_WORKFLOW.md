# PAS Connect — Sync Workflow

1. Carica configurazione sicura.
2. Ottieni o valida il token GPExe.
3. Sincronizza team.
4. Sincronizza categorie e tag.
5. Sincronizza atleti.
6. Sincronizza sessioni, preferendo `updated_on_gte`.
7. Per ogni sessione nuova/modificata recupera athlete session ID e dettaglio.
8. Recupera track solo quando necessario per diagnostica o metriche mancanti.
9. Normalizza nello schema PAS.
10. Valida conteggi, chiavi, unità e duplicati.
11. Esegui commit atomico nel futuro database PAS.
12. Registra ultimo cursore di sincronizzazione.

La release 3.7.36 implementa solo il piano e i contratti; non esegue scritture.

## v3.7.40 - Reference data snapshot

Dopo una connessione runtime valida, il comando `Sincronizza anagrafiche GPExe`
recupera Teams, Categories, Tags e Athletes, li normalizza e salva una snapshot
atomica in `.pas_data/gpexe_snapshot.json`. La snapshot non alimenta ancora le
analisi e non modifica `Database Hellas 25-26.xlsx`.
