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

## v3.7.41 - Reference data database

La stessa sincronizzazione scrive ora in modo transazionale anche nel database
SQLite isolato `.pas_data/pas_connect.sqlite3`. Gli ID provider sono usati come
chiavi di upsert e ogni esecuzione viene registrata in `gpexe_sync_runs`.
La sorgente operativa del PAS resta Excel. Il file locale è adatto a sviluppo e
verifica; su Streamlit Community Cloud è effimero e non rappresenta ancora la
persistenza cloud definitiva.

## Team Sessions incrementali (v3.7.42)

1. Il connettore legge il maggiore `provider_updated_at` già presente nel database PAS Connect.
2. Se disponibile, invia `updated_on_gte` a `GET /rest/v2/session/team/`.
3. Le risposte vengono normalizzate e salvate con upsert su `provider_session_id`.
4. Il log registra record ricevuti, inseriti e aggiornati.
5. Il database Excel e il PAS Core non vengono modificati.


## Step dettaglio Team Sessions
Dopo la lista Team Sessions, PAS Connect scarica solo i dettagli mancanti e registra eventuali errori per singola sessione.

## Step Athlete Sessions (v3.7.44)
Dopo Team Sessions e relativi dettagli, PAS Connect individua gli ID atleta-sessione mancanti, scarica ogni dettaglio e lo salva con upsert. Excel e PAS Core rimangono isolati.

## Orchestrazione completa v3.7.45
Il comando `run_full_sync` esegue in sequenza anagrafiche, Team Sessions,
dettagli Team Sessions e Athlete Sessions. Ogni fase viene salvata prima della
successiva e può comunicare avanzamento alla UI tramite callback. Le
sincronizzazioni manuali restano disponibili per diagnostica.
