# Changelog

## PAS v4.18.0 - 2026-08-20

### Added

- Aggiunta la foundation storica multi-season GPExe con contesto provider Team/Season.
- Aggiunto il supporto al catalogo Team e ai relativi nomi.
- Aggiunto il fallback REST elementary quando il payload aggregate non è sufficiente.
- Aggiunta la classificazione gerarchica di session, exercise e drill.
- Aggiunta l'eligibility canonica delle TeamSession per la Dashboard PAS.

### Changed

- Il selector GPExe mostra soltanto le TeamSession appartenenti alle categorie Dashboard canoniche.
- **Seleziona tutte** usa esclusivamente le TeamSession Dashboard eligible e non applica implicit-all a una selezione vuota.
- `Different Traning` è trattato come alias logico di `Different Training`, preservando il valore raw del provider.

### Fixed

- Resa autorevole la membership scoped per le drill TeamSession con `teamsession` parent interno.
- Impedito il doppio conteggio automatico in Dashboard tra parent ed exercise/drill.
- Consolidati la gestione `N/D` e lo stato dei selector nel flusso GPExe corrente.

### Unchanged

- I payload raw del provider, i dati PAS Connect e il file Excel canonico non vengono alterati.
- Lo schema PAS Connect resta 12.
- Daily Sync operativo avanzato 2026/2027, Drills Analysis GPExe, Match Cycle GPExe e backfill completo 2025/2026 restano fuori dalla release.

## PAS v4.17.4 - 2026-08-14

### Fixed

- Ripulita la Dashboard dalle metriche completamente `N/D`, ora raccolte in un expander dedicato; i selector di dettaglio e Session Report mostrano soltanto metriche disponibili.
- Resi coerenti i colori delle Dynamic Speed Zones tra grafici e contesti GPExe.
- Reso visibile Team 469 / 2025/2026 tramite discovery dei dati locali, senza dipendenza esclusiva dalla sync history.
- Mantenute disponibili le TeamSession locali quando la selezione corrente è vuota, senza applicare un implicit all.
- Separato lo stato del multiselect per Team/stagione e stabilizzato il contratto frontend con token stringa e stato canonico `list[int]`.
- Corretto lo stacking dei menu BaseWeb sopra il pannello Settings.

### Improved

- Distinti esplicitamente l'insieme delle TeamSession locali disponibili e il sottoinsieme selezionato dall'utente.
- Rafforzato lo switch tra Team 543 / 2026/2027 e Team 469 / 2025/2026, preservando soltanto selezioni compatibili con il contesto.

### Unchanged

- Nessuna modifica allo schema, al database PAS Connect o al file Excel incluso.
- Nessuna modifica alla source policy delle metriche e nessuna nuova sync inclusa nella release.

## PAS v4.17.3 - 2026-08-14

### Added

- Introdotto GPExe Athlete Identity Sync tramite roster REST e fallback Athlete detail.
- Aggiunti i metodi pubblici `athletes()` e `athlete(id)` al client REST.
- Aggiunta la persistenza identity-only, indipendente dalla readiness e dalla pubblicazione TeamSession.
- Integrata la strategia roster più detail fallback per gli athlete ID rilevanti mancanti.

### Fixed

- Sostituito il fallback tecnico `GPEXE ATHLETE <id>` quando GPExe REST rende disponibili i nomi reali.
- Rimossa la dipendenza della persistenza anagrafica dal publish di una TeamSession `READY`.
- Eliminato il rischio di downgrade dell'identità nei merge tra sorgenti REST e GraphQL.

### Improved

- Condiviso il merge anagrafico no-downgrade, preservando campi reali già presenti.
- Conservata provenance bounded per identity source in `raw_json`.
- Deduplicati i detail lookup per athlete ID anche tra più TeamSession dello stesso run.
- Rese non bloccanti le failure del roster e dei singoli Athlete detail, senza PII nei diagnostici.

### Validated live

- TeamSession 143261: identità reali persistite 27/27, fallback residui 0/27 e Dashboard con nomi reali 27/27.
- Metriche 143261 invariate: 27 AthleteSession, 27 Track, 189 KPI `rest_v2`, 135 KPI `rest_v2_speed_zone`, 324 KPI totali, Max Speed 27/27, RPE NULL 27/27 e zero duplicati.
- Roster: 100 record, 3/27 target risolti bulk e 24 detail fallback completati con successo su 24.

## PAS v4.17.2 - 2026-08-14

### Fixed

- Corretti i grafici di dettaglio che in contesto GPExe usavano ancora il catalogo globale `METRICS`.
- Rese selezionabili nei grafici di dettaglio le Speed Zones dinamiche del Team e della stagione correnti.
- Rimosse dal selettore GPExe le metriche legacy e Firstbeat non disponibili per il provider.
- Normalizzato lo state `dashboard_detail_metrics` al cambio di provider o Team, eliminando le selezioni stale.

### Improved

- Condiviso il catalogo metrico contestuale tra overview e grafici di dettaglio.
- Applicati metadata provider-aware e dataset GPExe contestuale ai grafici.
- Estesi confronto giocatori e Media Team alle metriche contestuali e dinamiche.

### Validated

- Team 543 / TeamSession 143261: 12 opzioni, 7 scalar e 5 zone dinamiche (`<10`, `10–16`, `16–20`, `20–25`, `>25 km/h`).
- Team 469 / TeamSession 121408: 11 opzioni, 7 scalar e 4 zone dinamiche (`<14.4`, `14.4–19.8`, `19.8–25.2`, `>25.2 km/h`).
- Percorso Excel invariato.

## PAS v4.17.1 - 2026-08-13

### Fixed

- Eliminato il fallback indebito a Excel quando una TeamSession GPExe contiene dati prestativi REST persistiti ma nessuna riga legacy.
- Impedito che label `Athlete` vuote fondano tutti gli atleti nello stesso `groupby`, lasciando vuoto il Player Selector.
- Ripristinate 27 opzioni selezionabili nel Player Selector REST-only e normalizzato lo state del Player Overview quando il giocatore precedente non appartiene al contesto corrente.
- Normalizzata `dashboard_reference_date` sulle date realmente disponibili e corretta la semantica dello stato vuoto del multiselect TeamSession.
- Corretto l'ordine di inizializzazione di Dynamic Speed Zones e `metric_groups`.

### Improved

- Esteso il performance bridge alle TeamSession REST-only senza righe legacy, mantenendo le colonne consumate dal PAS Core.
- Aggiunto il fallback source-aware della label atleta: nome reale, `player_name`, quindi `GPEXE ATHLETE <id>`.
- Normalizzati gli state Dashboard relativi a Player Selector e Player Overview tra provider e contesti differenti.

### Validated

- TeamSession 143261: 27 AthleteSession, 27 Track, 189 KPI `rest_v2`, 135 KPI `rest_v2_speed_zone`, 324 KPI totali, Max Speed 27/27 e zero duplicati.
- TeamSession 121408 invariata: 23 `identifierKpi`, 299 `kpi`, 138 `rest_v2`, 92 `rest_v2_speed_zone`, 552 KPI totali.
- Schema PAS Connect invariato alla versione 12 e database Excel incluso byte-identico.

## PAS v4.17.0 - 2026-08-13

- Introdotto un resolver centrale di metriche GPExe con descriptor canonico, unità, accumulation, source e provenance; la risoluzione avviene per AthleteSession e canonical metric.
- Formalizzata la precedence `rest_v2` primaria con fallback `identifierKpi` / `kpi` soltanto quando la riga REST è assente. Una riga REST `NULL` mantiene ownership e non viene sostituita; nessun valore viene sommato o fuso cross-source.
- Attivato il contratto REST validato di `max_values_speed`: provider `m/s`, canonico **Max Speed** in `km/h`, conversione `×3.6`, accumulation `max`, valore zero valido e provenance completa. Max Speed resta opzionale per la readiness.
- Proiettati nel DataFrame PAS i sette scalar REST: Distance, Duration, Acc Events, Dec Events, Speed Events, RPE e Max Speed, preservando le colonne consumer esistenti e il percorso Excel.
- Integrati Panoramica GPExe, Dashboard, Session Report e PDF Session Report con scalar source-aware e Dynamic Speed Zone Distance contestuali, senza aggiungere le zone alle `METRICS` globali.
- Ricostruite le zone dagli snapshot storici `rest_v2_speed_zone`, ordinate per bounds e visualizzate con label Unicode reali; mantenuta la separazione fra Team 469 (`19.8–25.2` / `>25.2`) e Team 543 (`20–25` / `>25`).
- Preservata la compatibilità Excel legacy per Z3, Z4 e Max Speed già in km/h, senza reinterpretazione dei bounds o doppia conversione. GraphQL legacy resta fallback deterministico e viene preservato dal replacement source-aware.
- Documentato il comportamento di migrazione: le sessioni REST sincronizzate prima della v4.17 possono non contenere Max Speed. Non viene eseguito alcun backfill automatico; una futura sincronizzazione REST READY aggiornerà `rest_v2` senza eliminare GraphQL o speed zones.
- HTTP 202 / `processing` resta uno stato operativo provider-side: PAS non pubblica bundle incompleti. TeamSession 143261 mantiene lo snapshot v4.16 con sei scalar REST finché GPExe non restituirà READY.
- Restano fuori scope Performance Research avanzata, Performance Model, Period Load, Match Cycle/Report, PAS Intelligence, Load Index, Drills, Forecast ed Exercise Library/Planner.
- Nessuna migrazione: schema PAS Connect 12. Database Excel incluso byte-identico.

## PAS v4.16.0 - 2026-08-13

- Introdotto il mapping dinamico delle **GPExe Speed Zone Distance** dai bounds REST reali, con conversione delle soglie da `m/s` a `km/h` e label canoniche contestuali a Team e stagione.
- Aggiunto lo snapshot storico per metrica con bounds originali e canonici, unità provider/canoniche, contesto Team/Season/TeamSession/AthleteSession, `metric_family` e `provider_zone_number` conservato esclusivamente come provenance.
- Resa l'identità delle speed zone indipendente da `zone_number` e ordine del payload; bounds coincidenti producono la stessa identità, mentre configurazioni differenti restano semanticamente separate.
- Distinte esplicitamente le soglie legacy `19.8–25.2 km/h` / `>25.2 km/h` dalle soglie `20–25 km/h` / `>25 km/h`, senza interpolazione o ricostruzione parziale. La compatibilità Excel è consentita soltanto per bounds esattamente coincidenti.
- Implementato il replacement KPI source-aware: REST sostituisce soltanto `rest_v2` e `rest_v2_speed_zone`, mentre GraphQL sostituisce soltanto `identifierKpi` e `kpi`; le source esterne restano preservate con transazione atomica e rollback.
- Validata live la persistenza della TeamSession 121408 con 138 KPI `rest_v2` e 92 `rest_v2_speed_zone`, e della TeamSession 143261 con 162 KPI `rest_v2` e 135 `rest_v2_speed_zone`, senza duplicati e con isolamento cross-session.
- Il secondo publish live di idempotenza su 143261 è stato impedito esclusivamente da HTTP 202 `processing/not ready` provider-side; idempotenza e source isolation restano coperte dai test automatici.
- Validato per una release successiva il contratto `max_values_speed`: provider `m/s`, canonico **Max Speed** in `km/h`, conversione `×3.6`, accumulation `max`. La metrica resta intenzionalmente inattiva in v4.16.0.
- Nessuna migrazione: `SCHEMA_VERSION` resta 12. Nessuna modifica a statistiche o consumer UI; il database Excel incluso resta byte-identico.

## PAS v4.15.0 - 2026-08-13

- Integrata l'API REST v2 ufficiale GPExe con autenticazione dedicata e client separato dal percorso GraphQL legacy/internal.
- Implementati contratti reali per TeamSession detail, AthleteSession list e AthleteSession detail, fixture anonimizzate, mapping provider-neutral e bundle builder interamente in memoria.
- Aggiunto il persistence gate: pubblica esclusivamente bundle `READY` e preserva atomicità, rollback, idempotenza, isolamento Team/stagione, membership atleta–Team–stagione e provenance `REST v2`.
- Collegato il transport REST al Full Sync tramite `run_full_sync()` e aggiunto il selector esplicito **REST ufficiale** / **GraphQL legacy/internal**, senza fallback automatico REST→GraphQL, GraphQL→REST o verso Excel.
- Estesi run history, risultati per sessione e riepilogo ultimo sync con transport, status, readiness e stati `READY`, `INCOMPLETE`, `FAILED` e `processing`.
- Gestito HTTP 202 come `processing/not ready`, senza pubblicazione né polling aggressivo; preservato `Retry-After` e applicato il rate limit ufficiale di 40 richieste/minuto con esecuzione seriale.
- Attivate come metriche canoniche REST esclusivamente **Distance**, **Duration**, **Acc Events**, **Dec Events**, **Speed Events** e **RPE**, preservando `NULL` per RPE assente.
- Mantenute inattive **Max Speed**, **Distance 19.8–25.2 km/h**, **Distance >25.2 km/h**, **Anaerobic Threshold Zone**, **High Intensity Training** e le metriche provider sconosciute. Max Speed resta sospesa finché l'unità non sarà confermata; le speed zones richiedono mapping dinamico per Team/stagione in una release successiva.
- Validati live Full Sync REST, persistenza atomica e idempotenza sulla TeamSession 143261: 27 AthleteSession, 27 Track, 162 KPI REST v2 e 27 membership nella stagione 2026/2027.
- Nessuna migrazione: `SCHEMA_VERSION` resta 12. Il database Excel incluso è rimasto byte-identico e la compatibilità Streamlit Cloud è preservata.

## PAS v4.14.0 - 2026-08-11

- Semplificata la pagina Strumenti → PAS Connect con una vista principale dedicata al flusso quotidiano: sorgente, connessione, Team/stagione/date/TeamSession, Full Sync e riepilogo sintetico dell'ultimo risultato.
- Raccolte le funzioni meno frequenti negli expander chiusi `Opzioni GPExe` e `Avanzate / Diagnostica`, preservando chiavi e comportamento dei widget esistenti.
- Reso l'uploader visibile soltanto in modalità `File export`; rimossi dalla vista principale gli import manuali già coperti dall'orchestratore GraphQL.
- Raccolti i quattro flussi REST storici in `Legacy — sola lettura`, mantenendoli disabilitati senza riattivarne il comportamento.
- Nessuna modifica a schema o dati PAS Connect, query e sync GPExe, fallback KPI, database Excel, Dashboard, calcoli, report, Drills o Planner.
- Aggiunti test di contratto UI per layout, visibilità condizionale, riepilogo sync, diagnostica embedded e isolamento dei controlli legacy.

## PAS v4.13.0 - 2026-08-11

- Sostituito il percorso Full Sync operativo con orchestrazione GraphQL contestualizzata; il vecchio flusso REST non viene riattivato.
- Aggiunto tracing redatto C-01…C-05 per TeamSessionAthletesession, senza credenziali o header sensibili.
- Introdotte le migrazioni additive PAS Connect 10→11→12: risultati per TeamSession, stati terminali, readiness, contesto run, audit retry e relazione contestuale atleta–Team–stagione.
- Implementato UPSERT atomico per bundle TeamSession, rollback e protezione dell'ultimo dato READY, con import ripetuto idempotente/SKIPPED.
- Aggiunti retry singolo e retry degli errori e diagnostica Sync read-only.
- Reso il contesto GPExe locale Team/stagione/data/sessione indipendente da Excel; rimosso il filtro roster Hellas dal percorso GPExe.
- Mantenuta `gpexe_athletes` come anagrafica provider e spostata l'appartenenza contestuale nella relazione atleta–Team–stagione, preservando il Team legacy e gli atleti condivisi tra contesti.
- Validata live TeamSession 143261 del Team 543, stagione 2026/2027, data 31/07/2026: i resolver GPExe `identifierKpi` e `kpi` falliscono lato provider con ID vuoto per tutte le 27 AthleteSession.
- Aggiunto il fallback controllato che, soltanto quando gli errori sono confinati ai resolver KPI, pubblica 27 AthleteSession e 27 Track con stato `PARTIAL`, readiness `INCOMPLETE`, KPI zero e diagnostica `provider KPI error`, senza inventare KPI e senza fallback Excel.
- Aggiunti test v4.13.0 per orchestrazione, variabili/tracing, schema, rollback, idempotenza, retry, multi-Team e contratti UI.

## PAS v4.12.0 - 2026-08-04

- Resa provider-aware la Panoramica del giorno per Duration, Distance, Acc Events, Dec Events, Max Speed, Speed Events e metriche a soglia dotate di profilo verificato.
- Normalizzata Duration internamente in secondi dal `totalTime` AthleteSession verificato, mantenendo la visualizzazione storica in minuti.
- Con GPExe la Panoramica legge esclusivamente PAS Connect e non usa fallback silenziosi a Excel.
- Le metriche Firstbeat mostrano uno stato provider esterno; metriche e profili mancanti restano N/D con messaggio leggibile.
- Aggiunta nei Developer Tools la copertura read-only della Panoramica e ampliata Bridge Validation alle metriche integrate, senza modificare Distance e Relative Distance.
- Aggiornato Metric Usage Registry esclusivamente in base agli utilizzi verificati nel codice.

## PAS v4.11.0 - 2026-08-04

- Implementato e validato il provider GPExe di Relative Distance, disponibile nel Data Provider comune per le future integrazioni operative dedicate a Drills e Match.
- La sorgente GPExe usa esclusivamente PAS Connect e il Metric Catalog, con filtri per data, Team, TeamSession e atleta e senza fallback Excel.
- Estesa Bridge Validation alla Relative Distance con tolleranza configurabile e righe presenti in una sola sorgente separate.
- Spostati Distance Pilot e Bridge Validation in Settings → PAS Connect → Developer Tools.
- La Panoramica del giorno resta invariata e non introduce una nuova card Relative Distance.
- Excel resta la sorgente predefinita e la selezione della sorgente resta manuale.

## PAS v4.10.0 - 2026-08-04

- Aggiunta la migrazione additiva schema 9 con tabella `pas_metric_usage` e UPSERT non distruttivo.
- Estesa la migrazione allo schema 10 con stato di validazione `VERIFIED`, `PROBABLE`, `AMBIGUOUS` o `MANUAL` e compatibilità con le associazioni già salvate.
- Aggiunta in PAS Connect la sezione **Utilizzo metriche PAS** con filtri, conteggi, creazione e aggiornamento senza eliminazione.
- Aggiunto il censimento read-only con provenienza file/riga e confidenza verificata, probabile o ambigua.
- Censiti Distance, MPE Rec Avg Time e gli utilizzi reali delle metriche Firstbeat, senza mapping provider inventati.
- Segnalate metriche senza utilizzo e associazioni orfane senza cancellazioni automatiche.
- Nessuna modifica al comportamento di Dashboard, Drills, Match Analysis, report, grafici o calcoli.

## PAS v4.9.0 - 2026-08-04

- Integrata la Distance certificata nella sola Panoramica giornaliera della Dashboard tramite il Data Provider comune.
- Il provider GPExe legge esclusivamente il database PAS Connect, usa il Catalogo metriche e aggrega per atleta e giornata senza mescolare righe Excel.
- Aggiunti filtri per data, Team, TeamSession e atleta, conversione km→m e deduplicazione per AthleteSession già garantita dal bridge.
- Aggiunti messaggi distinti per giornata assente, Distance assente e Drill non supportato, senza fallback silenzioso a Excel.
- Aggiunto il confronto tecnico giornaliero Excel/GPExe per atleta, con tolleranza e record presenti in una sola fonte separati.
- Excel resta predefinito e la selezione della sorgente resta esclusivamente manuale; nessuna scrittura nei database e nessuna modifica a report, grafici o calcoli.

## PAS v4.6.0 - 2026-08-04

- Aggiunta la vista interna di sviluppo **Bridge Validation** per il confronto Distance Excel/GPExe.
- Limitato il confronto alle sedute comuni per data e, quando presente in entrambe le sorgenti, TeamSession ID.
- Aggiunti confronto per atleta, differenza assoluta, stato OK/DIFFERENTE ed evidenziazione automatica.
- Aggiunto riepilogo di sedute e atleti confrontati, coincidenti e differenti.
- Elencate separatamente le sedute presenti in una sola sorgente, senza classificarle come errore.
- Nessuna modifica a Dashboard, report, grafici, calcoli, database Excel o dati PAS Connect.

## PAS v4.5.0 - 2026-08-04

- Esteso il Data Provider comune con il contratto canonico della metrica pilota Distance.
- Aggiunta la vista isolata **Distance Pilot**, alimentata dal provider Excel esistente oppure esclusivamente dal database PAS Connect quando è selezionato GPExe.
- Mantenuta Excel come sorgente predefinita e rimossa ogni modifica automatica della sorgente selezionata.
- Aggiunti test di equivalenza Excel/GPExe per Distance, deduplicazione KPI e conversione chilometri/metri.
- Nessuna modifica alle altre Dashboard, ai report, ai grafici, ai calcoli, al database Excel o ai dati PAS Connect.

## PAS v4.4.0 - 2026-08-04

- Implementata la query ufficiale `Athletes` con modalità Current, Expired e Tutti, paginazione e deduplicazione.
- Aggiunto il campo opzionale **Club ID GPExe** per Expired/Tutti, precompilato dai dati Team quando disponibile e con invalidazione mirata dello stato Athletes.
- Implementata `TeamSessionAthletesession` con Template ID, Drill e Fields Limit opzionali.
- Aggiunte migrazioni SQLite additive per Athletes, Athlete Sessions e Tracks e la tabella KPI dinamici normalizzata.
- Aggiunti UPSERT per Athletes, Athlete Sessions e Tracks e sostituzione transazionale dei KPI per evitare duplicati.
- Resi operativi in PAS Connect recupero, selezione, riepilogo e importazione locale dei nuovi dati GPExe.
- Nessun collegamento a Dashboard, report, grafici, calcoli o Match Analysis; database Excel invariato.

## PAS v4.3.1 - 2026-08-04

- Allineate `TeamSelector` e `GetTeamSessions` alle query GraphQL ufficiali catturate dal portale GPExe.
- Corretta la lettura dei risultati da `data.res.content` e la paginazione mediante `first`, `skip` e `data.res.count`.
- Rimossi gli argomenti GraphQL non verificati `offset`, `pageSize` e `after` e ogni gestione cursor-based.
- Aggiunta diagnostica sicura per HTTP 400 con operationName, status ed eventuali errori GraphQL redatti.
- Aggiunto in PAS Connect il filtro Team **Attivi / Scaduti / Tutti**, con deduplicazione per ID e invalidazione mirata di Team e TeamSession al cambio filtro.
- Nessuna modifica a UI PAS Connect, database Excel, Dashboard, report, grafici, calcoli o pipeline dati.

## PAS v4.3.0 - 2026-08-04

- Implementate esclusivamente le query GraphQL verificate `TeamSelector` e `GetTeamSessions` nel provider GPExe.
- Resi operativi in PAS Connect il menu Team, l'intervallo date precompilato sugli ultimi 7 giorni e il recupero delle TeamSession.
- Aggiunta tabella TeamSession con selezione multipla e importazione nel database SQLite locale PAS Connect.
- Mantenuti disabilitati Athletes, Tracks e metriche dinamiche con il messaggio “Funzione disponibile in una release successiva.”
- Aggiunti test per query e variabili GraphQL, errori GraphQL, risposte vuote, Team senza sessioni, timeout, risposta non JSON e persistenza locale.
- Nessuna modifica a database Excel, Dashboard, report, grafici, calcoli o Match Analysis.

## PAS v4.2.0 - 2026-08-03

- Sostituito il flusso di autenticazione REST presunto con il client dedicato `GPExeGraphQLClient` e la mutation verificata `TokenAuth` inviata via `POST` JSON.
- Configurato l'endpoint GraphQL predefinito `https://e15.gpexe.com/ui/v2/`, mantenendolo modificabile da PAS Connect e Streamlit Secrets.
- Gestiti `token`, `refreshToken`, `isActive`, timeout, retry prudenti, errori HTTP, risposte non JSON, errori GraphQL e struttura `data` non valida.
- Protetta la diagnostica da password, token, refresh token, cookie e header `Authorization`.
- Mantenuta Excel come sorgente predefinita e mantenuti separati provider Excel e GPExe.
- Scollegati dalle analisi i dati API GPExe derivati da query non verificate; gli export GPExe restano disponibili separatamente.
- Disabilitati i controlli Team, TeamSession e sincronizzazione con il messaggio “Query GraphQL Team/TeamSession da acquisire e verificare.”
- Non implementate query GraphQL Team, TeamSession, Athletes, Categories, Tags o Tracks.
- Nessuna modifica a database Excel, calcoli, dashboard, grafici o report.

# v4.0.0 — GPExe Foundation

- Aggiunto `GPExeClient` resiliente con autenticazione `/auth/token` e gestione token.
- Aggiunta gestione di timeout, errori di rete, 401 con rinnovo, 429, retry HTTP temporanei e 202 Accepted con polling.
- Aggiunti servizi API Teams, TeamSessions, Athletes, Categories, Tags e Tracks.
- Aggiunto `GPExeAPIDataProvider`, separato dal provider Excel.
- Esteso PAS Connect con login, test connessione, recupero Team e TeamSession in sola lettura.
- Nessuna modifica a calcoli, report, dashboard o database Excel.

## v3.9.2

### Modificato
- Configurato il GPExe API Connector sull’istanza fornita `https://e15-ui.gpexe.com/api`.
- Normalizzata centralmente la base URL preservando il prefisso `/api` durante la composizione degli endpoint REST `/rest/v2/...`.
- Aggiornati PAS Connect e l’esempio Streamlit Secrets con l’indirizzo dell’istanza reale.
- Mantenuti autenticazione runtime tramite token oppure username/password, test connessione, recupero Team Sessions e sincronizzazioni già disponibili.

### Verificato
- Composizione degli endpoint Team e Team Sessions sull’istanza indicata.
- Credenziali non persistite nei file del progetto.
- Database Excel incluso invariato.
- Calcoli, Dashboard, grafici e report non modificati.
- Compatibilità Streamlit Cloud preservata.

## v3.9.1

### Modificato
- Spostato il caricamento degli export GPExe nel pannello **Settings → PAS Connect**.
- Aggiunto stato esplicito per export GPExe attivo e fallback Excel in assenza di file.
- Sostituito il controllo stretto delle card con la checkbox orizzontale **Aggiungi box plot al report**.
- Mantenuti i dettagli giocatori nella tendina chiusa per impostazione predefinita.

### Verificato
- Import del CSV GPExe reale con separatore `;`.
- Database Excel incluso invariato.
- Calcoli, grafici e report non modificati.
- Compatibilità Streamlit Cloud preservata.

## v3.8.9

### Aggiunto
- GPExe Import Engine per export JSON, CSV e XLSX.
- Importazione canonica in memoria con validazione per record.
- Errore controllato predisposto per il fallback Excel.

### Invariato
- GPExe non alimenta ancora il PAS Core.
- Nessuna modifica a calcoli, grafica, report, filtri o database Excel.

## v3.8.7

### Modificato
- Completata l'orchestrazione del PAS Data Provider con catalogo centralizzato, metadati comuni e factory unica.
- Separati provider richiesto e provider effettivo tramite una selezione esplicita e testabile.
- PAS Connect genera le opzioni dal registro dei provider.
- Se viene selezionato GPExe, il fallback controllato mantiene Excel come provider effettivo.

### Invariato
- GPExe resta intenzionalmente non operativo nel PAS Core.
- Nessuna modifica a calcoli, grafica, report, filtri o dati.
- Database Excel incluso completamente invariato.
- Compatibilità con Streamlit Cloud preservata.

## v3.8.6

### Modificato
- Aggiunta nel pannello **PAS Connect** la selezione della sorgente dati con **Excel** predefinito.
- **GPExe** è disponibile come opzione infrastrutturale ma resta non operativo; selezionandolo il PAS informa che continua a utilizzare Excel.
- Nei report, valori e percentuali vengono allineati a sinistra dall'inizio della barra solo quando il testo centrato oltrepasserebbe il bordo sinistro della colonna; in caso contrario restano centrati.
- Mantenute le dimensioni maggiorate correnti di **Team Average** nel Session Report e **Total Match**.

### Invariato
- Nessuna modifica ai calcoli, alla grafica, alla struttura o ai contenuti dei report.
- Database Excel incluso completamente invariato.
- Compatibilità con Streamlit Cloud preservata.

## v3.8.5

### Modificato
- La reportistica PAS riceve ora il dataset prestativo tramite il contratto dedicato del PAS Data Provider.
- `ExcelProvider` resta il provider operativo e predefinito, preservando filtro rosa, contenuto e logica di caricamento esistenti.
- `GPExeProvider` espone lo stesso punto di accesso Report ma rimane intenzionalmente non operativo.

### Invariato
- Nessun cambiamento a grafica, impaginazione, etichette, calcoli o contenuti dei report.
- Nessun modulo utilizza ancora GPExe come sorgente operativa.
- Database Excel incluso completamente invariato.

## v3.8.4

### Modificato
- La sezione Forecast carica `Esercitazioni Avg` tramite un contratto dedicato del PAS Data Provider.
- `ExcelProvider` resta il provider operativo e predefinito; `GPExeProvider` espone lo stesso contratto ma rimane non operativo.
- Nei report tabellari, valori e percentuali restano centrati nella barra finché rientrano nella colonna; se il testo centrato supererebbe i bordi, viene allineato a sinistra dall'inizio della barra colorata.

### Invariato
- Nessun cambiamento ai calcoli, alla palette, alle dimensioni dei caratteri o alla struttura dei report.
- Nessun modulo utilizza ancora GPExe come sorgente operativa.
- Database Excel incluso completamente invariato.

## v3.8.3

### Modificato
- La sezione Match Analysis riceve ora il dataset completo tramite il contratto dedicato del PAS Data Provider.
- `ExcelProvider` resta il provider operativo e predefinito, preservando lo stesso caricamento senza filtro roster richiesto dalle analisi partita.
- `GPExeProvider` espone lo stesso punto di accesso Match Analysis ma rimane intenzionalmente non operativo.

### Invariato
- Nessun cambiamento a grafica, filtri, calcoli, selezione giocatori o report Match Analysis.
- Performance Model continua a utilizzare lo stesso dataset partita già caricato.
- Nessun modulo utilizza ancora GPExe come sorgente operativa.
- Database Excel incluso completamente invariato.

## v3.8.2

### Modificato
- La sezione Drills carica ora le tabelle `Esercitazioni` e `Esercitazioni Avg` tramite il contratto dedicato del PAS Data Provider.
- `ExcelProvider` resta il provider operativo e predefinito, preservando lo stesso contenuto e la stessa logica di caricamento.
- `GPExeProvider` espone lo stesso punto di accesso Drills ma rimane intenzionalmente non operativo.

### Invariato
- Nessun cambiamento a grafica, filtri, calcoli, box plot o report Drills.
- Nessun modulo utilizza ancora GPExe come sorgente operativa.
- Database Excel incluso completamente invariato.

## v3.8.1

### Modificato
- Dashboard confermata sul PAS Data Provider con Excel come provider operativo predefinito.
- Dimensione uniforme delle etichette numeriche nelle barre dei report tabellari, senza riduzione automatica sulle barre corte.
- Percentuale Max Speed allineata al centro della relativa barra, come il valore Max Speed.
- Valori `TEAM AVERAGE` del Session Report ingranditi allo stesso livello di `TOTAL MATCH`.

### Invariato
- Nessun cambiamento a calcoli, dati, palette, struttura dei report o funzionalità esistenti.
- GPExe resta predisposto ma non collegato ai moduli operativi.
- Database Excel incluso completamente invariato.

## v3.8.0

### Aggiunto
- Livello unico `PASDataProvider` per l'accesso ai dati del PAS Core.
- `ExcelProvider` operativo e predefinito, basato sulla logica Excel esistente.
- `GPExeProvider` predisposto con lo stesso contratto, non ancora collegato ai moduli operativi.
- Test automatici dedicati alla selezione del provider e al blocco controllato di GPExe.

### Invariato
- Tutti i moduli continuano a leggere da Excel.
- Database Excel incluso, dati, grafica, report, analisi e calcoli non vengono modificati.
- Compatibilità con Streamlit Cloud mantenuta.

## v3.7.45

### Aggiunto
- Pulsante unico `Sincronizzazione completa GPExe`.
- Orchestratore sequenziale per anagrafiche, Team Sessions, dettagli Team Sessions e Athlete Sessions.
- Barra di avanzamento, log runtime e riepilogo finale dei record sincronizzati.
- Test automatico end-to-end della pipeline con client GPExe simulato.

### Invariato
- Excel resta la sorgente dati operativa.
- Database Excel, Dashboard, analisi e report non vengono modificati.

## v3.7.44

### Aggiunto
- Sincronizzazione del dettaglio delle Athlete Sessions tramite `GET /rest/v2/session/athlete/{id}/`.
- Collegamento stabile fra Athlete Session e Team Session già importata.
- Tabella SQLite `gpexe_athlete_session_details` con metriche scalari, zone e payload grezzo.
- Upsert sugli ID GPExe, conteggi di record nuovi/aggiornati ed errori per singola sessione atleta.
- Comando `Sincronizza Athlete Sessions GPExe` nel pannello PAS Connect.
- Test di regressione dedicati al mapping dinamico e alla persistenza.

### Invariato
- Excel resta la sorgente operativa del PAS.
- Dashboard, report, filtri e analisi non utilizzano ancora i dati GPExe.
- Database Excel incluso non modificato.

## Versione 3.7.43

### Dettaglio Team Sessions GPExe
- Aggiunto il comando **Sincronizza dettagli Team Sessions GPExe**.
- Importazione da `GET /rest/v2/session/team/{id}/?all_params=true`.
- Normalizzazione dinamica delle metriche tramite gli header restituiti da GPExe, senza indici fissi.
- Salvataggio separato di dettaglio sessione, intestazioni metriche e righe atleta nel database PAS Connect.
- Sincronizzazione limitata alle Team Sessions ancora prive di dettaglio, con log degli errori per sessione.
- Excel resta la sorgente dati operativa; Dashboard, analisi e report restano invariati.

## Versione 3.7.42

### Sincronizzazione Team Sessions GPExe
- Aggiunto il comando **Sincronizza Team Sessions GPExe** nel pannello PAS Connect.
- Importazione da `GET /rest/v2/session/team/` con paginazione e filtro incrementale `updated_on_gte`.
- Le Team Sessions vengono normalizzate e salvate tramite upsert nella tabella `gpexe_team_sessions`.
- Il registro sincronizzazioni indica record ricevuti, nuovi e aggiornati.
- Excel resta la sorgente dati operativa; Dashboard, analisi e report restano invariati.

## Versione 3.7.41

### Database PAS Connect per anagrafiche GPExe
- Teams, Categories, Tags e Athletes sincronizzati vengono salvati anche in `.pas_data/pas_connect.sqlite3`.
- Aggiunte tabelle SQLite dedicate e aggiornamento tramite upsert sugli ID stabili GPExe, senza duplicati.
- Aggiunto registro delle sincronizzazioni con stato, data/ora e conteggi importati.
- La snapshot JSON resta disponibile come copia diagnostica.
- Il database Excel operativo, Dashboard, analisi e report restano invariati.
- Su Streamlit Community Cloud il database locale è effimero e viene ricreato dopo reboot/deploy; una persistenza cloud esterna sarà introdotta successivamente.

## Versione 3.7.40

### Prima sincronizzazione anagrafica GPExe
- Aggiunto il comando **Sincronizza anagrafiche GPExe** per Teams, Categories, Tags e Athletes.
- Le risposte API vengono normalizzate nello schema PAS e salvate in `.pas_data/gpexe_snapshot.json`.
- La snapshot è separata dal database Excel, non contiene credenziali ed è esclusa da Git.
- Aggiunti riepilogo dei record sincronizzati, paginazione e test automatici senza chiamate di rete reali.
- Excel resta la sorgente operativa del PAS; nessuna analisi usa ancora la snapshot GPExe.

## [3.7.39] - 2026-08-03

### Aggiunto
- Connessione GPExe persistente nella sola sessione runtime.
- Stato visibile **Connesso / Non connesso** nel pannello Settings.
- Comandi **Connetti a GPExe** e **Disconnetti GPExe**.
- Verifica dell'accesso Teams e memorizzazione runtime del numero di team rilevati.

### Sicurezza
- Token e credenziali non vengono scritti nei file o nel repository.

### Invariato
- Excel resta la sorgente dati operativa; nessuna sincronizzazione o modifica al database incluso.

## [3.7.38] - 2026-08-03

### Aggiunto
- Pannello **PAS Connect · GPExe** in Settings.
- Autenticazione tramite token oppure username/password.
- Test reale della connessione con verifica dell’accesso all’endpoint Teams.
- Supporto a `st.secrets` per le credenziali su Streamlit Cloud.
- Token ottenuto tramite login conservato esclusivamente nella sessione runtime.

### Invariato
- Excel resta la sorgente dati operativa; nessuna sincronizzazione o modifica al database incluso.

## [3.7.37] - 2026-08-03

### Corretto
- Ripristinato il colore primario rosso PAS (`#D71920`) nei componenti Streamlit.
- Pulsanti, selezioni e controlli interattivi tornano al contrasto precedente.

### Invariato
- Architettura PAS Connect, caricamento Excel, analisi, report e database incluso.

## [3.7.36] - 2026-08-03

### Aggiunto
- Fondamenta del livello `pas_connect` indipendente dal PAS Core.
- Configurazione provider con Excel predefinito e GPExe predisposto ma non attivo.
- Catalogo degli endpoint GPExe documentati, gestione token e client REST basato sulla libreria standard.
- Mapper iniziali per team, atleti, categorie, tag e tabelle metriche posizionali guidate dagli header.
- Piano di sincronizzazione ordinato e documentazione tecnica in `docs/`.
- Test automatici della PAS Connect Foundation senza accesso alla rete.

### Invariato
- Caricamento Excel, interfaccia, analisi, report e database incluso.

## [3.7.35] - 2026-08-03

### Corretto
- Match Report: stemmi resi visibili su badge chiaro ad alto contrasto, inclusi loghi scuri.
- Match Report: parsing dell’avversario compatibile con le etichette reali della Match Analysis.
- Match Report: limite massimo della scala posizionato vicino al maggiore tra valore reale e target, con margine del 5% dell’intervallo utile.
- Invariati calcoli, target e database.

## [3.7.34] - 2026-08-03

### Changed
- Match Report: scala minima 80 per Relative Distance e 5 per MPE REC AVG TIME.
- Match Report: valore e target individuale sono rappresentati sulla stessa scala con minimo specifico per metrica.
- Match Report: rinominato MATCH TOTAL in TOTAL MATCH.
- Match Report: barre TOTAL MATCH sempre piene e valori più grandi.

## [3.7.33] - 2026-08-03

### Modificato
- Match Report: la scala delle barre include sia il valore reale sia il target individuale, con origine a zero e margine finale del 10%, rendendo proporzionale la distanza grafica tra valore e target.
- L’etichetta numerica del target segue la stessa scala della linea target.
- `MPE REC AVG TIME` è visualizzato con 0 decimali sia nel valore principale sia nell’etichetta del target.
- Invariati calcoli del modello prestativo, dati e altre sezioni del PAS.

## [3.7.32] - 2026-08-03

### Modificato
- Match Report: il valore della metrica è centrato nella barra colorata.
- Match Report: aggiunta una piccola etichetta con il valore del target individuale alla base e a sinistra della linea target.
- Invariati calcoli, dati e altre sezioni del PAS.

## [3.7.31] - 2026-08-02

### Corretto
- Corretto il selettore giocatori della Match Analysis: ogni partita usa una chiave Streamlit dedicata e preseleziona tutti i giocatori disponibili, evitando che rimangano soltanto 7–10 atleti della selezione precedente.
- La Match Analysis legge tutte le righe valide con `Drill = Match`, senza applicare la rosa statica come filtro obbligatorio.
- Mantenuta l'esclusione di `Team Average` e invariata la logica dei Match Total.
- Nessuna modifica al database.

## [3.7.30] - 2026-08-02

### Modificato
- Ridisegnata l’intestazione del Match Report con titolo **MATCH REPORT**, stemmi delle squadre e separatore **VS**.
- Applicato l’ordine casa/trasferta: Hellas Verona per primo nelle gare `(H)`, avversario per primo nelle gare `(A)`.
- Aggiunti gli stemmi degli avversari forniti nella cartella `assets/teams`.
- Gestiti alias dei nomi squadra e fallback testuale quando uno stemma non è disponibile.
- Nessuna modifica alle metriche, ai dati o alle altre funzionalità.

## [3.7.29] - 2026-08-02

### Modificato
- Impostata a **0 decimali** la visualizzazione di Relative Distance nei report PDF tabellari.
- Aggiunta nel Match Report la percentuale di Max Speed sotto al valore assoluto, usando la Max Speed storica individuale come riferimento e lo stesso layout del Session Report.
- Nessuna modifica ai dati, alle formule delle metriche o alle funzionalità non richieste.

## [3.7.28] - 2026-08-02

### Modificato
- Rimossa dalle card della Dashboard la dicitura **“Confronto giocatori del giorno”**.
- Aumentata l’opacità delle barre colorate nei report PDF tabellari, in particolare Session Report, Period Load Report e Match Report.
- Mantenuta invariata la palette PAS: sono stati modificati soltanto intensità e contrasto in stampa.
- Nessuna modifica a calcoli, filtri o database.

## [3.7.27] - 2026-08-02

### Modificato
- Ridisegnata graficamente la Dashboard senza modificare logica e dati.
- Migliorata la gerarchia delle card metriche e organizzate Media, Mediana, SD e CV in micro-box dedicati.
- Resi più compatti badge di stato, riferimento omologo e accumulo.
- Aggiunta una hero compatta alla Panoramica del giorno.
- Alleggerito lo stile dei box plot visualizzati nella Dashboard.
- Mantenuto invariato lo stile dei grafici usati nei report PDF.
- Nessuna modifica al database.

## [3.7.26] - 2026-08-02

### Corretto
- Allineate Media, Mediana, SD e CV delle card Dashboard alla stessa baseline usata per lo scostamento.
- Le statistiche utilizzano soltanto sedute omologhe precedenti con stesso Match Day relativo e stessa Length Cycle.
- Escluso il giorno selezionato dal campione storico.
- Eliminata l'incoerenza tra scostamento e statistiche calcolate su popolazioni differenti.
- In assenza di osservazioni omologhe valide non viene applicato alcun fallback silenzioso su altri periodi.
- Nessuna modifica al database.

## [3.7.25] - 2026-07-31

### Modificato
- Assegnato un colore distinto a ciascun drill nei box plot della pagina **Drills**.
- Introdotta una palette fissa di dieci colori ad alto contrasto, coerente sul tema scuro PAS.
- Resi coerenti con il colore del drill il riempimento, il bordo, i punti, gli outlier e la legenda.
- Mantenuta la stessa associazione drill-colore per tutte le metriche della stessa selezione e per l'esportazione report.
- Limitata a dieci la selezione simultanea dei drill.
- Nessuna modifica al database.

## [3.7.24] - 2026-07-30

### Corretto
- Ripristinata la popolazione del selettore **Drills** usando i nomi reali del foglio `Esercitazioni`, ordinati per frequenza.
- Rimossa dalla pagina Drills la sezione non pertinente **Player drill coverage** e i relativi controlli di soglia/inclusione.
- Aggiunto un messaggio esplicito quando nessun drill è disponibile con i filtri correnti.

### Modificato
- Aggiornato il placeholder di **PAS Intelligence** in **“Cosa vuoi analizzare?”**.
- Aggiornata la chiave del selettore Drills per evitare il riuso di uno stato Streamlit incompatibile con la nuova lista.
- Nessuna modifica al database.

## [3.7.23] - 2026-07-30

### Modificato
- Reso obbligatorio il confronto con sedute omologhe nella Panoramica del giorno: stesso Match Day relativo e stessa Length Cycle.
- Aggiunta nelle card la micro-etichetta `vs media omologa · n=X`, con il numero di giornate valide del riferimento.
- Aggiunto un tooltip compatto con Match Day e Length Cycle usati per il confronto.
- Rimossa l'opzione che consentiva di disattivare il filtro per Length Cycle, evitando benchmark non omogenei.
- Nessuna modifica al database o alle altre sezioni.

## [3.7.22] - 2026-07-30

### Corretto
- Eliminato il taglio dell’header PAS causato dal padding superiore troppo ridotto.
- Portato il padding superiore del contenitore principale da `1rem` a `3.5rem`, mantenendo un layout compatto e compatibile con la toolbar di Streamlit Cloud.
- Funzionalità, dati e struttura della pagina invariati.

## [3.7.21] - 2026-07-30

### Modificato
- Ridotto a `1rem` il padding superiore del contenitore principale Streamlit.
- Avvicinato l’header PAS alla toolbar nativa, eliminando gran parte dello spazio vuoto superiore.
- Mantenuti invariati toolbar, navigazione, sidebar, dati e logiche applicative.

## [3.7.20] - 2026-07-30

### Modificato
- Affiancati **Database** e **Settings** sulla stessa riga della sidebar tramite due pannelli popover compatti.
- Eliminato l'ingombro verticale generato dai due expander separati.
- Spostato nella sidebar il selettore della vista **Match Analysis**.
- Spostati nella sidebar i controlli di partita, giocatori e metriche della vista **Singola partita**.
- Spostati nella sidebar partite, soggetto e metriche della vista **Confronto / Totali partite**.
- Rimossi i tab di Match Analysis dalla pagina, lasciando nel contenuto principale solo risultati, grafici, tabelle e report.
- Logiche di calcolo, report e database invariate.

## [3.7.19] - 2026-07-30

### Modificato
- Spostato **Esci dalla Demo** nel pannello compatto **⚙️ Settings** della sidebar.
- Rimossa l’azione Esci dalla vista principale.
- Aggiunte nel pannello Settings le informazioni essenziali su versione e database attivo.

# Changelog

## 3.7.18

- Ridotta l’area occupata dal pannello Database nella sidebar.
- Eliminato il riepilogo duplicato e mantenuta una sola riga compatta con nome file e ultimo aggiornamento.
- Ridotto il logo nella sidebar e compattata l’intestazione PAS.
- Sostituito il pulsante a tutta larghezza “Esci dalla Demo” con il comando compatto “Esci” in fondo alla sidebar.
- PAS Intelligence è ora chiuso per impostazione predefinita e si apre con un click tramite pannello espandibile.
- Motore PAS Intelligence, dati e funzionalità delle sezioni invariati.
- Database invariato.

## 3.7.17

- Spostata la navigazione principale dalla sidebar alla parte superiore dell’app.
- Le sezioni sono ora disposte orizzontalmente e vanno automaticamente a capo su schermi più stretti.
- La sidebar resta disponibile esclusivamente per database, filtri e controlli contestuali.
- Mantenuta invariata la logica interna di tutte le pagine.
- Database invariato.

## 3.7.16

- Fix: errore `TypeError` nelle Visualizzazioni con più Match Cycle.
- `test_by_level` viene ora gestito correttamente come lista di confronti pairwise.
- Annotazioni di significatività e Performance Score compatibili con due o più gruppi.
- Database invariato.

## 3.7.15
- Corretto il problema per cui la funzione PDF esisteva nel backend ma non era accessibile nella pagina Performance Research.
- Aggiunta la sezione visibile “Stampa grafici” nella scheda Visualizzazioni.
- Aggiunti selettore dei grafici, titolo report, pulsante di generazione e download/stampa PDF.
- Confermato il limite di massimo quattro grafici per pagina.

## v3.7.14

### Aggiunto
- Manifest di release con inventario e checksum SHA-256 dei file distribuiti.
- Test automatico della paginazione PDF con cinque grafici.

### Verifica
- Confermato il limite massimo di quattro grafici per pagina.
- Confermata la presenza di tutti i 14 file Python sorgente.
- Esclusi dall'archivio i soli file temporanei `__pycache__`, non necessari all'esecuzione.
- Database incluso invariato.

## v3.7.13

- Aggiunta impaginazione multipagina dei report grafici PDF, pronta per la stampa.
- Limitati i grafici a un massimo di quattro per pagina A4 orizzontale.
- Implementati layout automatici: uno a tutta pagina, due affiancati, tre o quattro in griglia 2 x 2.
- Mantenute legende e annotazioni di significatività nei grafici esportati.
- Aggiunti numero di pagina e totale grafici nel piè di pagina.
- Database e funzionalità non richieste invariati.

## v3.7.12

- Aggiunte annotazioni di significatività nei grafici con parentesi e legenda scientifica (`ns`, `*`, `**`, `***`, `****`).
- Aggiunti confronti post-hoc pairwise per fattori con più di due livelli, eseguiti dopo un test globale significativo e corretti con metodo Holm.
- Supportati risultati differenziati tra coppie, ad esempio A–B significativo e A–C non significativo.
- Esplicitati nella Performance Interpretation i gruppi tra cui emerge la differenza, anche nel caso di soli due gruppi come S e NS.
- Aggiunta la direzione della differenza tramite confronto delle medie dei due gruppi.
- Database e funzionalità non richieste invariati.

## v3.7.11

- Ripristinato nella pagina Drills, modalità Players, il controllo di copertura per giocatore.
- Aggiunti conteggi basati su giornate uniche per Active Recovery, Individual Training, Return to Play, Full Training, Match e Different Training.
- Aggiunta una soglia minima indipendente per ciascuna delle sei categorie.
- Ripristinata la tabella modificabile con checkbox Include per includere o escludere manualmente ogni giocatore dai grafici.
- Mantenuti esclusivamente i sei drill richiesti nei selettori.
- Database e funzionalità non richieste invariati.

## v3.7.10

- Corretto anche il filtro Drill della Performance Research, che continuava a leggere l’intera tassonomia del database.
- Limitati entrambi i selettori visibili (Performance Research e pagina Drills) alle sole categorie: Active Recovery, Individual Training, Return to Play, Full Training, Match e Different Training.
- Aggiornate le chiavi Streamlit dei selettori per eliminare eventuali valori precedenti conservati nello stato della sessione.
- Mantenuta la normalizzazione della variante `Different Traning` verso `Different Training`.
- Database e funzionalità non richieste invariati.
- Compilazione completa e validazione release eseguite.

## v3.7.9

- Limitato il selettore della sezione Drills alle sole categorie richieste: Active Recovery, Individual Training, Return to Play, Full Training, Match e Different Training.
- Rimossi dal selettore Drills tutti gli altri valori presenti nella tassonomia del database.
- Mantenuta la normalizzazione della variante `Different Traning` verso `Different Training`.
- Database e funzionalità non richieste invariati.
- Compilazione completa e validazione release eseguite.

## v3.7.8

- Esteso il selettore delle sedute nella Performance Research Match Cycle con Active Recovery, Individual Training e Return to Play.
- Aggiunti nella tabella di copertura i conteggi delle giornate uniche per tutte e sei le categorie supportate.
- Aggiunte soglie minime indipendenti per Active Recovery, Individual Training e Return to Play.
- Il totale individuale giocatore-ciclo continua a sommare esclusivamente le categorie selezionate; le categorie non selezionate restano visibili nella tabella di controllo ma non entrano nel calcolo.
- Database e funzionalità non richieste invariati.
- Compilazione completa e validazione release eseguite.

## v3.7.7

- Aggiunto nella Performance Research Match Cycle il selettore delle sedute incluse: Full Training, Match e Different Training, anche in combinazione.
- Il totale individuale giocatore-ciclo somma esclusivamente le categorie selezionate prima dell’analisi descrittiva o del Linear Mixed Model.
- Aggiunta una tabella di controllo con conteggi di giornate uniche Full Training, Match e Different Training, totale sedute e numero di Match Cycle presenti per giocatore.
- Aggiunta l’inclusione/esclusione manuale dei giocatori direttamente dalla tabella.
- Aggiunte soglie minime indipendenti per Full Training, Match e Different Training.
- Il Linear Mixed Model continua a usare il giocatore come random intercept e riceve una sola osservazione aggregata per giocatore, ciclo e livello del fattore selezionato.
- Compilazione completa, validazione release e integrità del database verificate.

## v3.7.6

- Divisa l’analisi Match Cycle in confronto di un singolo ciclo e confronto di più cicli.
- Introdotto un Linear Mixed Model per il confronto multiplo: `totale individuale ~ Match Cycle × fattore principale + (1 | Giocatore)`.
- Il random intercept del giocatore gestisce misure ripetute, presenze variabili e dati non bilanciati tra i cicli.
- Nel Trend LMM, asse X = Match Cycle e linee = livelli del fattore principale, con blu per S e arancione per NS.
- Visualizzate medie marginali stimate, IC95% e numero di giocatori per ciclo/gruppo.
- Aggiunta la dipendenza `statsmodels` compatibile con Streamlit Cloud.
- Database e funzionalità non richieste invariati.

## v3.7.5

- Corretto il Trend delle medie quando Match Cycle è il secondo fattore: asse X = Match Cycle e linee = livelli del fattore principale.
- Supportato un pannello non bilanciato: ogni ciclo utilizza i giocatori realmente presenti dopo l’applicazione dei filtri.
- Confermata l’aggregazione giocatore-ciclo: somma delle giornate per atleta e successiva media dei totali individuali per gruppo.
- Aggiunto al tooltip il numero di giocatori presenti per ciascun punto del Trend.
- Mantenuti invariati database, filtri e funzionalità non richieste.

## v3.7.4

- Modificata la logica Match Cycle nella Performance Research: somma delle giornate per giocatore e ciclo, quindi media dei totali individuali separata tra S e NS.
- Rimossi media e mediana delle singole giornate dal percorso Match Cycle.
- Con più Match Cycle selezionati, asse X per ciclo e linee blu S / arancione NS.
- Conservati tutti i filtri esistenti, inclusi ruolo e giocatori.
- Database e funzionalità non richieste invariati.

## v3.7.3

- Hotfix delle barre di significatività nei raincloud: linee nere e simboli sempre visibili sopra ciascun confronto.
- Colori fissi per gruppi nella Performance Research: Starters blu PAS, No Starters arancione PAS, indipendentemente dalla metrica.
- Trend coerente con il fattore principale sull’asse X e con una linea per ciascun gruppo.
- Linea Team resa opzionale e disattivata di default.
- Totali allineati alla stessa codifica cromatica e ai marker di significatività.
- Database invariato.

## v3.7.2

- Estesi i raincloud alle analisi a due fattori e ai confronti S/NS per Match Cycle.
- Aggiunte barre scientifiche nere con `*`, `**`, `***` e `ns` direttamente sopra i gruppi.
- Aggiunto il trend Starters / No Starters / Team con IC95%.
- Aggiunti totali per ciclo configurabili come Media, Somma o Mediana per ogni metrica.
- Aggiunto selettore per Distribuzione, Trend, Totali o vista completa.
- Potenziata la Performance Interpretation e aggiunto il Performance Score per ciclo.
- Database invariato.

## v3.7.1

- Ripristinati i raincloud plot nella Performance Research.
- Aggiunto il trend dei gruppi nei diversi livelli del fattore principale, con supporto diretto a Starters/No Starters nei Match Cycle.
- Aggiunti confronti automatici tra i livelli del secondo fattore all’interno di ogni ciclo.
- Aggiunti marker di significatività `*`, `**`, `***` nei grafici.
- Rafforzata visivamente la Performance Interpretation per i risultati significativi.
- Database invariato.

## 3.7.0

- Riprogettata Statistical Analysis come Performance Research.
- Introdotto il workflow Metriche → Fattori → Filtri → Analizza.
- Aggiunto riconoscimento automatico del percorso statistico.
- Aggiunti confronti automatici a due gruppi e multi-gruppo con effect size.
- Aggiunta analisi multifattoriale esplorativa stratificata.
- Limitato PAS Intelligence a Dashboard e Period Load.
- Verificata l’esclusione delle percentuali del modello gara per Duration e RPE nel Period Load.
- Mantenute le correzioni dei report S/NS e dei nomi giocatore completi.

## v3.6.0

- Aggiunta la pagina Statistical Analysis.
- Aggiunti confronti tra due gruppi per giocatori, ruoli, S/NS, date e Match Cycle.
- Aggiunte descrittive, Shapiro–Wilk, t-test/Welch, Mann–Whitney, effect size, raincloud plot, istogrammi, dati grezzi e correlazioni.
- Aggiunta interpretazione PAS dei risultati statistici.
- Period Load: rimossa la percentuale del modello gara esclusivamente per Duration e RPE.
- Database invariato.

## v3.5.6

- Hotfix del grafico di dettaglio in Team Overview.
- Corretto l’errore `AttributeError` nella formattazione della media squadra del giorno.
- La media squadra della giornata continua a essere mostrata come rombo dedicato senza alterare box plot e distribuzione dei giocatori.
- Nessuna modifica al database o alle altre funzionalità.

## v3.5.5

- Team Overview: conservato il box plot dello storico squadra e la distribuzione completa dei giocatori della giornata.
- Aggiunto un indicatore dedicato alla media squadra della giornata nel grafico di dettaglio.
- I giocatori selezionati vengono evidenziati senza nascondere gli altri valori della giornata.
- Player Overview: conservato lo storico individuale e la distribuzione completa della squadra, con il giocatore della panoramica evidenziato.
- Nessuna modifica al database o alle altre funzionalità.

## v3.5.4

- Corretto il collegamento tra **Giocatore della panoramica** e grafici di dettaglio.
- Il giocatore selezionato nel Player Overview è ora evidenziato con pallino giallo più grande e nome.
- Conservata la distribuzione completa di tutti i giocatori della giornata.
- Nessuna modifica alle altre funzionalità.

# Changelog

## v3.5.3
- Grafici di dettaglio: mantenuta la distribuzione completa della giornata e giocatore selezionato evidenziato con un pallino giallo più grande, bordo scuro e nome.
- Period Load Report: una sola sigla S e una sola sigla NS, centrate verticalmente rispetto ai rispettivi gruppi.
- Ridotta al minimo la micro-colonna S/NS e aumentato lo spazio utile per il nome del giocatore.
- Period Load Report e Session Report: nomi completi, con adattamento automatico del font alla cella e senza troncamento.

## v3.5.2

- Corretto il Period Load Report: una sola etichetta S e una sola NS, centrate a sinistra dei nomi e non ripetute per giocatore.
- Reso più marcato il separatore orizzontale tra i gruppi S e NS.
- Ripristinata l’intera distribuzione dei giocatori del giorno nei grafici di dettaglio anche quando è selezionato un solo giocatore.
- Il giocatore selezionato resta evidenziato con un rombo giallo più grande e il nome.
- Nessuna modifica al database, al PLI o alle altre funzionalità.


## v3.5.1

### Modificato
- Period Load Report PDF: sostituiti i prefissi ripetuti con una sola etichetta `S` e una sola `NS`, centrate per gruppo.
- Reso più marcato il separatore orizzontale tra Starters e No Starters.
- Aggiunti ai grafici PLI i valori assoluti delle metriche che compongono ciascuna componente e i riferimenti individuali.
- Evidenziati nei grafici di dettaglio i giocatori selezionati con rombo giallo, bordo scuro e nome.

### Verifica
- Compilati tutti i file Python.
- Validazione automatica della release completata.
- Database incluso invariato.

## v3.5.0
- Introdotto il PAS Load Index (PLI) individuale rispetto al modello prestativo di gara.
- Sostituito il precedente indice basato sui ranghi percentili della squadra.
- Modello gara individuale per Distance, alta velocità, sprint, accelerazioni, decelerazioni e Max Speed.
- Duration normalizzata sul riferimento fisso di 90 minuti.
- RPE normalizzato sul riferimento fisso di 8.
- Sei componenti a peso uguale: Volume, Alta velocità, Sprint, Componente neuromuscolare, Velocità massima e Carico interno.
- Grafici e Key Insights aggiornati per mostrare PLI e percentuali del modello gara.
- Period Load Report ordinato S prima di NS, con prefisso S/NS e separatore orizzontale grigio chiaro.
- Database invariato.

## v3.4.1

- PAS Intelligence: confronto visuale Starters (S) vs No Starters (NS) nella Dashboard e in Period Load.
- Due pannelli affiancati con scale coerenti per ranking, soglie, metriche singole e indice multi-metrica.
- Key Insights con media separata dei due gruppi.
- Corretto il parser S/NS per evitare sovrapposizioni tra “Starters” e “No Starters”.
- Nessun nuovo filtro visibile e nessuna modifica ai dati del database.

## v3.4.0
- Aggiunta analisi completa della seduta tramite PAS Intelligence.
- Riconosciute richieste generali sulla seduta corrente.
- Aggiunti grafici di ranking, distribuzione e profilo multi-metrica.
- Key Insights per ogni metrica con massimo, minimo, media, mediana e dispersione relativa.
- Sostituita la terminologia “leader” con “carico maggiore” e formulazioni descrittive equivalenti.
- Nessuna modifica ai dati del database.

## v3.3.9
- Release di stabilizzazione per Streamlit Community Cloud.
- Ricreato e validato `requirements.txt`, senza testo descrittivo o righe non installabili.
- Aggiunto controllo automatico della struttura di release e della compilazione Python.
- Verificati `app.py`, `modules/config.py`, `modules/__init__.py` e i file essenziali nella radice dello ZIP.
- Documentata la selezione di Python 3.12 nelle impostazioni avanzate di Streamlit Cloud.
- Nessuna modifica alle funzionalità e nessuna alterazione del database.

## v3.3.8

- Esteso PAS Intelligence alle richieste sul carico complessivo della giornata.
- Riconosciute le formulazioni “maggior carico”, “carico maggiore”, “carico complessivo” e varianti equivalenti.
- “Chi ha fatto il maggior carico oggi?” restituisce il leader multi-metrica.
- “Fammi vedere i 5 giocatori con maggior carico oggi” restituisce il Top 5.
- Aggiunto grafico sintetico dell’indice di carico 0–100.
- Aggiunto profilo per metrica dei giocatori selezionati su scala percentile comune.
- Aggiunti Key Insights separati per ogni metrica disponibile.
- Nessuna modifica ai dati del database.

## v3.3.7

- Corretto il riconoscimento di `ultimi N giorni` in Period Load.
- Gli intervalli sono inclusivi dell'ultimo giorno disponibile (`N=3` = oggi più i due giorni precedenti).
- Aggiunto il riconoscimento di ultime N settimane, settimana corrente/precedente e mese corrente.
- `km` viene interpretato come Distance quando la richiesta non riguarda velocità o Max Speed.
- Il PAS Intelligence imposta automaticamente l'intervallo di date corrispondente.

# Changelog

## v3.3.6
- Esteso PAS Intelligence alla sezione Period Load.
- Aggiunto riconoscimento di ciclo gara corrente, precedente, ultimi N cicli e cicli nominati.
- Applicazione automatica di Match Cycle, giocatori, ruoli, S/NS e metriche nei totali di periodo.
- Aggiunti grafici contestuali per totali, ranking e confronto tra cicli gara.
- Esteso PAS Intelligence alla sezione Drills con ranking per esercitazione e confronto per giocatore.
- Applicazione interna di cicli gara e S/NS nei Drills senza nuovi filtri visibili.
- Migliorato il riconoscimento di termini come Possession e ciclo gara attuale.
- Database invariato.

## v3.3.5

### Migliorato
- Nella Dashboard, la card Max Speed mostra il valore assoluto in km/h e sotto la percentuale rispetto al massimo individuale.
- Nel confronto giocatori della Dashboard, le etichette Max Speed mostrano su due righe km/h e percentuale individuale.
- Nei grafici PAS Intelligence relativi alla % Max Speed, ogni giocatore mostra sia il valore assoluto sia la percentuale.
- Titoli e tooltip distinguono chiaramente Max Speed (km/h) e % del massimo individuale.

### Verifica
- Compilati tutti i file Python.
- Database incluso lasciato invariato.
- Archivio ZIP verificato.

## v3.3.4

### Corretto
- Risoluzione esplicita della directory radice del progetto prima degli import locali.
- Maggiore robustezza degli import `modules.*` su Streamlit Cloud.

### Verifica
- Confermata la presenza di `modules/config.py` e `modules/__init__.py` nello ZIP.
- Eseguito smoke test degli import da una directory estratta pulita.
- Compilati tutti i file Python.
- Database incluso lasciato invariato.

## 3.3.3

- Corretta la rappresentazione della `% Max Speed individuale`: valori e soglie sono sempre espressi in percentuale, non in km/h.
- Aggiunto il riconoscimento di richieste positive e negative come “ha raggiunto”, “non ha raggiunto”, “ha superato” e “non ha superato”.
- Estesa la stessa semantica di soglia a tutte le metriche supportate dal PAS Intelligence.
- Uniformate etichette, grafici, configurazione applicata e Key Insights.

# Changelog

## 3.3.2

- Riconoscimento testuale di Starters (`S`) e No Starters (`NS`) senza nuovi filtri UI.
- Riconoscimento dei ruoli e dei principali sinonimi italiani nelle richieste PAS Intelligence.
- Aggiunta analisi della percentuale di Max Speed rispetto al massimo storico individuale.
- Supportate soglie percentuali come `oltre l’85% di Max Speed`.
- Aggiunto ranking multi-metrica del carico tramite media dei ranghi percentili con peso uguale.
- Supportate richieste come `i 5 giocatori con il carico maggiore di oggi`.
- Aggiornati grafici prioritari e Key Insights per le nuove condizioni.
- Database invariato.


## 3.3.1

- PAS Intelligence: grafici soglia con intero gruppo visibile.
- Evidenziati con il colore della metrica i giocatori che soddisfano la condizione.
- Nomi corrispondenti evidenziati nel grafico.
- Aggiunta linea della soglia con etichetta.
- Key Insights estesi con elenco dei giocatori sopra/sotto soglia.
- Migliorato il riconoscimento di frasi naturali come “ha superato i 3,5 km”.
- Nessuna modifica al database o alle altre funzionalità.

## 3.3.0
- Mostrato il grafico prioritario immediatamente dopo la richiesta PAS Intelligence.
- Aggiunta memoria controllata del contesto tra richieste successive.
- Aggiunti livello di confidenza, sezione selezionata e configurazione applicata.
- Aggiunte Quick Actions per storico, confronto con il ruolo, Top 5 e vista squadra.
- Aggiunto `modules/pas_knowledge.py` per centralizzare sinonimi delle metriche e regole di navigazione.
- Mantenuto il riuso delle pagine e dei componenti originali del PAS.
- Database invariato.

## 3.2.1
- Rimosso il calendario Planner incorporato dalla Dashboard.
- Rimossi dalla Dashboard la navigazione mensile e il pulsante `Apri Planner`.
- Mantenuta invariata e accessibile dal menu laterale la pagina Planner dedicata.
- Nessuna modifica alle analisi, ai filtri, ai grafici o al database.

## 3.2.0
- Introdotto il primo PAS Intelligence Engine.
- Aggiunta selezione automatica della sezione in base alla richiesta.
- Supportata navigazione verso Dashboard, Drills, Match Analysis, Period Load, Planner, Forecast e Return To Play.
- Aggiunta preconfigurazione controllata di giocatori, ruoli, metriche e drill quando disponibili.
- Mantenuto il riuso dei componenti originali di ciascuna sezione.
- Nessuna modifica ai dati del database.

## v3.1.6

- Rimossi dalla Dashboard il titolo grande `Performance Analysis System — Hellas Verona 2025-26` e la riga informativa del database accanto al Planner.
- Mantenuto invariato il Planner e lasciate disponibili le informazioni sul database nella sidebar.
- Nessuna modifica alle analisi, ai grafici, ai filtri o al database.

## v3.1.5

- Rinominata e ridisegnata la sezione `Chiedi a PAS` come `PAS Analysis`.
- Introdotta una barra operativa compatta con richiesta, metrica, analisi e analisi della giornata sulla stessa riga.
- Rimossi gli elementi visivi da chatbot e ridotto lo spazio verticale occupato.
- Inserito il risultato in un pannello comprimibile, mantenendo Key Insights e componenti originali della Dashboard.
- Nessuna modifica alla logica analitica, alle altre sezioni o al database.

## v3.1.4

- Aggiunti Key Insights contestuali alle richieste di `Chiedi a PAS`.
- Gli insight vengono mostrati nel riquadro della richiesta prima dei componenti originali della Dashboard.
- Supportati insight oggettivi per confronti tra giocatori, storico personale, soglie, Top/Bottom e analisi automatica della giornata.
- Inclusi differenze percentuali, posizione nello storico, percentile, conteggi sopra soglia, media del gruppo filtrato, leader e dispersione.
- Nessun giudizio interpretativo o medico: gli insight derivano esclusivamente da calcoli verificabili.
- Database invariato.

## v3.1.3

- Collegato “Chiedi a PAS” ai widget e alle visualizzazioni originali della Dashboard.
- Aggiunto routing controllato per panoramica, confronto giocatori, storico, ruoli, soglie e classifiche Top/Bottom.
- La metrica richiesta configura sia la panoramica sia i grafici di dettaglio.
- Rimossi i grafici paralleli per le richieste già rappresentabili nella Dashboard.
- Aggiunto ripristino della configurazione applicata dall’assistente.
- Database invariato.

## v3.1.2

- Aggiunto il selettore della metrica accanto alla richiesta conversazionale nella Dashboard.
- La metrica selezionata agisce come contesto predefinito; una metrica esplicita nel testo ha priorità.
- Aggiunto il pulsante `Analizza la giornata` per generare un’analisi automatica della metrica selezionata.
- L’analisi include media, mediana, leader, valore minimo, giocatori sopra/sotto media, grafico e tabella ordinata.
- Mantenuta la risposta conversazionale in cima alla Dashboard senza alterare i filtri manuali.
- Nessuna modifica ai dati del database o alle altre sezioni del PAS.


## v3.1.1

- Trasformato `Chiedi a PAS` in una sezione conversazionale autonoma nella Dashboard.
- Rimossa la metrica di riferimento obbligatoria: la metrica viene riconosciuta dalla richiesta testuale.
- Aggiunta una risposta testuale prioritaria in cima alla Dashboard con grafici contestuali.
- Implementati confronto tra giocatori, confronto della seduta con lo storico personale e ricerche per soglia, Top N e Bottom N.
- Aggiunto un riepilogo multi-metrica quando vengono indicati giocatori senza una metrica specifica.
- Rimossa l'applicazione automatica dei filtri della Dashboard da parte dell'assistente.
- Mantenuta invariata la Dashboard ordinaria e non implementati gli Insights automatici, rinviati a una release successiva con regole dedicate.
- Nessuna modifica ai dati del database o alle altre sezioni del PAS.


## v3.1.0

- Trasformato `Chiedi a PAS` da analisi separata a controller dei filtri della Dashboard.
- Collegati i comandi allo stato Streamlit di data, drill, metriche, giocatori e modalità delle card.
- Le richieste con soglia selezionano direttamente i giocatori che rispettano il criterio.
- Aggiunto supporto a ruoli, Top N e Bottom N, mantenendo la conversione automatica delle unità.
- Aggiunti riepilogo dei filtri applicati e comando di ripristino della Dashboard.
- Nessuna modifica ai dati del database o alle altre sezioni del PAS.


## v3.0.7

- Concentrata la funzione `Chiedi a PAS` esclusivamente nella Dashboard per la fase di potenziamento.
- Aggiunto un selettore della metrica di riferimento, utilizzato quando la richiesta non nomina esplicitamente la metrica.
- Estese le soglie a tutte le metriche PAS con operatori linguistici: superato/oltre, raggiunto/almeno, sotto e al massimo.
- Aggiunta la conversione automatica delle unità, incluso `km` → `m` per le metriche di distanza.
- Migliorata la precisione dell’interpretazione con riepilogo della condizione, unità e metrica applicate.
- Mantenuti grafico, tabella, Top N, selezione giocatori e date senza modificare il database.

## v3.0.6

- Aggiunta la barra contestuale `Chiedi a PAS` in tutte le sezioni.
- Introdotto un interprete deterministico locale, senza dipendenze da API esterne.
- Supportati giocatori, date, metriche, confronti, soglie e Top N.
- Aggiunti grafico comparativo, tabella risultati e riepilogo dell’interpretazione.
- Nessuna modifica ai dati del database o alle funzionalità esistenti.

## v3.0.5

### Modificato
- Nei box plot Drills, ogni ruolo o giocatore utilizza un colore distinto e stabile.
- Contorno, riempimento e punti del box plot condividono il colore dell’entità.
- Aggiunta una legenda che associa chiaramente il colore al ruolo o al giocatore.
- Rimosse le etichette testuali sopra i box plot.
- Applicata la stessa rappresentazione ai grafici Drills nel report PDF.
- Aggiornata la versione dell’applicazione a `3.0.5`.

### Verifica
- Nessuna modifica ai calcoli, alle aggregazioni o ai dati del database incluso.
- Nessuna modifica alle funzionalità non richieste.

## v3.0.4

### Modificato
- Nei box plot Drills, contorno e riempimento mantengono il colore PAS associato alla metrica.
- I punti assumono colori distinti e stabili in base al ruolo o al giocatore selezionato.
- Le etichette identificative e i valori medi a schermo riprendono il colore dell’entità.
- La legenda indica che il colore dei punti identifica ruolo o giocatore.
- La stessa codifica visiva viene utilizzata nel report PDF Drills.
- Aggiornata la versione dell’applicazione a `3.0.4`.

### Verifica
- Nessuna modifica ai calcoli, alle aggregazioni o ai dati del database incluso.
- Nessuna modifica alle funzionalità non richieste.

## v3.0.3

### Aggiunto
- Simboli distinti per ruoli e giocatori nei punti dei box plot Drills.
- Etichetta del ruolo o nome abbreviato del giocatore sopra ogni box plot.
- Indicazione in legenda che il simbolo identifica il ruolo o il giocatore.

### Modificato
- Nome completo dell’entità mantenuto in legenda e hover.
- Stessa codifica visiva applicata ai box plot Drills del report PDF.
- Aggiornata la versione dell’applicazione a `3.0.3`.

### Verifica
- Colore PAS ancora associato esclusivamente alla metrica.
- Nessuna modifica ai dati del database incluso.
- Nessuna modifica alle funzionalità non richieste.

## v3.0.2

### Aggiunto
- Modalità `Roles` e `Players` nella sezione Drills.
- Punti dei box plot calcolati per singola occorrenza `Drill-Date`.
- Identificativo dell’occorrenza nell’hover dei punti.

### Modificato
- In modalità Roles, aggregazione per data e drill del Team Average o del ruolo selezionato.
- In modalità Players, aggregazione per data, drill e giocatore.
- Conteggio delle occorrenze distinte nel riepilogo statistico.
- Report PDF Drills con indicazione della modalità di analisi.
- Aggiornata la versione dell’applicazione a `3.0.2`.

### Verifica
- Mantenuta la palette PAS v3.0.1 nei box plot Drills.
- Nessuna modifica ai dati del database incluso.
- Nessuna modifica alle funzionalità non richieste.

## v3.0.1

### Modificato
- Applicata esclusivamente la palette PAS ai box plot Drills nella schermata Streamlit.
- Applicata la medesima palette PAS ai box plot Drills inclusi nel report PDF.
- Aggiornata la versione dell'applicazione a `3.0.1`.

### Verifica
- Nessuna modifica ai dati del database incluso.
- Nessuna modifica alle funzionalità non richieste.
## PAS v4.7.0 — Metric Profiles Foundation

- Aggiunta la configurazione esplicita dei profili metrici per Team e stagione in PAS Connect.
- Introdotta la migrazione additiva schema 7 con tabella `pas_metric_profiles`, soglie opzionali, inclusività, unità, validità, verifica, note e UPSERT non distruttivo.
- Aggiunto il confronto riutilizzabile dei profili con stati `CONFRONTABILE`, `NON CONFRONTABILE`, `CONFIGURAZIONE MANCANTE` e `CONFIGURAZIONE NON VERIFICATA`.
- Nessun profilo Team hardcoded; Distance Pilot e Bridge Validation Distance restano invariati.
- Excel resta predefinito e la scelta della sorgente rimane manuale; nessuna modifica a Dashboard, report, grafici, calcoli o dati dei database.
## PAS v4.8.0 — Metric Catalog Foundation

- Aggiunto il Catalogo metriche PAS, separato dai profili Team/stagione, con preview header-only da CSV e distinzione tra campi contestuali e metriche prestative.
- Introdotta la migrazione additiva schema 8 con tabella `pas_metric_catalog`, UPSERT transazionale e importazione che preserva le modifiche manuali.
- Previsti i provider Excel, GPExe, Firstbeat e VALD con modalità di acquisizione esplicita, senza nuovi connettori Firstbeat/VALD.
- Aggiunta la validazione logica e non distruttiva dei profili metrici orfani.
- Nessuna modifica a Distance, Dashboard, report, grafici, calcoli, database Excel o dati PAS Connect esistenti.
