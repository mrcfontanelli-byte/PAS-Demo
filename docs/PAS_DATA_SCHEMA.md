# PAS Data Schema v1.0 — Bozza stabile

Lo schema è indipendente dal provider. I campi `provider_*_id` conservano la
chiave originale e saranno affiancati da chiavi PAS interne nella fase database.

## Entità principali

### teams
`provider`, `provider_team_id`, `team_name`, `club_id`, `season`, `sport`,
`start_date`, `end_date`, `locked`, `updated_at`.

### players
`provider`, `provider_player_id`, `external_player_id`, `first_name`,
`last_name`, `player_name`, `short_name`, `birth_date`, `club_id`, `photo_url`,
`v0`, `a0`, `role_provider`, `role_pas`, `active`.

### session_categories
`provider`, `provider_category_id`, `category_name`, `team_id`,
`provider_color`, `pas_category`.

### tags / session_tags
Tag provider e relazione molti-a-molti con le sessioni.

### sessions
ID provider, team, categoria, nome, timestamp iniziale/finale, durata, note,
stato di elaborazione, `updated_at` e campi PAS derivati: Match Cycle,
MD+/MD-, Length Cycle, opponent e home/away.

### athlete_sessions
Relazione giocatore-sessione con stato, ruolo, starter status e metriche
aggregate della sessione.

### drills / athlete_drill_metrics
Drill della sessione e dati nel livello `giocatore × sessione × drill`.

### tracks
Identificativo della traccia, atleta, team, timestamp UTC, timezone e stato.

## Regole

- Date ISO-8601; distanze in metri; velocità in km/h; durata interna in secondi.
- Mancante = `NULL`, mai zero automatico.
- Metriche GPExe posizionali interpretate tramite `table_data.headers`, mai con indici fissi.
- Nomi categorie PAS controllati da tassonomia; categorie provider conservate separatamente.
- `Team Average` non è un atleta e non entra nei totali additivi.

## Implementazione locale v3.7.41

Le prime entità provider sono persistite nel file isolato
`.pas_data/pas_connect.sqlite3` nelle tabelle `gpexe_teams`,
`gpexe_categories`, `gpexe_tags`, `gpexe_athletes` e `gpexe_sync_runs`.
Le chiavi primarie sono gli ID stabili GPExe e le sincronizzazioni successive
aggiornano i record con upsert, senza duplicarli. Questo database non sostituisce
`Database Hellas 25-26.xlsx` e non alimenta ancora il PAS Core.

Su Streamlit Community Cloud il filesystem è effimero: il file SQLite può essere
ricreato dopo reboot o deploy. La persistenza definitiva richiederà un database
cloud esterno mantenendo lo stesso schema logico.
