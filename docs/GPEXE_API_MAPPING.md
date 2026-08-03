# Mapping GPExe → PAS (iniziale)

| Risorsa GPExe | Campo | Campo PAS |
|---|---|---|
| Team | `id` | `provider_team_id` |
| Team | `name` | `team_name` |
| Team | `season` | `season` |
| Athlete | `id` | `provider_player_id` |
| Athlete | `custom_id` | `external_player_id` |
| Athlete | `first_name`, `last_name`, `name` | anagrafica giocatore |
| Athlete | `v0`, `a0` | parametri provider conservati |
| Category | `id`, `name`, `color` | categoria provider + mapping PAS |
| TeamSession | `id` | `provider_session_id` |
| TeamSession | `start_timestamp`, `end_timestamp` | intervallo sessione |
| TeamSession | `updated_on` | sincronizzazione incrementale |
| AthleteSession | `id` | `provider_athlete_session_id` |
| AthleteSession | `values` + `headers` | metriche normalizzate |
| Track | `id`, `athlete`, `team`, `utc_timestamp` | track PAS |

## Metriche già individuate

Distance, acceleration/deceleration events, speed events, max speed,
equivalent distance, equivalent distance index, recovery average time,
zone velocità/accelerazione/decelerazione/cardio/potenza.

Le metriche a soglia (es. 19.8–25.2 km/h e >25.2 km/h) saranno derivate dalle
speed zones dopo verifica sulle soglie reali dell'istanza GPExe.


## Team Session detail
`table_data.headers` definisce dinamicamente la corrispondenza delle posizioni in `athlete_sessions[].values`; il PAS non usa indici hard-coded.

## Athlete Session detail (v3.7.44)
`GET /rest/v2/session/athlete/{id}/` viene mappato conservando ID, sessione, atleta, drill, track, timing, stato, metriche scalari e collezioni di zone. Nuovi campi del provider restano disponibili nel payload grezzo.


## Mapping Layer v3.8.8
`modules/data_mapping.py` contiene il catalogo canonico delle metriche PAS, gli alias provider, le unità attese e conversioni esplicite. Il mapping è isolato e non alimenta ancora il PAS Core. Label sconosciute vengono ignorate, valori mancanti restano nulli e unità non supportate producono un errore di validazione.
