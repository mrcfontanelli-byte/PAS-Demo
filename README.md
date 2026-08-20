## PAS v4.18.0 — GPExe Historical Multi-Season Foundation

PAS introduce la foundation storica multi-season GPExe con contesto provider Team/Season e catalogo storico separato dall'analysis eligibility. Sono supportati Team 543 / 2026/2027 e Team 469 / 2025/2026; Team 443 / 2024/2025 viene catalogato senza inferire uno Speed Profile. Il recupero REST usa aggregate ed elementary fallback, mentre la membership scoped è la fonte autorevole per le TeamSession drill.

La gerarchia GPExe distingue session, exercise e drill. La Dashboard espone soltanto TeamSession appartenenti alle categorie canoniche PAS: `EXERCISE` e `DRILL` sono escluse, mentre `Different Traning` è normalizzato logicamente a `Different Training` senza alterare il valore raw del provider. **Seleziona tutte** seleziona esclusivamente le TeamSession Dashboard eligible; una selezione `[]` resta vuota e non attiva alcun implicit-all.

Daily Sync operativo avanzato 2026/2027, Drills Analysis GPExe, Match Cycle GPExe e backfill completo 2025/2026 non fanno parte di questa release e restano attività future.

## PAS v4.17.4 — Dashboard N/D Cleanup + Speed Zone Color Consistency

La Dashboard separa le metriche completamente prive di valori nel contesto GPExe corrente, spostandole in un expander dedicato **Metriche non disponibili**. I selector dei grafici di dettaglio e del Session Report propongono soltanto metriche disponibili; il percorso Excel e la source policy delle metriche restano invariati.

Le Dynamic Speed Zones mantengono colori coerenti tra visualizzazioni e contesti. Il discovery locale GPExe espone tutti i Team e le stagioni supportati dai dati già persistiti, inclusi Team 543 · 2026/2027 e Team 469 · 2025/2026, senza richiedere una nuova sync.

Il selector delle TeamSession separa le opzioni locali disponibili dai valori scelti, conserva uno state distinto per Team/stagione e usa token frontend stabili con stato canonico `list[int]`. La rimozione dell'ultima selezione continua a significare zero sessioni selezionate e non elimina le opzioni riselezionabili. Nei Settings, il menu BaseWeb del multiselect resta sopra il pannello grazie al fix dello stacking del portal.

## PAS v4.17.3 — GPExe Athlete Identity Sync

PAS sincronizza le identità reali degli atleti tramite REST indipendentemente dalla readiness delle TeamSession. Il roster account-level `GET /rest/v2/athlete/` è la fonte primaria ed è richiesto una sola volta per run; per gli athlete ID rilevanti non presenti nel roster viene usato `GET /rest/v2/athlete/{id}/`, con lookup seriali e deduplicati per ID.

La persistenza identity-only aggiorna esclusivamente `gpexe_athletes` anche quando una TeamSession è ancora HTTP 202, senza pubblicare TeamSession, AthleteSession, Track, KPI o Dynamic Speed Zones. Il merge condiviso REST/GraphQL è no-downgrade: valori nulli, vuoti o fallback tecnici non sostituiscono mai un'identità reale e la provenance in `raw_json` resta bounded.

Il Dashboard usa automaticamente i nomi reali disponibili, conservando il fallback `GPEXE ATHLETE <id>` soltanto quando necessario. La semantica e i dataset delle metriche GPExe ed Excel restano invariati.

## PAS v4.17.2 — GPExe Contextual Detail Metrics

I grafici di dettaglio della Dashboard sono ora provider-aware anche con GPExe e riusano lo stesso catalogo metrico contestuale di Team Overview e Player Overview. In un contesto GPExe il selettore propone i sette scalar disponibili e le Speed Zones dinamiche definite per Team e stagione, con metadata, formati e dataset contestuali coerenti anche nel confronto giocatori e nella Media Team.

Le metriche legacy o Firstbeat non applicabili non vengono proposte quando `source=GPExe`. Lo state `dashboard_detail_metrics` viene normalizzato al cambio di provider o Team, rimuovendo selezioni non più valide. Il percorso Excel, il catalogo `METRICS` e il relativo comportamento restano invariati.

## PAS v4.17.1 — GPExe REST-only Dashboard Bridge Compatibility

PAS collega correttamente alla Dashboard le TeamSession GPExe composte esclusivamente da dati REST persistiti, anche in assenza delle righe legacy. Il performance frame mantiene le colonne consumer esistenti e assegna a ogni atleta una label stabile con precedenza: nome e cognome reali, `player_name`, quindi fallback tecnico `GPEXE ATHLETE <id>`.

Player Selector e Player Overview usano ancora la colonna `Athlete`, ora popolata per tutte le AthleteSession REST-only. Le selezioni non più valide vengono rimosse quando cambiano provider o contesto; anche data Dashboard e selezione TeamSession vengono normalizzate sulle opzioni locali correnti. Team Overview, calendario e semantica dei filtri esistenti restano invariati.

Dynamic Speed Zone Distance continua a usare gli snapshot contestuali già integrati. Quando `max_values_speed` è persistita, il Dashboard espone Max Speed in `km/h` con conversione unica dal valore REST in `m/s`. La TeamSession 143261 validata contiene 27 AthleteSession, 27 Track, 189 KPI `rest_v2`, 135 KPI `rest_v2_speed_zone`, 324 KPI totali e Max Speed valorizzata 27/27 senza duplicati.

Excel resta una sorgente separata e conserva integralmente struttura, dati e semantica legacy; questa release non introduce migrazioni o modifiche Excel.

## PAS v4.17.0 — GPExe KPI Consumer Integration + Max Speed Activation

PAS integra nei consumer operativi i sette scalar REST ufficiali GPExe: **Distance**, **Duration**, **Acc Events**, **Dec Events**, **Speed Events**, **RPE** e **Max Speed**. Il resolver centrale seleziona una sola source per canonical metric e AthleteSession: `rest_v2` è primaria, mentre `identifierKpi` / `kpi` GraphQL sono fallback soltanto quando la riga REST è assente. Una riga REST presente mantiene ownership anche con valore `NULL`, quindi RPE REST nullo non viene sostituito silenziosamente e non avvengono somme o fusioni cross-source.

Il contratto validato di `max_values_speed` è attivo: il valore provider in `m/s` viene convertito una sola volta in **Max Speed (km/h)** mediante `×3.6`, con accumulation `max` e provenance del valore/unità provider, valore/unità canonici e conversione. Max Speed resta opzionale e la sua assenza non rende incompleto il bundle.

Panoramica GPExe, Dashboard, Session Report e relativo PDF consumano gli scalar REST e le **Dynamic Speed Zone Distance** contestuali. Le zone sono ricostruite dagli snapshot storici `rest_v2_speed_zone`, ordinate per bounds canonici e mostrate con le label reali del Team/Season/TeamSession senza inserirle nelle `METRICS` globali. Restano semanticamente distinti `19.8–25.2` / `>25.2` e `20–25` / `>25`; `zone_number` e ordine del payload non partecipano all'identità.

Excel resta un provider separato: Z3, Z4 e `max speed (km/h)` conservano mapping e unità legacy senza conversioni aggiuntive. GraphQL legacy rimane disponibile come fallback GPExe deterministico e non viene eliminato dal replacement source-aware.

### Migrazione delle sessioni REST storiche

Le TeamSession sincronizzate prima della v4.17.0 possono non contenere Max Speed. Non viene eseguito alcun backfill o migrazione automatica: per acquisirla occorre risincronizzare la singola sessione via REST quando GPExe restituisce `READY`. Il replacement source-aware aggiorna `rest_v2` preservando GraphQL e `rest_v2_speed_zone`. Una risposta HTTP 202 / `processing` è uno stato operativo provider-side: PAS non pubblica dati parziali e consente un nuovo tentativo successivo.

La TeamSession 143261 mantiene quindi lo snapshot v4.16 validato con sei scalar REST; una futura sincronizzazione READY con v4.17 aggiungerà automaticamente Max Speed. Lo schema PAS Connect resta 12.

## PAS v4.16.0 — Dynamic GPExe Speed Threshold Mapping

PAS Connect mappa le **Speed Zone Distance** REST usando i bounds reali restituiti da GPExe per ogni AthleteSession. Le soglie provider vengono conservate in `m/s` e convertite in `km/h` per descriptor e label canonici; lo snapshot storico registra contesto Team/stagione/TeamSession/AthleteSession, bounds originali e canonici, unità e provenance. L'identità della metrica dipende esclusivamente dai bounds canonici, non da `zone_number` o dall'ordine del payload.

Le label sono dinamiche e mantengono separati set semanticamente diversi: `19.8–25.2 km/h` / `>25.2 km/h` non equivalgono a `20–25 km/h` / `>25 km/h`. La compatibilità con le colonne Excel legacy è ammessa soltanto quando i bounds coincidono esattamente; PAS non interpola né ricostruisce zone parziali.

La persistenza REST applica replacement source-aware alle sole source possedute `rest_v2` e `rest_v2_speed_zone`, preservando KPI GraphQL e qualsiasi altra source. Il modello mantiene coesistenza GraphQL/REST, atomicità, rollback, assenza di duplicati e `metric_family` esplicita nello snapshot, senza modificare lo schema PAS Connect 12.

Il contratto REST di `max_values_speed` è stato validato per una release successiva: il valore provider è in `m/s`, la metrica canonica è **Max Speed** in `km/h`, la conversione è `×3.6` e l'accumulation è `max`. **Max Speed resta inattiva in v4.16.0** e questa release non introduce modifiche statistiche o nuove integrazioni UI/consumer.

## PAS v4.15.0 — GPExe Official REST API Integration

PAS Connect integra l'API REST v2 ufficiale GPExe come transport esplicito del Full Sync. Nell'area **Opzioni GPExe** è possibile selezionare **REST ufficiale** oppure **GraphQL legacy/internal**; i due percorsi restano separati e non effettuano fallback automatici tra loro o verso Excel.

Il Full Sync REST autentica tramite il contratto ufficiale, costruisce in memoria il bundle TeamSession → AthleteSession → Track → KPI, ne verifica la readiness e pubblica soltanto bundle `READY` con transazione atomica, rollback e UPSERT idempotenti. Gli stati `INCOMPLETE`, `FAILED` e HTTP 202 `processing/not ready` non vengono pubblicati. L'esecuzione iniziale è seriale, rispetta il limite ufficiale di 40 richieste/minuto e conserva `Retry-After` senza polling aggressivo. Run history e riepilogo dell'ultimo sync indicano sempre il transport utilizzato.

Le metriche canoniche REST attive sono **Distance**, **Duration**, **Acc Events**, **Dec Events**, **Speed Events** e **RPE**; un RPE assente resta `NULL`. Restano volutamente inattive **Max Speed**, **Distance 19.8–25.2 km/h**, **Distance >25.2 km/h**, **Anaerobic Threshold Zone**, **High Intensity Training** e le metriche provider sconosciute. L'unità REST di Max Speed non è ancora confermata contrattualmente; le speed zones GPExe hanno soglie dinamiche specifiche per Team e saranno mappate nel contesto Team/stagione in una release successiva.

La persistenza mantiene provenance `REST v2`, contesto Team/stagione e membership atleta–Team–stagione. Lo schema PAS Connect resta alla versione 12, GraphQL rimane disponibile come percorso legacy/internal selezionabile ed è preservata la compatibilità Streamlit Cloud.

## PAS v4.14.0 — Semplificazione PAS Connect UI/UX

La pagina **Strumenti → PAS Connect** separa ora l'uso quotidiano dalle funzioni tecniche. La vista principale mantiene sorgente dati, stato e comandi di connessione GPExe, contesto Team/stagione/date/TeamSession, sincronizzazione completa e riepilogo sintetico dell'ultimo sync. Le configurazioni e i recuperi operativi meno frequenti sono raccolti in **Opzioni GPExe**; cataloghi, Developer Tools, tracing e dettagli GraphQL in **Avanzate / Diagnostica**; i quattro flussi REST storici restano disabilitati e raccolti in **Legacy — sola lettura**.

L'uploader è visibile soltanto in modalità **File export** e i due import manuali coperti dall'orchestratore non compaiono più nella vista principale. La riorganizzazione è esclusivamente presentazionale: non cambia schema PAS Connect, query o sincronizzazione GPExe, fallback KPI, Excel, calcoli, Dashboard, report, Drills o Planner. Tutte le funzioni ancora supportate restano raggiungibili e le chiavi di sessione Streamlit esistenti sono preservate.

## PAS v4.13.0 — GPExe Sync Reliability & Multi-Team Foundation

PAS Connect dispone ora di un orchestratore esclusivamente GraphQL per la catena TeamSession → AthleteSession → Track → KPI. Ogni TeamSession viene validata, tracciata nei checkpoint redatti C-01…C-05 e pubblicata con una singola transazione; un refresh incompleto o fallito non sostituisce l'ultimo bundle READY. Import ripetuti senza `force refresh` sono `SKIPPED`, mentre retry singolo e retry degli errori operano solo sulle sessioni richieste.

Lo schema PAS Connect 12 aggiunge lo storico per sessione con stati `SUCCESS`, `PARTIAL`, `FAILED`, `SKIPPED` e readiness `READY` / `INCOMPLETE`. La relazione additiva atleta–Team–stagione mantiene `gpexe_athletes` come anagrafica provider e consente allo stesso `provider_player_id` di appartenere a più Team e stagioni senza riscrivere il campo Team legacy. Il contesto locale GPExe usa Team, stagione, date, TeamSession e athlete ID provenienti esclusivamente da PAS Connect; il roster Excel non filtra il percorso GPExe. Excel resta sorgente predefinita e non viene modificato.

La validazione live finale ha usato Team 543, stagione 2026/2027, data 31/07/2026 e TeamSession 143261. Per questa sessione i resolver GPExe `identifierKpi` e `kpi` restituiscono lato provider `Field 'id' expected a number but got ''` per tutte le 27 AthleteSession. PAS ripete quindi il recupero omettendo esclusivamente i due resolver KPI e pubblica atomicamente 27 AthleteSession e 27 Track come `PARTIAL / INCOMPLETE`, con KPI pari a zero e diagnostica esplicita `provider KPI error`. Non vengono inventati KPI e non viene eseguito alcun fallback a Excel.

Questa release non introduce routing multi-provider completo, registri canonici Team/Athlete, nuove famiglie di profili, persistenza cloud esterna o migrazioni di Drills, Match, Forecast e Report.

## PAS v4.10.0 — Metric Usage Registry Foundation

PAS Connect introduce il **Metric Usage Registry**, separato dal Catalogo metriche e dai profili Team/stagione. Il registry descrive modulo, vista e tipo di utilizzo di ogni metrica, con validazione `VERIFIED` / `PROBABLE` / `AMBIGUOUS` / `MANUAL`, stato enabled/required, ordine e note, senza cambiare il comportamento delle viste esistenti.

Una preview read-only censisce riferimenti con file, riga, evidenza e confidenza verificata/probabile/ambigua; il database viene aggiornato soltanto dopo conferma esplicita. Gli utilizzi restano indipendenti dal provider, le metriche senza associazioni e gli utilizzi orfani sono soltanto segnalati. Excel resta predefinito e Dashboard, Drills, Match, report, grafici e calcoli restano invariati.

## PAS v4.9.0 — Session Distance Provider Integration

La **Panoramica del giorno** della Dashboard integra la prima metrica operativa certificata del bridge: **Distance**. Con sorgente Excel usa il provider storico invariato; con sorgente GPExe legge esclusivamente AthleteSession e KPI dal database PAS Connect, filtra la giornata e il Team selezionati e aggrega per athlete ID, usando il nome normalizzato solo come compatibilità.

Excel resta la sorgente predefinita e la scelta Excel/GPExe rimane manuale. La modalità GPExe non effettua fallback silenzioso: distingue giornata assente, Distance non utilizzabile e filtro Drill non ancora supportato. Un pannello tecnico confronta i valori giornalieri per atleta con tolleranza configurabile; sedute o atleti presenti in una sola sorgente sono indicati separatamente. Tutte le altre viste, metriche, Dashboard, report, grafici e calcoli continuano a usare il percorso esistente.

## PAS v4.8.0 — Metric Catalog Foundation

PAS Connect include un catalogo master separato dei mapping metrici. Il catalogo può generare una preview leggendo esclusivamente le intestazioni di un template CSV, distingue campi contestuali e metriche prestative e conserva provider, modalità di acquisizione, categoria, tipo, unità e necessità di un profilo Team/stagione. Le righe delle sessioni non vengono lette né importate.

Il registro provider prevede Excel (`EXCEL`), GPExe (`GRAPHQL`), Firstbeat (`MANUAL`, senza nuova connessione) e VALD (`CSV` futuro, senza import). L'importazione delle proposte preserva le modifiche manuali già salvate. I profili metrici v4.7.0 restano separati e gli eventuali profili orfani vengono soltanto segnalati, mai eliminati.

Excel resta la sorgente predefinita e la scelta Excel/GPExe rimane manuale. Distance Pilot, Bridge Validation, Dashboard, report, grafici, calcoli, database Excel e dati PAS Connect esistenti restano invariati.

## PAS v4.7.0 — Metric Profiles Foundation

PAS Connect permette di creare e aggiornare profili metrici configurabili per Team e stagione. Ogni profilo associa una metrica canonica PAS al nome KPI del provider e descrive soglie aperte, chiuse o semiaperte, unità, inclusività, periodo di validità e stato di verifica. Nessun profilo specifico viene precompilato: ogni configurazione deve essere salvata esplicitamente dall'utente.

La migrazione additiva dello schema PAS Connect conserva i dati esistenti e introduce `pas_metric_profiles` con UPSERT sicuro e storico distinto per Team, stagione e validità. Bridge Validation espone inoltre una funzione riutilizzabile per certificare la confrontabilità semantica dei futuri KPI a soglia. Distance totale resta esclusa dai profili e continua a funzionare come nella v4.6.0.

Excel resta la sorgente predefinita; la scelta Excel/GPExe rimane manuale. Dashboard, report, grafici, calcoli, database Excel e dati GPExe già presenti non vengono modificati.

## PAS v4.6.0 — Bridge Validation

La vista interna **Bridge Validation** confronta la metrica pilota Distance tra Excel e GPExe esclusivamente per le date presenti in entrambe le sorgenti, usando anche il TeamSession ID quando entrambe lo espongono. Il risultato mostra Distance per atleta, differenza assoluta e stato OK/DIFFERENTE, con riepilogo e sedute non confrontabili separate.

La validazione legge le due sorgenti senza modificarle. Excel resta la sorgente predefinita, la scelta operativa resta manuale e Dashboard, report, grafici e calcoli esistenti non cambiano.

## PAS v4.5.0 — Bridge analitico Distance

Il Data Provider comune espone la prima vista analitica pilota **Distance Pilot**. Con sorgente **Excel** usa il provider Excel esistente; con sorgente **GPExe** legge esclusivamente AthleteSession e KPI dal database SQLite PAS Connect separato. Entrambi restituiscono lo stesso schema canonico per data, atleta e Distance in metri.

Excel resta la sorgente predefinita e la selezione non viene mai modificata automaticamente. Le altre Dashboard, i report, i grafici, i calcoli, il database Excel e i dati PAS Connect restano invariati.

## PAS v4.4.0 — GPExe Athletes, Athlete Sessions e KPI

PAS Connect recupera Athletes Current ed Expired mediante la query GraphQL ufficiale, con filtro **Current / Expired / Tutti**, paginazione `first/skip/count` e deduplicazione per ID. Gli Expired usano il `clubId` del Team selezionato quando disponibile; in sua assenza PAS Connect mostra il campo opzionale **Club ID GPExe** per l'inserimento manuale, senza hardcode.

Le TeamSession selezionate possono ora caricare `TeamSessionAthletesession` con Template ID, Drill e Fields Limit opzionali. Athletes, Athlete Sessions, Tracks minimi e tutti i KPI `identifierKpi`/`kpi` vengono salvati con UPSERT nel database SQLite PAS Connect separato. Dashboard, report, grafici, calcoli, Match Analysis ed Excel non utilizzano ancora questi dati e restano invariati.

## PAS v4.3.1 — Correzione schema GraphQL GPExe

PAS Connect usa le query ufficiali del portale GPExe per `TeamSelector` e `GetTeamSessions`, con alias `res`, risultati in `data.res.content` e paginazione completa tramite `first`, `skip` e `count`. Il filtro **Team da mostrare** consente di caricare Team attivi, scaduti oppure entrambi, deduplicati per ID. La diagnostica HTTP 400 indica in modo sicuro operazione, stato ed eventuali errori GraphQL senza esporre credenziali o token. Database Excel, Dashboard, report, grafici, calcoli e caricamento GPExe locale restano invariati.

## PAS v4.3.0 — GPExe Team e TeamSession

PAS Connect rende operative le query GraphQL ufficiali `TeamSelector` e `GetTeamSessions`. Dopo l'autenticazione, il selettore Team viene popolato dal provider; l'utente può scegliere un intervallo precompilato sugli ultimi 7 giorni, recuperare le TeamSession, selezionarle in modo multiplo e importarle nel database SQLite locale PAS Connect.

Le TeamSession mostrano categoria, data, durata, numero atleti, match cycle, stato e informazioni drill. L'importazione non modifica l'Excel e non alimenta Dashboard, report, grafici, calcoli o Match Analysis. Athletes, Tracks e metriche dinamiche restano disabilitati con il messaggio “Funzione disponibile in una release successiva.” La soluzione resta compatibile con Streamlit Cloud, considerando effimera la persistenza SQLite locale sul cloud.

## PAS v4.2.0 — GPExe GraphQL Foundation

PAS Connect usa esclusivamente la mutation GraphQL verificata `TokenAuth` tramite `POST` JSON verso l'endpoint configurabile `https://e15.gpexe.com/ui/v2/`. La connessione gestisce `token`, `refreshToken` e `isActive` soltanto nella sessione corrente e presenta errori leggibili per credenziali rifiutate, account non attivo, timeout, errori HTTP, risposte non JSON o campo GraphQL `errors`, senza includere credenziali, token, cookie o header di autorizzazione nella diagnostica.

Excel resta la sorgente predefinita. La selezione Excel / GPExe e l'importazione separata di export GPExe restano disponibili, ma i dati remoti GPExe non vengono collegati alle analisi: le query GraphQL Team, TeamSession, Athletes, Categories, Tags e Tracks non sono ancora state acquisite e verificate. I relativi controlli di sincronizzazione rimangono disabilitati. Database Excel, calcoli, dashboard, grafici e report non sono modificati.

## Versione 4.2.0

La release 4.2.0 completa il flusso operativo GPExe nel pannello **PAS Connect** e rifinisce le card della Dashboard. Se GPExe è selezionato, l'export CSV, XLS/XLSX o JSON si carica direttamente da PAS Connect, viene validato e utilizzato esclusivamente in memoria. In assenza di un file valido il PAS continua a utilizzare Excel; Drills e Forecast restano alimentati dal database Excel incluso.

Nella Dashboard, i dettagli di tutti i giocatori restano raccolti nella tendina **Visualizza dettagli giocatori**, chiusa per impostazione predefinita. Il controllo report usa ora tutta la larghezza disponibile ed è mostrato in una singola riga con l'etichetta **Aggiungi box plot al report**.

- Nessuna modifica ai calcoli o alla struttura dei report.
- Database Excel incluso completamente invariato.
- Compatibilità Streamlit Cloud preservata.

## Versione 3.8.9

La release 3.8.9 introduce il **GPExe Import Engine** isolato dal PAS Core. Legge export JSON, CSV e XLSX, applica il Mapping Layer e restituisce dati canonici esclusivamente in memoria. I record non validi vengono scartati con avvisi controllati; se nessun record è utilizzabile viene segnalato il fallback a Excel. GPExe non alimenta ancora calcoli, grafici o report.

- Database Excel incluso completamente invariato.
- Compatibilità Streamlit Cloud preservata.

## Versione 3.8.7

La release 3.8.7 completa l'architettura del PAS Data Provider con un catalogo centralizzato delle sorgenti, metadati comuni e una risoluzione esplicita tra provider richiesto e provider effettivo. Excel resta l'unica sorgente operativa; selezionando GPExe il PAS registra la scelta, applica un fallback controllato a Excel e mantiene invariati dati e risultati.

- Introdotti `ProviderDescriptor` e `ProviderSelection` per separare metadati, scelta richiesta e provider effettivo.
- Aggiunto un registro unico dei provider e funzioni centrali per catalogo, normalizzazione, factory e fallback.
- PAS Connect costruisce il selettore dal catalogo comune anziché da opzioni duplicate nella UI.
- GPExe resta non operativo e non viene mai consegnato ai moduli del PAS Core.
- Nessuna modifica a calcoli, grafica, report o database Excel incluso.

## Versione 3.8.6

La release 3.8.6 completa l'infrastruttura del PAS Data Provider aggiungendo nel pannello PAS Connect la selezione della sorgente dati. Excel resta la sorgente predefinita e operativa; GPExe è visibile ma non ancora utilizzabile dal PAS Core. Nei report, valori e percentuali restano centrati quando rientrano nella colonna e vengono allineati a sinistra dall'inizio della barra soltanto quando il centraggio oltrepasserebbe il bordo sinistro. Le dimensioni maggiorate di Team Average nel Session Report e Total Match restano invariate.

- Aggiunto il selettore **Sorgente dati** in **PAS Connect**, con **Excel** come scelta predefinita.
- **GPExe** è presente nel selettore ma mostra uno stato non operativo; i dati continuano a essere caricati esclusivamente da Excel.
- Adeguato l'allineamento automatico delle etichette nei report esclusivamente per lo sconfinamento verso sinistra.
- Nessuna modifica a calcoli, grafici, struttura dei report o database Excel incluso.

## Versione 3.8.5

La release 3.8.5 migra la reportistica PAS al Data Provider mantenendo Excel come sorgente predefinita. I report continuano a usare gli stessi dati, calcoli e componenti grafici della v3.8.4.

## Versione 3.8.4

La release 3.8.4 migra Forecast al PAS Data Provider mantenendo Excel come sorgente predefinita. Nei report, le etichette restano centrate finché rientrano nella colonna; quando uscirebbero dai bordi vengono allineate a sinistra dall’inizio della barra colorata.

- La sezione **Match Analysis** utilizza ora un contratto dedicato del PAS Data Provider per ricevere il dataset completo delle partite.
- Dashboard e Drills continuano a utilizzare il PAS Data Provider con Excel come sorgente predefinita.
- Nessuna variazione a grafica, filtri, calcoli o report.
- `ExcelProvider` rimane la sorgente predefinita e conserva esattamente il comportamento precedente.
- `GPExeProvider` è predisposto sullo stesso contratto, ma non è ancora collegato ai dati operativi.
- Nessuna modifica a interfaccia, filtri, calcoli, grafici o report.

## Versione 3.8.1

### Dashboard e uniformità dei report
- La Dashboard utilizza il PAS Data Provider già introdotto, mantenendo `ExcelProvider` come sorgente predefinita e senza variazioni funzionali.
- Nei report tabellari condivisi (Session, Period, Match e layout equivalenti) le etichette numeriche mantengono una dimensione costante anche quando la barra è corta; il testo può oltrepassare la barra senza essere ridotto.
- La percentuale di Max Speed è centrata orizzontalmente nella stessa barra del valore Max Speed.
- `TEAM AVERAGE` nel Session Report usa la stessa dimensione maggiorata dei valori di `TOTAL MATCH`.
- Calcoli, grafica restante, database Excel e collegamento GPExe restano invariati.

## Versione 3.8.0

### PAS Data Provider
- Introdotto `modules/data_provider.py` come livello unico di accesso ai dati del PAS Core.
- `ExcelProvider` mantiene senza variazioni il caricamento, la pulizia e i filtri Excel già esistenti.
- `GPExeProvider` è predisposto sullo stesso contratto, ma resta intenzionalmente non operativo e non collegato ai moduli.
- Dashboard, Drills e Match Analysis passano dal PAS Data Provider; Forecast e Report restano predisposti per le release successive. Tutti continuano a utilizzare esclusivamente Excel.
- Excel resta il provider predefinito; grafica, report, calcoli e database incluso restano invariati.

## Versione 3.7.45


### Sincronizzazione completa GPExe (v3.7.45)
- Nuovo comando unico che orchestra anagrafiche, Team Sessions, dettagli Team Sessions e Athlete Sessions.
- Barra di avanzamento e log sintetico durante l'esecuzione.
- Riepilogo finale con conteggi per ogni fase.
- I comandi manuali restano disponibili per diagnostica e recuperi mirati.
- Excel resta la sorgente operativa e il database incluso non viene modificato.

### PAS Connect · Athlete Sessions GPExe
- Sincronizza anagrafiche, Team Sessions, dettagli Team Session e Athlete Sessions in `.pas_data/pas_connect.sqlite3`.
- Gli ID GPExe vengono aggiornati tramite upsert, senza creare duplicati.
- Metriche scalari, zone e payload grezzi delle Athlete Sessions restano disponibili nel database tecnico separato.
- Ogni sincronizzazione registra stato, data/ora, conteggi ed errori isolati.
- Excel resta la sorgente operativa e tutte le sezioni del PAS restano invariate.
- Su Streamlit Community Cloud il file SQLite locale è effimero e sarà sostituito successivamente da persistenza cloud esterna.

### PAS

**Versione corrente: 3.8.8**

### GPExe Athlete Sessions (v3.7.44)

PAS Connect può ora scaricare il dettaglio delle Athlete Sessions collegate alle Team Sessions già sincronizzate. Il database separato conserva identificativi, collegamenti a sessione/atleta/drill/track, metriche scalari, zone ed il payload grezzo. Excel resta la sorgente operativa e Dashboard, report e analisi non cambiano.

La release 3.7.43 aggiunge la sincronizzazione incrementale delle Team Sessions GPExe nel database PAS Connect separato, con upsert e log di record nuovi/aggiornati. Excel resta la sorgente operativa e nessuna analisi usa ancora le sessioni GPExe.

- Introdotto il package isolato `pas_connect/` con configurazione provider, catalogo endpoint GPExe, autenticazione token, client REST testabile, mapper iniziali e piano di sincronizzazione.
- Excel resta la sorgente dati predefinita e operativa: nessuna sezione, analisi o interfaccia è stata modificata.
- Aggiunta documentazione tecnica in `docs/` per specifica PAS Connect, schema dati PAS, mapping GPExe e workflow di sincronizzazione.
- Le credenziali GPExe non sono incluse nel progetto e dovranno essere lette da Streamlit secrets o variabili d'ambiente nelle release successive.
- Aggiunti test automatici della foundation senza effettuare chiamate di rete reali.

## Versione 3.7.35

### Match Report stemmi e scala compatta v3.7.35

- Gli stemmi nell’intestazione del Match Report sono inseriti su un badge chiaro ad alto contrasto, così restano visibili anche quando il logo è nero o molto scuro.
- Il riconoscimento dell’avversario supporta sia il formato reale `data · MD AVVERSARIO (H/A)` sia varianti senza prefisso `MD`.
- Il limite massimo delle barre individuali è calcolato sul maggiore tra valore reale e target, con un margine del 5% dell’intervallo utile sopra il minimo della metrica.
- Relative Distance mantiene il minimo 80 e MPE REC AVG TIME il minimo 5.
- Nessuna modifica ai calcoli o ai valori del modello prestativo.

## Versione 3.7.34

### Match Report scale e TOTAL MATCH v3.7.34

- Relative Distance usa una scala grafica con minimo 80 m/min.
- MPE REC AVG TIME usa una scala grafica con minimo 5 s.
- Valore reale e target individuale condividono la stessa scala metrica.
- La sintesi partita è rinominata TOTAL MATCH.
- Le barre del TOTAL MATCH sono sempre piene e le etichette numeriche sono più grandi.
- Calcoli, metriche e dati restano invariati.

### Match Report target scale v3.7.33

- Le barre del Match Report usano una scala comune per metrica che include valori reali e target individuali.
- La scala parte da zero e aggiunge un margine del 10% oltre il massimo, così la distanza tra barra e linea target è rappresentata correttamente.
- L’etichetta target è ancorata alla stessa posizione scalata della linea.
- `MPE REC AVG TIME` è arrotondato a 0 decimali nel valore e nel target.
- Nessuna modifica ai calcoli del modello prestativo o ai dati.

## Versione 3.7.32

### Match Report target labels v3.7.32
- Il valore individuale della metrica è centrato all'interno della barra colorata.
- La linea del target individuale mostra una piccola etichetta numerica alla base, posizionata verso sinistra.
- Nessuna modifica ai calcoli del modello prestativo o agli altri report.

## Versione 3.7.31

### Correzione Match Analysis v3.7.31
- Il selettore giocatori viene inizializzato separatamente per ogni partita e preseleziona tutti gli atleti disponibili nella riga `Drill = Match`.
- Match Analysis non esclude più atleti validi in base alla rosa statica configurata nel codice.
- `Team Average` resta escluso e i Match Total continuano a usare esclusivamente i giocatori reali.

### Match Report
- L’intestazione del Match Report mostra ora **MATCH REPORT** seguito dagli stemmi delle due squadre separati da **VS**.
- Nelle partite `(H)` l’ordine è **Hellas Verona → avversario**.
- Nelle partite `(A)` l’ordine è **avversario → Hellas Verona**.
- Inclusi gli stemmi degli avversari forniti e una mappatura compatibile con nomi alternativi come `Inter` / `Internazionale`.
- Se lo stemma dell’avversario non è disponibile, il report usa il nome della squadra senza interrompere la generazione.
- Nessuna modifica a dati, metriche o calcoli.

## Versione 3.7.29

### Report PDF
- **Relative Distance** viene visualizzata con **0 decimali** nei report tabellari (Session, Period, Match e report basati sullo stesso layout).
- Nel **Match Report**, sotto al valore di **Max Speed**, viene mostrata la percentuale della Max Speed individuale rispetto al massimo storico del giocatore, con lo stesso stile del Session Report.
- Palette, calcoli delle altre metriche e database restano invariati.

## Versione 3.7.28

### Dashboard e report
- Rimossa dalle card Dashboard la dicitura ridondante **“Confronto giocatori del giorno”**.
- Resi più pieni e leggibili i colori delle barre nei report PDF di Session, Period e Match, mantenendo invariata la palette PAS.
- Nessuna modifica ai calcoli, ai dati o alla struttura dei report.

- Dashboard aggiornata con una gerarchia visiva più chiara e compatta.
- Card metriche con valore principale più evidente, badge di stato più leggibile e statistiche Media/Mediana/SD/CV organizzate in quattro micro-box.
- Riquadro accumulo reso più compatto e meglio bilanciato.
- Intestazione della Panoramica del giorno trasformata in una hero compatta con contesto e baseline omologa.
- Box plot della Dashboard alleggeriti con sfondo trasparente, griglia discreta e spazi ridotti.
- Lo stile Dashboard resta separato dai report PDF; nella v3.7.28 i PDF ricevono soltanto colori più pieni, senza modifiche strutturali.
- Nessuna modifica a calcoli, filtri o database.

## Versione 3.7.26

- Nelle card della **Panoramica del giorno**, Media, Mediana, SD e CV sono ora calcolati esclusivamente sulle sedute omologhe precedenti.
- La baseline usa sempre lo stesso **Match Day relativo** e la stessa **Length Cycle** del giorno selezionato.
- Il giorno selezionato è escluso dalla baseline.
- Scostamento percentuale, stato storico e statistiche descrittive derivano ora dallo stesso identico campione.
- Se non esistono sedute omologhe valide, la card mostra la baseline come non disponibile senza usare altri periodi.
- Database e funzionalità non richieste invariati.

## Versione 3.7.25

- Nei box plot della pagina **Drills**, ciascun drill selezionato usa un colore distinto.
- Aggiunta una palette fissa di **10 colori** ottimizzata per il tema scuro PAS.
- Lo stesso drill conserva lo stesso colore in tutte le metriche visualizzate e nei report.
- Box, bordi, punti e legenda condividono il colore assegnato al drill.
- Il selettore consente di confrontare al massimo **10 drill** contemporaneamente.
- Database e funzionalità non richieste invariati.

## Versione 3.7.24

- In **PAS Intelligence** il campo di richiesta mostra ora il prompt professionale **“Cosa vuoi analizzare?”**.
- Rimossa dalla pagina **Drills** la sezione non pertinente **Player drill coverage**.
- Il selettore Drills viene ora popolato con i nomi reali presenti nel foglio **Esercitazioni**, ordinati per frequenza; i tre più ricorrenti sono preselezionati.
- Se i filtri non restituiscono esercitazioni, viene mostrato un messaggio esplicito invece di un selettore vuoto.
- Database e funzionalità non richieste invariati.

## Versione 3.7.23

- Nella Panoramica del giorno lo scostamento usa sempre sedute omologhe: stesso Match Day relativo e stessa Length Cycle.
- Le card mostrano una sola micro-etichetta compatta: `vs media omologa · n=X`.
- Il dettaglio del criterio è disponibile al passaggio del mouse, senza aumentare sensibilmente l'altezza delle card.
- Database e logiche non richieste invariati.

## Versione 3.7.22

- Corretto il taglio superiore dell’intestazione PAS su Streamlit Cloud.
- Aggiunto un margine di sicurezza di `3.5rem` sotto la toolbar nativa.
- L’header resta più alto rispetto alla configurazione precedente, ma continua a occupare molto meno spazio del layout Streamlit predefinito.
- Nessuna modifica a navigazione, sidebar, calcoli, report o database.

## Versione 3.7.21

- Ridotto il padding superiore del contenitore principale Streamlit.
- Spostata verso l’alto l’intestazione PAS, recuperando lo spazio vuoto sotto la toolbar nativa.
- Toolbar Streamlit, navigazione, sidebar e funzionalità applicative invariate.
- Modifica compatibile con Streamlit Cloud e con i selettori moderni/legacy del contenitore principale.

## Versione 3.7.20

- **Database** e **Settings** sono affiancati nella sidebar e si aprono come pannelli compatti.
- In **Match Analysis** la scelta tra *Singola partita* e *Confronto / Totali partite* è nella sidebar.
- Anche partita, giocatori, metriche, partite da confrontare e soggetto del confronto sono gestiti dalla sidebar.
- La pagina principale di Match Analysis è dedicata esclusivamente ai risultati e ai report.

## Versione 3.7.19

- Esportazione PDF verificata con massimo quattro grafici per pagina.
- Aggiunto `RELEASE_MANIFEST.txt` con inventario e checksum SHA-256 dei file della release.
- Aggiunto test ripetibile `tests/test_pdf_pagination.py` per verificare che cinque grafici producano due pagine.
- I file `__pycache__` non sono distribuiti: vengono rigenerati automaticamente da Python e non fanno parte dei sorgenti.

# PAS Demo v3.7.13 — Performance Analysis System





## Novità v3.7.19

- Il comando **Esci dalla Demo** è stato spostato nel pannello compatto **⚙️ Settings** della sidebar.
- Rimossa l’azione di uscita dalla vista principale per ridurre l’ingombro dell’interfaccia.
- Nel pannello Settings sono visibili anche versione PAS e database attivo.


## Interfaccia compatta v3.7.18

- Il pannello Database della sidebar è chiuso per impostazione predefinita e mostra all’esterno soltanto un riepilogo compatto.
- Il comando Demo è ridotto a un piccolo pulsante **Esci** collocato nella parte inferiore della sidebar.
- **PAS Intelligence** non occupa più spazio permanente: si apre tramite il pannello cliccabile **✨ PAS Intelligence** nelle sezioni Dashboard e Period Load.
- L’apertura o chiusura del pannello non modifica filtri, analisi o navigazione.

## Navigazione orizzontale

La navigazione principale del PAS è collocata nella parte superiore dell’interfaccia, con le sezioni disposte orizzontalmente. Su schermi più stretti le voci vanno automaticamente a capo. La sidebar resta dedicata a database, filtri e controlli specifici delle singole pagine.

## Stampa dei grafici v3.7.13

- I report grafici PDF sono ora impaginati su A4 orizzontale con un massimo di quattro grafici per pagina.
- Un grafico viene mostrato a tutta pagina; due grafici sono affiancati; tre o quattro grafici usano una griglia 2 x 2.
- Dal quinto grafico viene creata automaticamente una nuova pagina.
- Titoli, legende e annotazioni di significatività sono mantenuti nell'esportazione.
- Ogni pagina riporta numero pagina e totale dei grafici selezionati.

## Significatività nei grafici e confronti pairwise v3.7.12

- Le differenze statisticamente significative sono visualizzate nei grafici con parentesi e simboli in stile pubblicazione scientifica (`*`, `**`, `***`, `****`).
- Con tre o più gruppi, dopo il test globale vengono eseguiti confronti post-hoc a coppie con correzione di Holm: può quindi risultare significativo A–B ma non A–C.
- Anche con due soli gruppi, per esempio S e NS, il confronto viene indicato esplicitamente nel grafico e nella Performance Interpretation.
- La Performance Interpretation riporta i nomi dei gruppi coinvolti, il p-value, l'effect size e la direzione della differenza quando disponibile.

## Ripristino controlli giocatori Drills v3.7.11

Nella pagina Drills, in modalità Players, sono nuovamente disponibili i conteggi per giocatore delle sei categorie supportate, una soglia minima indipendente per ciascun drill e la selezione manuale tramite checkbox Include. I conteggi usano le giornate uniche e i grafici includono soltanto i giocatori rimasti selezionati.

## Correzione v3.7.10 — Selettori Drill coerenti

Sia il filtro **Drill** della Performance Research sia il selettore della pagina **Drills** mostrano esclusivamente: Active Recovery, Individual Training, Return to Play, Full Training, Match e Different Training. Le chiavi dei widget sono state aggiornate per evitare che lo stato Streamlit mantenga vecchie selezioni non più consentite.

## Novità v3.7.9 — Categorie consentite nella sezione Drills

Il selettore **Drills** mostra esclusivamente queste sei categorie:

- Active Recovery
- Individual Training
- Return to Play
- Full Training
- Match
- Different Training

Gli altri valori della tassonomia non vengono proposti nella sezione Drills. La variante storica `Different Traning` viene ricondotta a `Different Training`.

## Novità v3.7.8 — Nuove categorie di seduta nel Match Cycle

- Nel percorso **Giocatore per Match Cycle** il selettore comprende ora **Full Training**, **Match**, **Different Training**, **Active Recovery**, **Individual Training** e **Return to Play**.
- La tabella di copertura mostra per ogni giocatore il numero di giornate uniche svolte in ciascuna delle sei categorie.
- Ogni categoria dispone di una soglia minima indipendente utilizzabile per la preselezione automatica dei giocatori.
- La colonna **Includi** resta modificabile manualmente dopo l’applicazione delle soglie.
- Il totale individuale del ciclo somma soltanto le categorie selezionate, mentre la tabella mantiene visibili tutti i conteggi per supportare la decisione di inclusione.


## Novità v3.7.7 — Controllo esposizioni e inclusione giocatori

- Nel percorso **Giocatore per Match Cycle** è possibile selezionare quali sedute includere nel totale: **Full Training**, **Match** e **Different Training**.
- Prima dell’analisi viene mostrata una tabella di copertura per giocatore con il numero di giornate uniche per ciascuna categoria, il totale delle sedute e il numero di Match Cycle presenti.
- La colonna **Includi** permette di escludere manualmente i giocatori dall’analisi.
- Le soglie minime FT, Match e DT consentono una prima selezione automatica, modificabile successivamente dalla tabella.
- Il dataset analitico viene costruito dopo questi controlli: una riga aggregata per giocatore e Match Cycle (e per il livello del fattore quando necessario), ottenuta sommando esclusivamente le sedute selezionate.
- Con più cicli il Linear Mixed Model mantiene il giocatore come random effect, gestendo presenze variabili e pannelli non bilanciati.


## Novità v3.7.6 — Confronto Match Cycle con Linear Mixed Model

- Separata la modalità Match Cycle in **Confronta un ciclo gara** e **Confronta più cicli gara · Linear Mixed Model**.
- Nel confronto multiplo, ogni osservazione è il totale individuale del giocatore nel ciclo, ottenuto sommando tutte le giornate del ciclo.
- Il modello usa `Match Cycle × fattore principale` come effetti fissi e `(1 | Giocatore)` come random intercept.
- Questa struttura gestisce misure ripetute e pannelli non bilanciati: i giocatori possono essere diversi nei vari cicli.
- Nel Trend, quando Match Cycle è il secondo fattore, l’asse X mostra i cicli e le linee rappresentano i livelli del fattore principale (blu S, arancione NS).
- I punti mostrano le medie marginali stimate dal modello con IC95% e numerosità dei giocatori nel ciclo/gruppo.
- Il confronto di un singolo ciclo mantiene la lettura descrittiva dei totali individuali.

## Novità v3.7.5 — Trend Match Cycle con pannello giocatori variabile

- Nel **Trend delle medie**, quando **Match Cycle** è selezionato come secondo fattore, i Match Cycle vengono mostrati sull’asse X.
- Il fattore principale definisce le linee del grafico; ad esempio Starters (S) e No Starters (NS) sono rappresentati con linee di colore diverso.
- L’analisi usa i giocatori effettivamente presenti in ciascun ciclo e gruppo, senza richiedere che il campione sia identico tra i diversi Match Cycle.
- Con unità **Giocatore per Match Cycle**, ogni punto è la media dei totali individuali del ciclo; il tooltip mostra anche il numero di giocatori presenti.
- Filtri, database e funzionalità non coinvolte restano invariati.

## Novità v3.7.4 — Match Cycle Individual Totals

- Nella **Performance Research**, con unità di osservazione **Giocatore per Match Cycle**, i valori di tutte le giornate del ciclo vengono prima sommati per ciascun giocatore.
- Starters (S) e No Starters (NS) vengono separati dopo il calcolo dei totali individuali; il valore di gruppo è la media dei rispettivi totali individuali.
- Non vengono più usate media o mediana delle singole giornate nella logica Match Cycle.
- Se sono selezionati più Match Cycle, l’asse X mostra i cicli e il confronto usa due linee: blu per S e arancione per NS.
- Tutti i filtri esistenti, inclusi ruolo e giocatori, restano attivi.
- Database e funzionalità non coinvolte invariati.

## Novità v3.7.3 — Group Colors & Significance Hotfix

- Nella **Performance Research** i colori identificano ora stabilmente i gruppi: blu PAS per Starters e arancione PAS per No Starters, indipendentemente dalla metrica.
- Le barre di significatività dei raincloud sono ora tracciate come livelli grafici dedicati, con linea nera più spessa e `*`, `**`, `***` o `ns` sempre sopra le distribuzioni.
- I livelli con differenza significativa ricevono una lieve evidenziazione di sfondo.
- Nel Trend l’asse X coincide sempre con il fattore principale selezionato; scegliendo Match Cycle, i cicli costituiscono le categorie dell’asse X.
- Le linee del Trend rappresentano i due gruppi con colori coerenti; la linea Team è opzionale e disattivata per impostazione predefinita.
- Il grafico Totali usa la stessa codifica cromatica dei gruppi e mantiene i marker di significatività.
- Database e sezioni non coinvolte invariati.

## Novità v3.7.2 — Performance Research Visual Suite

- I **raincloud plot** sono ora disponibili anche nelle analisi a due fattori, con distribuzione, boxplot e punti individuali per Starters e No Starters in ogni Match Cycle.
- Le barre nere di significatività sono disegnate direttamente sopra i gruppi con `*`, `**`, `***` o `ns`.
- Aggiunto il grafico **Trend** lungo i cicli con Starters, No Starters e linea Team, media e IC95%.
- Aggiunto il grafico **Totali per ciclo**, configurabile come Media, Somma o Mediana per ogni metrica.
- Introdotto il selettore Visualizzazioni: Tutti, Distribuzione (Raincloud), Trend e Totali per ciclo.
- Rafforzata la Performance Interpretation con avviso ad alta evidenza, effect size e lettura operativa non valutativa.
- Aggiunto il Performance Score sintetico per ciascun livello del fattore principale.
- Database e sezioni non coinvolte invariati.

## Novità v3.7.1 — Raincloud e trend S/NS

- Ripristinati i **raincloud plot** nella sezione Performance Research per i confronti a un fattore.
- Nei disegni a due fattori è ora visibile l’andamento dei gruppi lungo il fattore principale, incluso il confronto **Starters vs No Starters nei diversi Match Cycle**.
- Aggiunti confronti automatici S/NS all’interno di ogni ciclo e indicatori `*`, `**`, `***` nei grafici quando la differenza è significativa.
- Resa più evidente la Performance Interpretation attraverso messaggi dedicati alle differenze significative.
- Nessuna modifica al database o alle altre sezioni del PAS.

## Novità v3.7.0 — Performance Research Foundation

- La precedente pagina **Statistical Analysis** è stata riprogettata come **Performance Research**.
- L’utente seleziona metriche, uno o due fattori e filtri; non deve scegliere manualmente il test statistico.
- Introdotto un motore che riconosce automaticamente descrittive, confronto tra due gruppi, confronto tra più gruppi, analisi multifattoriale esplorativa e correlazioni.
- Scelta automatica tra t-test/Welch e Mann–Whitney per due gruppi.
- Scelta automatica tra ANOVA a una via e Kruskal–Wallis per più gruppi.
- Aggiunti effect size, visualizzazioni coerenti e Performance Interpretation orientata alla pratica.
- PAS Intelligence è ora visibile esclusivamente in **Dashboard** e **Period Load**.
- Nel Period Load, Duration e RPE restano esclusi dalle percentuali del modello gara.
- Confermata la struttura dei report con una sola etichetta S e una sola NS per gruppo e nomi completi.

## Novità v3.6.0 — Statistical Analysis

- Nuova sezione **Statistical Analysis** integrata nella navigazione PAS.
- Confronto tra due gruppi definiti tramite giocatori, ruoli, Starters/No Starters, intervalli di date e Match Cycle.
- Selezione simultanea di una o più metriche.
- Unità di osservazione configurabile: giocatore per giornata oppure giocatore per Match Cycle.
- Statistiche descrittive: N, media, mediana, SD, SE, CV, minimo, massimo e IC95%.
- Test di normalità Shapiro–Wilk.
- Selezione automatica tra t-test indipendente, Welch e Mann–Whitney.
- Effect size con Hedges g o correlazione rank-biserial e interpretazione dell'entità.
- Raincloud/violin plot, distribuzioni, dati grezzi e correlazioni Pearson/Spearman.
- PAS Statistical Insights con sintesi leggibile dei risultati.
- Nel Period Load, **Duration** e **RPE** sono mostrati solo come valori assoluti e non come percentuale del modello gara.

## Novità v3.5.6 — Hotfix grafico Team Overview

- Corretto il crash nella visualizzazione della media squadra del giorno nei grafici di dettaglio.
- Restano invariati lo storico squadra, la distribuzione completa della giornata e l’evidenziazione dei giocatori selezionati.


## Novità v3.5.5 — Grafici di dettaglio coerenti tra Team e Player Overview

- Team Overview: mantenuto lo storico squadra a sinistra e l’intera distribuzione dei giocatori della giornata a destra.
- Team Overview: aggiunto un indicatore dedicato alla media squadra della giornata, senza rimuovere alcun pallino.
- Team Overview: eventuali giocatori selezionati restano evidenziati sopra la distribuzione completa.
- Player Overview: mantenuto lo storico individuale e l’intera distribuzione della squadra del giorno, con il giocatore della panoramica evidenziato.

## Novità v3.5.4 — Evidenziazione corretta nel Player Overview

- Nei grafici di dettaglio del Player Overview il giocatore scelto in **Giocatore della panoramica** viene ora evidenziato con un pallino giallo più grande, bordo scuro e nome.
- Tutti gli altri giocatori della giornata restano visibili per mantenere la distribuzione completa.
- Il filtro generale dei giocatori non interferisce più con l’evidenziazione del Player Overview.


## Novità v3.5.3 — Correzione Period Report e distribuzione giornaliera

- Nel Period Load Report PDF le etichette **S** e **NS** sono ora visibili una sola volta, centrate nella colonna a sinistra dei rispettivi gruppi.
- Il separatore tra Starters e No Starters è più marcato.
- Nei grafici di dettaglio della Dashboard resta sempre visibile l’intera distribuzione dei giocatori del giorno.
- In Player Overview il giocatore selezionato viene evidenziato con un rombo giallo più grande senza nascondere gli altri giocatori.
- Nessuna modifica al calcolo del PAS Load Index o alle altre funzionalità.


## Novità v3.5.1 — Trasparenza PLI e gruppi S/NS

- Nel Period Load Report PDF gli Starters e i No Starters sono ordinati in due gruppi con una sola etichetta `S` e una sola `NS`, centrate verticalmente accanto ai nomi.
- Il separatore tra i due gruppi è più marcato e mantiene una tonalità grigio chiaro professionale.
- Nel profilo PAS Load Index le etichette e i tooltip mostrano, oltre alla percentuale della componente, i valori assoluti delle metriche che la compongono e i rispettivi riferimenti gara.
- Nei grafici di dettaglio della Dashboard i giocatori selezionati sono evidenziati con rombo giallo, bordo scuro e nome; gli altri punti della distribuzione restano visibili con opacità ridotta.
- Nessuna modifica ai dati del database.

## Novità v3.5.0 — PAS Load Index (PLI)

- Sostituito l’indice multi-metrica basato sui percentili di squadra con il **PAS Load Index (PLI)** individuale.
- Ogni giocatore viene confrontato con il proprio modello prestativo di gara.
- Il modello gara usa le metriche additive proiettate sui 90 minuti; la Durata usa il riferimento fisso di 90 minuti e l’RPE il riferimento fisso di 8.
- Il PLI è la media, a peso uguale, delle sei componenti disponibili:
  - **Volume**: Distance + Durata;
  - **Alta velocità**: Distance 19.8–25.2 km/h;
  - **Sprint**: Distance >25.2 km/h + Speed Events;
  - **Componente neuromuscolare**: Accelerazioni + Decelerazioni;
  - **Velocità massima**: Max Speed + % Max Speed individuale;
  - **Carico interno**: RPE.
- PAS Intelligence mostra ranking PLI, distribuzione e profilo per componente, sempre espressi come `% del modello gara`.
- I Key Insights indicano carico maggiore/minore, PLI medio e dettaglio delle sei componenti.
- Nel Period Load Report i giocatori sono ordinati prima S e poi NS, con prefisso a sinistra del nome e separatore orizzontale grigio chiaro.
- Nessuna modifica ai dati del database.


## Novità v3.4.1 — Starters vs No Starters in PAS Intelligence

- Le richieste che citano insieme Starters (S) e No Starters (NS) vengono rappresentate in due pannelli coordinati.
- La distinzione è disponibile nella Dashboard e in Period Load, senza nuovi filtri visibili.
- Le scale dei due pannelli sono coerenti e i Key Insights riportano anche la media dei due gruppi.
- Corretto il riconoscimento testuale di “No Starters”, “S e NS” e formulazioni equivalenti.

## Novità v3.4.0 — Analisi completa della seduta
- PAS Intelligence riconosce domande come “cosa possiamo dire della seduta di oggi?”.
- Aggiunti ranking e distribuzione del carico complessivo multi-metrica.
- Aggiunto profilo percentile dei giocatori con carico maggiore.
- Key Insights estesi a tutte le metriche: valore maggiore/minore, media, mediana e dispersione.
- Terminologia resa neutra e professionale: “carico maggiore/minore”, senza giudizi sulla qualità della prestazione.
- Metodo dell’indice composito invariato e trasparente: media dei ranghi percentili con peso uguale.

## Novità v3.3.9 — Stabilizzazione Streamlit Cloud
- Nessuna modifica alle funzionalità analitiche.
- `requirements.txt` ricreato e validato: contiene esclusivamente dipendenze Python.
- Aggiunto `validate_release.py` per controllare entrypoint, moduli essenziali, dipendenze, compilazione e struttura dello ZIP.
- Documentata la configurazione consigliata di Streamlit Community Cloud con Python 3.12 e `app.py` nella radice.
- Verificati gli import locali e l'integrità del database.

## Novità v3.3.8 — Carico multi-metrica nella Dashboard

PAS Intelligence riconosce domande come “chi ha fatto il maggior carico oggi?” e “fammi vedere i 5 giocatori con maggior carico oggi”. Il risultato include un indice composito 0–100, il ranking richiesto, un profilo grafico dei ranghi percentili per metrica e Key Insights separati per ciascun parametro disponibile. Le metriche hanno peso uguale e il metodo è dichiarato nell’interfaccia.

## Novità v3.3.7 — Periodi naturali inclusivi

PAS Intelligence in Period Load riconosce ora intervalli temporali espressi in linguaggio naturale.

- `ultimi N giorni` indica un intervallo inclusivo: oggi/ultimo giorno disponibile compreso;
- `ultime N settimane`, `questa settimana`, `settimana precedente` e `questo mese`;
- richieste con `km` senza riferimenti alla velocità vengono associate a `Distance`;
- il periodo riconosciuto imposta direttamente l'intervallo date di Period Load.

Esempio: `quanti km ha fatto SARR negli ultimi 3 giorni?` usa Distance e il periodo dall'ultimo giorno disponibile ai due giorni precedenti.



## Novità v3.3.6 — Max Speed assoluta e percentuale

- La Dashboard mostra **Max Speed (km/h)** e, subito sotto, la **% del massimo individuale**.
- Lo stesso doppio valore è presente nelle barre di confronto giocatori.
- PAS Intelligence mostra km/h e percentuale insieme nelle richieste sulla % Max Speed.
- Tooltip e titoli rendono esplicite entrambe le scale.

Prima versione funzionale costruita sul database Hellas Verona 2025-26.



## Hotfix v3.3.4 — Import locali su Streamlit Cloud

- Resa esplicita la radice del progetto nel percorso di importazione Python.
- Verificata la presenza del package `modules`, di `modules/__init__.py` e di `modules/config.py`.
- Aggiunto un controllo di avvio su estrazione pulita dell’archivio.
- Nessuna modifica alle funzionalità analitiche o ai dati.

## Novità v3.3.3 — Soglie linguistiche e % Max Speed

- `% Max Speed individuale` viene calcolata, visualizzata e riportata sempre in percentuale.
- Riconoscimento di domande come “chi ha raggiunto il 90% di velocità massima?” e “chi non ha raggiunto il 90%?”.
- Estensione delle formulazioni positive e negative a tutte le metriche: raggiunto, superato, almeno, sotto, non ha raggiunto e non ha superato.
- Grafici, soglie, riepiloghi e Key Insights usano l’unità corretta.


## Novità v3.3.2 — Gruppi, % Max Speed e carico multi-metrica

- PAS Intelligence riconosce direttamente nel testo Starters (`S`) e No Starters (`NS`), senza aggiungere filtri visibili.
- Riconosciuti ruoli e sinonimi italiani nelle richieste (attaccanti, centrocampisti, difensori, terzini, esterni, portieri, ecc.).
- Supportate combinazioni come `attaccanti NS sopra 3,5 km` o `Starters oltre 20 accelerazioni`.
- Aggiunta la `% di Max Speed`: il valore della seduta viene rapportato alla massima velocità storica individuale.
- Supportate richieste come `chi ha superato l’85% di Max Speed oggi`, con grafico soglia e Key Insights nominativi.
- Aggiunte richieste multi-metrica come `chi sono i 5 giocatori con il carico maggiore di oggi`.
- Il carico multi-metrica è un indice trasparente 0–100 ottenuto dalla media dei ranghi percentili di RPE, durata, distanze ad alta velocità, accelerazioni, decelerazioni e speed events disponibili, con peso uguale.
- Nessuna modifica ai dati del database.

## Novità v3.3.1 — Soglie evidenziate

- Le richieste PAS Intelligence con soglia mantengono visibile l’intero gruppo.
- Barre e nomi dei giocatori che soddisfano la soglia sono evidenziati con il colore PAS della metrica.
- Gli altri giocatori restano visibili in grigio per mantenere il contesto.
- Il grafico mostra una linea tratteggiata con il valore della soglia.
- I Key Insights riportano anche i nomi dei giocatori che soddisfano la condizione.
- La logica si applica a tutte le metriche e agli operatori sopra, almeno, sotto e al massimo.

## Novità v3.3.0 — PAS Intelligence potenziato

- Il risultato grafico principale viene mostrato subito dopo ogni richiesta, prima degli insight e del testo di configurazione.
- Aggiunta memoria del contesto per richieste successive brevi come `ora gli sprint` o `e lo storico`.
- Aggiunti livello di confidenza dell’interpretazione e indicazione esplicita della sezione selezionata.
- Introdotte Quick Actions contestuali: Storico, Confronta ruolo, Top 5 e Squadra.
- Creata la struttura iniziale della Knowledge Base con sinonimi delle metriche e regole di navigazione centralizzate.
- Mantenuto il riuso delle sezioni e dei componenti originali del PAS sotto il risultato prioritario.
- Nessuna regola interpretativa calcistica o modifica ai dati del database.


## Novità v3.2.1 — Dashboard più compatta

- Rimosso il Planner incorporato dalla Dashboard per recuperare spazio verticale e orizzontale.
- La pagina Planner resta disponibile e invariata nel menu laterale.
- PAS Analysis, filtri, KPI, grafici e tabelle della Dashboard restano invariati.
- Nessuna modifica ai dati del database.


## Novità v3.2.0 — PAS Intelligence Engine

- PAS interpreta la richiesta e seleziona automaticamente la sezione più coerente.
- Supportate Dashboard, Drills, Match Analysis, Period Load, Planner, Forecast e Return To Play.
- Giocatori, ruoli, metriche e drill vengono preconfigurati quando i controlli della sezione lo permettono.
- Storico e profilo individuale usano la Player Overview della Dashboard finché Player Profiles non sarà sviluppata.
- I componenti originali del PAS vengono riutilizzati senza creare visualizzazioni alternative non necessarie.


## Novità v3.1.5 — PAS Analysis Engine

- Ridisegnata la sezione dell’assistente con un’interfaccia compatta e professionale denominata `PAS Analysis`.
- Campo richiesta, selettore metrica, comando di analisi e analisi giornata sono ora disposti su un’unica barra operativa.
- Rimossi titolo da chatbot, icona conversazionale e testo introduttivo esteso.
- Il risultato è presentato in un pannello comprimibile con configurazione, Key Insights e componenti originali della Dashboard.
- La logica di interpretazione e i dati restano invariati.

## Novità v3.1.4 — Key Insights contestuali

- Ogni richiesta a `Chiedi a PAS` può mostrare un blocco `Key Insights` prima dei grafici e delle card originali della Dashboard.
- I confronti tra giocatori evidenziano leader, differenza assoluta e percentuale e posizione rispetto alla media.
- I confronti con lo storico mostrano scostamento dalla media personale, posizione della seduta e percentile rispetto alle sedute precedenti.
- Le richieste con soglia mostrano numero di giocatori corrispondenti, quota sul totale e media del gruppo filtrato.
- Top/Bottom e analisi della giornata mostrano leader, media, mediana e dispersione dei valori.
- Gli insight sono esclusivamente descrittivi e numerici; non vengono ancora generati giudizi interpretativi come sovraccarico, rischio o criticità.

## Novità v3.1.3 — Assistente collegato alla Dashboard originale

- Le richieste di “Chiedi a PAS” pilotano direttamente i componenti esistenti della Dashboard.
- Supportati panoramica giocatore/squadra, confronti, storico personale, filtri per ruolo, soglie e Top/Bottom.
- La metrica richiesta viene portata nella panoramica e nei grafici di dettaglio originali.
- I giocatori risultanti vengono applicati alla selezione e alle card standard della Dashboard.
- Nessun grafico alternativo viene creato quando esiste già un componente equivalente.
- Il pulsante “Ripristina” rimuove la configurazione applicata dall’assistente.

## Novità v3.1.2 — Metrica contestuale e analisi automatica della giornata

- Aggiunto un selettore della metrica accanto alla barra `Chiedi a PAS`.
- La metrica selezionata viene usata come contesto quando la richiesta non ne indica una esplicitamente.
- La metrica scritta nella richiesta testuale mantiene la priorità sul selettore.
- Aggiunto il comando `Analizza la giornata`, che produce automaticamente un riepilogo testuale oggettivo della metrica scelta.
- L’analisi automatica mostra media, mediana, massimo, minimo, numero di giocatori sopra/sotto media, grafico ordinato e tabella.
- Mantenuta invariata la Dashboard ordinaria e non aggiunti gli Insights automatici basati su regole.

## Novità v3.1.1 — PAS Conversational Dashboard

- Rimossa la selezione obbligatoria della metrica dalla barra `Chiedi a PAS`.
- La richiesta viene interpretata direttamente dal testo, inclusi giocatori, metrica, data, drill, soglie e Top/Bottom N.
- Il risultato compare in cima alla Dashboard solo dopo una richiesta.
- Aggiunta una risposta testuale con il grafico contestuale più adatto.
- Supportati confronto tra giocatori, seduta contro storico personale e classifiche/soglie per tutte le metriche PAS.
- La Dashboard ordinaria resta invariata sotto l'analisi conversazionale.
- Gli Insights automatici della seduta non sono inclusi in questa release e saranno definiti successivamente tramite regole dedicate.

## Novità v3.1.0 — PAS Dashboard Controller

- `Chiedi a PAS` controlla direttamente la Dashboard esistente e non genera più grafici separati
- Aggiornamento automatico di data, drill, metrica, giocatori e modalità delle card
- Filtri per qualunque metrica PAS con soglie `>`, `>=`, `<` e `<=`
- Conversione automatica delle unità, incluso `8 km` → `8000 m` per Distance
- Supporto a giocatori, ruoli, Top N, Bottom N e date esplicite
- Riepilogo persistente dei filtri applicati e pulsante `Ripristina Dashboard`
- Nessuna API esterna, nessuna modifica al database e compatibilità Streamlit Cloud

## Funzioni presenti

- Dashboard con periodo selezionabile
- Contesto della data scelta: Match Cycle, Match Day, Length Cycle, gara precedente e successiva
- Statistiche: media, mediana, deviazione standard, CV, minimo, massimo, P25, P75
- Metriche:
  - Distance
  - Z3
  - Z4
  - Speed Events
  - Max Speed
  - ACC Events
  - DEC Events
- Selezione multipla dei giocatori
- Confronto Team Average vs giocatori
- Historical Reference con giornate simili
- Confronto opzionale con la stessa Length Cycle
- Trend del periodo
- Box plot storico e distribuzione dei giocatori
- Pagine predisposte per Player Profiles e Return To Play

## Avvio

1. Metti il database Excel nella stessa cartella di `app.py`.
2. Attiva l'ambiente virtuale.
3. Installa le librerie:

```cmd
pip install -r requirements.txt
```

4. Avvia:

```cmd
python -m streamlit run app.py
```

Il programma riconosce automaticamente un file `.xlsx` che contiene `Database Hellas` nel nome.


## Novità v0.2

- Panoramica contemporanea fino a 7 metriche
- Selezione delle metriche da mostrare
- Ogni card mostra media, mediana, SD e CV
- Delta della giornata rispetto alle giornate simili
- Grafici di dettaglio controllati da una metrica separata
- Key Insights ridotti a un massimo di 3 indicazioni realmente rilevanti


## Novità v0.3

- Selezione del giorno da analizzare tramite elenco delle sole date presenti nel database
- Panoramica commutabile tra Team e singolo giocatore
- Statistiche multi-metrica individuali
- Delta individuale rispetto allo storico delle giornate simili
- Historical Reference individuale
- Trend principale del giocatore selezionato, con altri giocatori sovrapponibili


## Correzione calcoli v0.4

- La card principale mostra il valore della data e del drill selezionati, non la media del periodo
- Il filtro Drill è singolo e contiene solo i drill presenti nella data scelta
- Team del giorno = media tra gli atleti dopo aggregazione giornaliera
- Distance, Z3, Z4, Speed Events, ACC e DEC vengono sommati per atleta nella giornata
- Max Speed usa il massimo giornaliero per atleta
- Media, mediana, SD e CV del periodo restano visibili come riferimento sotto ogni card
- Aggiunta tabella di verifica con tutti i valori individuali usati per calcolare la media Team


## Novità v0.6

- Nomenclatura estesa con unità di misura:
  - Distance (m)
  - Distance 19.8-25.2 km/h (m)
  - Distance >25.2 km/h (m)
  - Speed Events (n°)
  - Max Speed (km/h)
  - Acc Events (n°)
  - Dec Events (n°)
- Mini box plot per ogni parametro della panoramica
- Team Overview confrontato con le medie team delle sedute simili
- Player Overview confrontato con lo storico dello stesso giocatore


## Novità v0.7

- Hover dei punti storici con Match Cycle
- Data della seduta visibile nell'etichetta
- Valore della metrica visibile nell'etichetta
- Funzione disponibile sia per Team Overview sia per Player Overview
- Match Cycle disponibile sia nei mini box plot sia nel box plot storico principale


## Novità v0.8

- Max Speed (km/h) visualizzata con 1 decimale
- Tutte le altre metriche visualizzate senza decimali
- Regola applicata a card, statistiche, tabelle, box plot e hover
- CV e scostamenti percentuali restano con 1 decimale
- Z-score resta con 2 decimali


## Correzione v0.8.1

- Ripristinata la funzione globale `metric_decimals()` prima del suo utilizzo.


## Correzione v0.8.2

- Risolto l'errore nella sezione "Tabella statistica completa"
- Le colonne vengono convertite correttamente prima di applicare la formattazione testuale


## Novità v0.9

- Selezione del giorno tramite calendario
- Controllo automatico delle date realmente presenti nel database
- Unità di misura rimossa dal numero grande nelle card
- Unità di misura mantenuta nel nome della metrica
- Titoli delle metriche ingranditi e resi più evidenti
- Valori principali leggermente più grandi


## Dashboard v1.0

- Card KPI personalizzate e più leggibili
- Titoli delle metriche nettamente più grandi
- Valore del giorno molto più evidente
- Unità di misura presente solo nel titolo della metrica
- Metriche organizzate per Volume, High Speed Running, Mechanical e Speed
- Indicatore visivo basato sullo z-score rispetto allo storico
- Mini box plot integrato nella stessa card
- Media, mediana, SD e CV compatti sotto il valore


## Novità v1.1 — Accumulo personalizzato

- Accumulo selezionabile per intervallo di date
- Accumulo selezionabile per uno o più Match Cycle
- Il Drill dell'accumulo coincide con il Drill selezionato nella Dashboard
- Distance, HSR, Speed Events, Acc e Dec vengono sommati
- Max Speed restituisce il picco del periodo
- Team Overview: media degli accumuli individuali
- Player Overview: accumulo diretto del giocatore selezionato
- Tabella di verifica dell'accumulo


## Novità v1.2 — Grafici multi-metrica

- Selezione multipla delle metriche per i grafici di dettaglio
- Una scheda separata per ogni metrica selezionata
- Colore stabile e distinto per ciascuna metrica
- Colori applicati alle barre del confronto Team vs Players
- Colori applicati anche allo storico e alla linea principale del trend
- Scale separate per evitare confronti visivi fuorvianti tra metriche con unità diverse


## Correzione v1.2.1

- Corretta e verificata la firma di `historical_boxplot`
- Chiamata con argomenti nominati
- Controllo automatico contro file di versioni miste


## Novità v1.3 — Dettaglio metriche nella stessa sezione

- Rimosse le schede cliccabili per le metriche di dettaglio
- Tutte le metriche selezionate sono mostrate una sotto l'altra
- Ogni metrica ha le proprie barre orizzontali
- Ogni parametro mantiene colore e scala dedicati
- Historical Reference, confronto e trend sono visibili senza cambiare scheda


## Correzione v1.3.1

- Ripristinata la costante `CHARTS_MODULE_VERSION`
- Allineato il controllo di versione tra `app.py` e `modules/charts.py`
- Verificato l'import completo del modulo grafici


## Installazione pulita v1.3.2

Questa distribuzione è pensata per sostituire completamente la precedente cartella PAS.
Usare `INSTALLA_E_AVVIA.bat` per creare un nuovo ambiente `.venv`, installare le dipendenze,
verificare i moduli e avviare l'applicazione.


## Novità v1.4 — Team Average vs Players multi-metrica

- Tutte le metriche selezionate sono visualizzate nello stesso confronto
- Barre orizzontali raggruppate e colore distinto per ogni metrica
- Valori normalizzati sul Team Average = 100%
- Hover con valore originale e unità di misura
- Tabella espandibile con i valori originali


## Novità v1.5 — Barre giocatori e Media Team

- Rimossa la normalizzazione percentuale sul Team Average
- Ogni metrica mantiene il proprio valore reale e la propria unità di misura
- Una barra orizzontale per ogni giocatore selezionato
- Una barra aggiuntiva con la Media Team per ogni metrica
- Tutte le metriche selezionate sono visibili nella stessa sezione
- Grafici disposti su due colonne per maggiore compattezza


## Correzione v1.5.1

- Rimosso l'import obsoleto `multi_metric_comparison_chart`
- Allineati `app.py` e `modules/charts.py`
- Verificato l'import completo dell'applicazione


## Novità v1.6 — Confronto giocatori nella Panoramica del giorno

- Ogni card mantiene il confronto con le sedute simili
- Sotto al box plot compare il confronto con i giocatori della stessa giornata
- Barre orizzontali con valore numerico
- Linea verticale tratteggiata della Media Team
- Possibilità di mostrare tutta la squadra oppure solo i giocatori selezionati
- Nella Player Overview il giocatore scelto può essere evidenziato


## Novità v1.7 — Trend selezionabile

- Nuovo filtro indipendente `Metriche per Trend del periodo`
- Possibilità di selezionare una o più metriche
- La selezione del Trend non dipende dai grafici di dettaglio
- Ogni metrica conserva colore, scala e unità propri
- Trend disposti su due colonne quando vengono selezionate più metriche


## Novità v1.8 - Internal Load e Report PDF

Nuove metriche integrate in tutte le analisi:
- RPE
- Anaerobic Threshold Zone (mm:ss)
- High Intensity Training (mm:ss)
- Duration (min), visualizzata senza decimali

Nuova organizzazione:
- Internal Load
- Volume
- High Speed Running
- Mechanical Load
- Speed

Report Builder:
- checkbox "Aggiungi al report PDF" sotto ogni grafico
- selezione libera di più grafici
- generazione di un PDF completo
- download e stampa del report


## Novita v1.9 - Session Report completo

Nuovo Session Report ispirato al report di sessione fornito come esempio:
- intestazione con data, Match Day, Match Cycle, drill e Time of Day;
- metriche selezionabili;
- tutti i giocatori presenti nella giornata;
- riga Team Average;
- mini-barre individuali dentro ogni cella;
- linea verticale rossa della Media Team;
- valori reali con formattazione corretta;
- suddivisione automatica su piu pagine quando metriche o giocatori sono numerosi;
- PDF pronto per download e stampa.

Il precedente Report grafici rimane disponibile separatamente.


## Novità v1.10 — Accumuli corretti per Team e Player

### Team Overview
L'accumulo include:
- il drill selezionato;
- il drill Match.

### Player Overview
L'accumulo include:
- il drill selezionato;
- Match;
- Individual Training;
- Different Training;
- Active Recovery;
- Return to Play.

È gestita anche la variante presente nel database `Different Traning`.

### Session Report
- intestazione PAS più professionale;
- migliore gerarchia grafica;
- numero di giocatori e metriche evidenziato;
- riga Team Average più visibile.


## Novità v1.11 — Sidebar riorganizzata

Nuovo ordine dei filtri:
1. Giorno da analizzare
2. Drill
3. Confronto giocatori del giorno
4. Panoramica principale
5. Metriche della panoramica
6. Metriche per grafici di dettaglio
7. Accumulo carico
8. Periodo e metriche per Trend, collocati in fondo

Sono stati aggiunti titoli e separatori per rendere la sidebar più leggibile.


## Novità v1.12 - Session Report in una sola pagina

- Tutte le metriche selezionate sono impaginate sulla stessa pagina.
- Formato A2 orizzontale per mantenere leggibilità e impatto visivo.
- Tutti i giocatori e la riga Team Average restano nello stesso foglio.
- Barre individuali e linea rossa della Media Team.
- Intestazioni metriche abbreviate e organizzate come nel report di riferimento.
- Impaginazione compatta ispirata al Session Report fornito come esempio.

## Novità v1.13 - Professional Session Report A4

- Un'unica pagina A4 orizzontale.
- Ordine colonne: DIST, AT, HIT, ACC, DEC, HSR, SPR, SPD, MAX, MIN, RPE.
- RPE, MIN, AT e HIT sono colonne compatte senza barra.
- Micro-barre e linea della Media Team per le altre metriche.
- Header, margini, font e griglia ottimizzati per la stampa.


## Novità v1.14 - Ordine e visualizzazione Professional Report

Ordine colonne:
1. Duration
2. Distance
3. Anaerobic Threshold
4. High Intensity Training
5. Acc Events
6. Dec Events
7. HSR
8. Sprint Distance
9. Speed Events
10. Max Speed
11. RPE

Visualizzazione:
- Duration: solo numero
- RPE: solo numero
- Tutte le altre metriche: numero + barra
- Ogni metrica mantiene un colore dedicato e distinto

## Novità v1.15

- Accumulo Team fisso: Full Training + Match.
- Accumulo Player fisso: Full Training, Individual Training, Return to Play,
  Active Recovery, Different Training, Match e Recovery.
- Il filtro Drill della giornata non modifica l'accumulo.
- Tabella di verifica delle sedute incluse.
- Nel Session Report, Different Training è escluso dalla Team Average
  e compare in fondo in una sezione separata.


## Novità v1.16 - Barre nella Team Average

- La riga Team Average mostra ora sia il numero sia la barra colorata.
- Ogni barra mantiene il colore specifico della propria metrica.
- Duration e RPE restano visualizzate solo come numero.
- La barra della Team Average è leggermente più intensa per distinguerla.
- La linea rossa resta esclusivamente nelle righe dei giocatori,
  perché rappresenta il riferimento della Team Average.


## Novità v1.17 - Team Average definitiva

- Rimossa la dicitura `- FULL TRAINING`.
- La prima cella `TEAM AVERAGE` resta evidenziata in giallo.
- Le celle delle metriche della Team Average hanno sfondo bianco.
- Ogni metrica mantiene la propria barra colorata.
- I valori della Team Average restano in grassetto.
- Duration e RPE continuano a essere visualizzate solo come numero.


## Novità v1.18 - Separazione visiva del report

- Inserito uno spazio bianco tra Team Average e giocatori Full Training.
- Inserito uno spazio bianco leggermente più ampio prima di Different Training.
- I tre blocchi del report sono ora più leggibili:
  1. Team Average
  2. Full Training
  3. Different Training
- Tutte le informazioni restano contenute nella singola pagina A4 orizzontale.


## Novità v1.19 - Team Average ampliata

- Riga Team Average più alta del 35%.
- Barre Team Average più alte e più leggibili.
- Numeri Team Average più grandi.
- Scritta Team Average più grande.
- Nella sezione Different Training è stata rimossa la linea della media.
- Different Training mostra solo barra colorata e valore.


## Novità v1.20 - Database caricabile

- Caricamento diretto di un database Excel dalla sidebar.
- Supporto `.xlsx` e `.xls`.
- Fallback automatico al database presente nella cartella PAS.
- Il file caricato non sovrascrive il database locale.
- Validazione automatica delle colonne obbligatorie.
- Riepilogo di righe, giocatori, sessioni e intervallo date.
- Elenco dei drill trovati.
- Avviso in caso di metriche PAS mancanti.
- Pulsante per ricaricare i dati e svuotare la cache.


## Novità v1.21 - Nuovo ordine dei filtri

Dopo Giorno da analizzare e Drill, la sidebar segue questo ordine:

1. Panoramica
2. Session Report
3. Accumulo carico
4. Confronto giocatori del giorno
5. Grafici di dettaglio
6. Trend del periodo

I controlli del Session Report sono ora collocati immediatamente
sotto la Panoramica.


## Novità v1.22 - Etichette complete e colori report

- Colore di Distance e Acc Events invertito nel solo Session Report.
- Etichette complete:
  - Duration
  - Distance
  - Anaerobic Threshold
  - High Intensity Training
  - Acc Events
  - Dec Events
  - Distance 19.8-25.2
  - Distance >25.2
  - Speed Events
  - Max Speed
  - RPE
- Tutte le colonne metriche hanno la stessa larghezza.
- Duration e RPE restano più strette.
- Le etichette lunghe vengono distribuite su due righe.


## Novità v1.23 - Session Report nella sua sezione

- Il pulsante `Genera Session Report PDF` è ora dentro
  la sezione Session Report della sidebar.
- Titolo, metriche, scelta giocatori, generazione e download
  sono tutti riuniti nello stesso blocco.
- Il pulsante è evidenziato come azione principale e occupa
  tutta la larghezza della sidebar.
- Quando si sceglie `Solo giocatori selezionati`, compare
  un selettore dedicato esclusivamente al report.
- Rimosso il vecchio pulsante collocato nella parte inferiore.


## Correzione v1.23.1

- Risolto `NameError: name 'context' is not defined`.
- Il Session Report calcola ora autonomamente Match Day e Match Cycle
  tramite `context_for_date(raw, reference_ts)`.
- Il pulsante resta nella sezione Session Report della sidebar.


## Novità v1.24 - Totali di periodo

Nuova voce di navigazione subito sotto Dashboard:
- Totali di periodo

Funzioni:
- selezione per intervallo di date;
- selezione di uno o più Match Cycle;
- selezione libera dei giocatori;
- selezione delle metriche;
- barre orizzontali per ogni metrica;
- somma delle metriche cumulative;
- picco per Max Speed;
- media per RPE;
- drill individuali inclusi secondo la logica PAS;
- tabella di verifica delle sedute;
- Period Load Report PDF nello stesso stile del Session Report.

La sezione Database è ora compatta e chiusa di default.


## Correzione v1.25 - Accumulo Dashboard

- La Dashboard mostra ora la somma del periodo, non la media.
- In Team Overview viene mostrato il totale complessivo dei giocatori inclusi.
- In Player Overview viene mostrato il totale del giocatore selezionato.
- Max Speed continua a riportare esclusivamente il valore più alto.
- Drill inclusi:
  Full Training, Individual Training, Return to Play,
  Active Recovery, Different Training, Match e Recovery.
- Gestita anche la variante `Different Traning`.


## Novità v1.26

### Trend del periodo
- Nuovo menu `Soggetto del Trend`.
- È possibile selezionare `Tutto il Team` oppure un singolo giocatore.
- Il Team mostra la media giornaliera dei giocatori.
- Il singolo giocatore mostra esclusivamente il proprio andamento.

### RPE nella Panoramica del giorno
- Rimosso il totale del periodo dalla card RPE.
- Restano valore della giornata, confronto storico e statistiche.
- Le altre metriche mantengono regolarmente il proprio accumulo.


## Correzione v1.26.1 - Card Panoramica

- Ripristinato il layout delle card della versione precedente.
- Risolto il problema dell'HTML mostrato come testo.
- Tutte le metriche mantengono il riquadro dell'accumulo.
- Solo RPE non mostra più l'accumulo del periodo.
- Il nuovo menu del Trend Team/Giocatore resta invariato.


## Novità v1.27 - Team Average del periodo

### Dashboard
- Team Overview: per ogni giornata viene calcolato il Team Average.
- Il totale del periodo è la somma dei Team Average giornalieri.
- Max Speed è il massimo dei Team Average giornalieri.
- Player Overview mantiene somma individuale e picco Max Speed.
- RPE resta senza accumulo nella Panoramica del giorno.

### Totali di periodo
- Nessun giocatore selezionato = Team Average del periodo.
- Uno o più giocatori selezionati = totali individuali.
- Le metriche sono sommate; Max Speed è il picco.
- RPE è mostrato come media del periodo.
- Il Period Load Report PDF usa la stessa logica.


## Correzione v1.27.1 - Etichette Trend

- `Soggetto del Trend` rinominato in `Giocatore del Trend`.
- `Tutto il Team` rinominato in `Team Average`.
- La logica del grafico non cambia:
  `Team Average` mostra la media giornaliera della squadra;
  selezionando un atleta viene mostrato il suo andamento individuale.


## PAS Demo v2.0

### Accesso
La Demo è protetta da password.

Password locale iniziale:

`PAS2026`

Prima della pubblicazione è consigliato cambiarla.

Per generare l'hash SHA-256 di una nuova password:

```python
import hashlib
print(hashlib.sha256("NUOVA_PASSWORD".encode()).hexdigest())
```

Su Streamlit Community Cloud inserire nei Secrets:

```toml
demo_password_hash = "HASH_GENERATO"
```

Non pubblicare un file `.streamlit/secrets.toml` nel repository.
È disponibile soltanto `secrets.toml.example`.

### Accumulo carico
La modalità predefinita è ora `Uno o più Match Cycle`.
Il ciclo corrispondente alla giornata analizzata viene selezionato
automaticamente quando disponibile.


## Correzione v2.0.1

- Corretto l'hash locale della password iniziale `PAS2026`.
- Modificare `PUBBLICAZIONE_DEMO.txt` non cambia la password:
  quel file contiene solo istruzioni.
- Per Streamlit Cloud bisogna modificare la sezione `Secrets`.
- Aggiunto `GENERA_HASH_PASSWORD.py` per creare facilmente l'hash.


## Correzione v2.0.2 - Password semplificata

La password della Demo si trova nel file:

`modules/security.py`

Per cambiarla, modifica soltanto questa riga:

```python
DEMO_PASSWORD = "PAS2026"
```

La modifica funziona sia in locale sia dopo la pubblicazione online.
Non sono più necessari hash o Streamlit Secrets.


## Novità v2.1.0

### Performance Model
- Modello individuale calcolato solo da Drill = Match.
- Esclusione outlier oltre ±2 deviazioni standard.
- Modello consolidato da almeno 5 partite valide.
- Target individuale per ogni metrica.
- MPE Rec Avg Time incluso esclusivamente nei moduli partita.

### Match Analysis
- Selezione rapida della singola partita.
- Team Average e valori individuali.
- Barre con target del modello individuale.
- Match Report PDF con linea rossa individuale per atleta e parametro.
- Confronto tra una o più partite.
- Totali Team Average o singolo giocatore.


## Correzione v2.1.1 - Metriche Match Report

Nuovo ordine del Match Report:
1. Duration
2. Distance
3. Relative Distance
4. MPE Rec Avg Time
5. Acc Events
6. Dec Events
7. Distance 19.8-25.2 km/h
8. Distance >25.2 km/h
9. High Intensity Running
10. Speed Events
11. Max Speed

`High Intensity Running` è calcolata come:
Distance 19.8-25.2 km/h + Distance >25.2 km/h.

`Relative Distance` usa la colonna `avg speed (m/min)`.


## Novità v2.1.3 - Modello prestativo normalizzato

Per Distance, Acc Events, Dec Events, HSR, Sprint/High Intensity
Running e Speed Events:

1. ogni partita viene normalizzata al minuto;
2. gli outlier sono esclusi sul valore per minuto;
3. il modello individuale è la media dei valori per minuto validi;
4. il target della partita viene calcolato come:
   modello al minuto × durata effettiva della partita.

Restano in valore assoluto:
- Max Speed;
- Relative Distance;
- MPE Rec Avg Time.

Duration resta una variabile di contesto e non mostra una linea target.
Il Match Report e il confronto tra partite usano target dinamici
specifici per la durata reale di ogni atleta nella partita.


## Novità v2.1.4 - Foto giocatori

- Integrate 37 foto dei giocatori nella cartella `assets/players`.
- Integrato anche il logo Hellas Verona tra gli asset disponibili.
- La pagina Performance Model mostra:
  - foto del giocatore;
  - nome;
  - ruolo;
  - stato del modello;
  - numero di partite disponibili;
  - data dell'ultima partita.
- Il riconoscimento delle immagini gestisce automaticamente:
  - ordine nome/cognome;
  - accenti;
  - trattini;
  - alias per Akpa-Akpro, Al-Musrati e Valentini.
- Se una foto manca, viene mostrato un profilo neutro.


## Baseline stabile v2.2.0

Questa versione consolida:

- Dashboard giornaliera;
- Totali di periodo;
- Match Analysis;
- Performance Model normalizzato al minuto;
- Match Report con target individuali;
- Relative Distance, MPE Rec Avg Time e High Intensity Running;
- foto dei giocatori;
- Session Report e Period Load Report;
- accesso Demo tramite password.

La versione dell'app è definita una sola volta in `modules/version.py`.

Il vecchio controllo bloccante tra `app.py` e `modules/charts.py`
è stato rimosso. Non può quindi più comparire il messaggio
`I file del PAS non appartengono alla stessa versione`.


## Correzione v2.2.1 - Match Analysis

- Il nome completo della metrica è visibile sopra ogni grafico
  nella sezione `Giocatori vs modello individuale`.
- `Team Average` è stato sostituito da `Totale della partita`.
- Il totale somma i valori di tutti i giocatori selezionati.
- Sono escluse dal totale:
  Max Speed, Relative Distance e MPE Rec Avg Time.


## Novità v2.2.2 - Confronto totali partita

- Nel confronto partite è possibile selezionare più metriche.
- La modalità predefinita è `Totale partita`.
- Il Totale partita somma tutti i giocatori della stessa partita.
- Max Speed, Relative Distance e MPE Rec Avg Time sono escluse
  perché non sommabili.
- È ancora possibile selezionare un singolo giocatore.
- Ogni metrica ha un grafico dedicato.
- Aggiunto il Match Comparison Report PDF nello stesso stile
  degli altri report.


## Correzione v2.2.3 - Confronto totali partita

- La modalità predefinita del confronto è `Totale partita`.
- Per ogni partita vengono sommati i valori di tutti i giocatori presenti.
- Il confronto avviene tra i totali complessivi delle diverse partite.
- Non viene utilizzata alcuna Team Average.
- Max Speed, Relative Distance e MPE Rec Avg Time restano escluse
  perché non sono metriche additive.
- Il PDF di confronto utilizza gli stessi totali partita.


## Correzione v2.2.4

- Risolto `NameError: name 're' is not defined` nella pagina
  Performance Model.
- Il riconoscimento automatico delle foto giocatori ora funziona
  correttamente anche su Streamlit Cloud.


## Novità v2.2.5 - Performance Model a 90 minuti

- Duration rimossa dai Parametri del modello prestativo.
- Tutte le metriche normalizzate sono proiettate sui 90 minuti.
- Ogni card mostra anche il valore al minuto con un decimale.
- Restano in valore assoluto:
  Relative Distance, Max Speed e MPE Rec Avg Time.
- La tabella Modello completo mostra sia il valore al minuto
  sia la proiezione sui 90 minuti.


## Correzione v2.2.6 - Match Report PDF

Nel Match Report PDF la riga superiore è `MATCH TOTAL`.

- Somma dei valori di tutti i giocatori per le metriche additive.
- Media dei giocatori per Relative Distance, MPE Rec Avg Time e Max Speed.
- La stessa logica è visibile anche nella singola partita di Match Analysis.


## Novità v2.2.7 - Distribuzione Performance Model

- Box plot per ogni parametro.
- Ogni punto rappresenta una partita.
- Selezione di una partita da evidenziare.
- Punto selezionato in giallo.
- Linea rossa del modello individuale.
- Metriche normalizzate visualizzate sui 90 minuti.
- Relative Distance, Max Speed e MPE Rec Avg Time restano assolute.


## Novità v2.2.9

- Tooltip box plot con data, partita e Match Cycle.
- Tutte le partite visualizzate, incluse quelle escluse dal modello ±2 SD.
- Report box plot selezionabile e adattato in una sola pagina A4.
- Dashboard report grafici adattato in una sola pagina A4.
- Colori specifici per ogni metrica mantenuti in stampa.


## Novità v2.3.0 - Totali di periodo vs Match

- Per ogni parametro viene calcolata la percentuale rispetto
  al riferimento gara individuale.
- Esempio: 20.000 m e riferimento gara 10.000 m = 200% Match.
- Il riferimento gara usa solo Drill = Match.
- Le metriche additive sono normalizzate al minuto,
  filtrate ±2 SD e proiettate sui 90 minuti.
- Duration, RPE e Max Speed usano la media assoluta delle partite.
- Nel riepilogo e nei grafici compare l'etichetta `% Match`.
- Nel Period Load Report la percentuale compare sotto
  al valore assoluto.
- Il report usa dinamicamente tutta l'altezza A4 in base
  al numero di giocatori inclusi.


## Correzioni v2.3.1

- Duration esclusa dal confronto percentuale con il carico gara.
- Nelle etichette compare solo la percentuale, senza la parola Match.
- Un solo selettore report per parametro nella Dashboard.
- Se un parametro contiene due grafici, una sola selezione li include entrambi.
- Export grafici PDF stabilizzato con Kaleido 0.2.1.
- Sfondo dei grafici PDF reso bianco per maggiore compatibilità.
- Nei tooltip dei box plot Performance Model rimangono:
  partita, data e valore; Match Cycle rimosso.


## Novità v2.3.2

- Nel report della Panoramica del giorno sono selezionabili solo i box plot.
- Punti storici colorati per Match Cycle con legenda.
- Giorno selezionato evidenziato con rombo giallo più grande.
- Session Report adattato per utilizzare tutta l'altezza del foglio A4.
- Altezza righe, font e spazi verticali regolati automaticamente.


## Novità v2.3.3 - Max Speed storica

### Period Load
- Max Speed non viene più confrontata con il carico gara.
- La percentuale indica la quota di Max Speed storica individuale
  raggiunta nel periodo.
- Esempio: 31,0 km/h su storico 33,0 km/h = 94% max storica.
- Logica applicata a schermata, grafici e PDF.

### Session Report
- Sotto la Max Speed di ogni giocatore compare la percentuale
  rispetto alla sua Max Speed storica.
- Il riferimento è il valore massimo registrato nel database
  per quello specifico giocatore.


## Novità v2.3.4 - Performance Model Report

- Titolo PDF aggiornato automaticamente con il giocatore selezionato.
- La linea tratteggiata mostra `AVG` e il relativo valore.
- Il rombo della partita selezionata mostra `SELECTED` e il valore.
- Nelle card sono visibili AVG e valore della partita selezionata.


## Correzioni v2.3.5

- Box plot Performance Model con valori al minuto per tutte le metriche
  tranne Relative Distance, Max Speed e MPE Rec Avg Time.
- Tutte le partite restano visibili nel box plot.
- Il modello AVG continua a escludere gli outlier oltre ±2 SD.
- Sul rombo selezionato compare soltanto il valore, nero e in grassetto.
- Rimossa la dicitura `max storica` da Period Load e Session Report:
  rimane visibile solo la percentuale.


## Restyling v2.4.0

- Logo Hellas Verona FC nella sidebar e nell'header di tutte le pagine.
- Logo discreto nell'header di tutti i report PDF.
- Firma discreta `Performance Analysis System | Hellas Verona FC`.
- Spinner di caricamento sostituito da un pallone da calcio rotante.
- Icona dell'app aggiornata al pallone.
- Distance rimossa esclusivamente dai box plot del Performance Model.
- Distance resta disponibile nelle card superiori del modello.


## Novità v2.5.0

### Navigazione
- `Totali di periodo` rinominato `Period Load`.
- Aggiunte le sezioni `Forecast` e `Drills`.
- `Player Profiles` spostata in fondo.

### Forecast
- Dati dal foglio `Esercitazioni Avg`.
- Selezione del ruolo.
- Selezione di più drill e relativa durata.
- Calcolo automatico di Distance, ACC, DEC, Z3, Z4 e Speed Events.
- Totale della seduta e grafici per metrica.
- Forecast Session Report PDF a colori.

### Drills
- Dati dal foglio `Esercitazioni`.
- Filtro per Team Average o ruolo.
- Box plot con valori normalizzati al minuto.
- Statistiche descrittive e Drills Analysis Report PDF.

### Rifiniture
- Riepilogo percentuale del Period Load spostato dopo i grafici.
- Rimossa la dicitura `PAS - PERFORMANCE ANALYSIS SYSTEM`
  dall'header dei report.


## Correzioni v2.5.1

### Forecast
- Sostituito il data editor con selettori stabili riga per riga.
- La selezione del drill viene applicata immediatamente.
- Cambiando ruolo vengono aggiornate correttamente le opzioni.
- Forecast Report ridisegnato nello stile del Session Report.
- I drill sostituiscono gli atleti nelle righe del report.
- Righe e spazi adattati all'intera altezza A4.

### Drills Analysis
- Linea tratteggiata AVG con valore su ogni drill nella pagina.
- Nel PDF AVG e valore sono neri e in grassetto.
- Il report continua a mantenere colori diversi per i drill.


## Correzioni v2.5.2

### Forecast
- Z3 rinominata `Distance 19.8-25.2 km/h (m)`.
- Z4 rinominata `Distance >25.2 km/h (m)`.
- Anche ACC e DEC usano i nomi del Session Report:
  `Acc Events (n°)` e `Dec Events (n°)`.
- Il Forecast Report utilizza direttamente il motore grafico
  del Session Report.
- Stessa intestazione, colonne, colori, riga TOTAL e adattamento
  automatico a tutta l'altezza del foglio A4.
- Nel report la prima colonna è `DRILL` invece di `PLAYER`.

### Drills
- Escluse tutte le esercitazioni con nome `/`
  sia dal foglio `Esercitazioni` sia da `Esercitazioni Avg`.


## Correzione v2.5.3 - Loader PAS

- Nascosta l'animazione di stato nativa di Streamlit.
- Sostituiti tutti gli `st.spinner()` del PAS con un loader proprietario.
- Il loader mostra un pallone da calcio rotante e il messaggio
  relativo all'operazione in corso.
- Applicato alla creazione di:
  - Period Load Report;
  - Forecast Session Report;
  - Drills Analysis Report;
  - Session Report;
  - PAS Dashboard Report.

Nota: durante il primissimo caricamento tecnico della pagina il browser
può mostrare per un istante elementi gestiti direttamente da Streamlit,
prima che il CSS dell'app venga applicato.


## Correzioni v2.5.4

### Drills Analysis
- ACC/min rinominata `Acc Events/min`.
- DEC/min rinominata `Dec Events/min`.
- Z3/min rinominata `Distance 19.8-25.2 km/h/min`.
- Z4/min rinominata `Distance >25.2 km/h/min`.
- I nuovi nomi sono applicati sia nella pagina sia nel PDF.

### Report PDF
- Rimossa la causa delle pagine finali vuote nei report tabellari.
- Logo, footer e contenuto restano sulla stessa pagina.

### Forecast
- Le righe si espandono dinamicamente in base al numero di drill.
- Con 5 drill, ad esempio, la tabella occupa tutta l'altezza utile
  del foglio A4 mantenendo la grafica del Session Report.


## Correzioni v2.5.5

### Nomenclatura Drills definitiva
- `Relative Distance (m/min)`
- `Acc Events (n°/min)`
- `Dec Events (n°/min)`
- `19.8-25.2 km/h (m/min)`
- `>25.2 km/h (m/min)`
- `Speed Events (n°/min)`

I nuovi nomi sono applicati:
- nei filtri;
- nei titoli dei box plot;
- nelle tabelle statistiche;
- nei report PDF.

### Report
- Ridotta la lunghezza massima dei titoli dei grafici nel PDF
  per evitare sovrapposizioni.
- Mantenuta la generazione su una sola pagina senza pagina finale vuota.
- Il Forecast continua ad adattare l'altezza delle righe al numero di drill.


## Correzioni v2.5.6

### Drills
- Corretto l'AttributeError nella Statistical Summary.
- Le colonne mancanti vengono ora gestite come serie vuote,
  senza interrompere l'app.
- La stessa protezione è applicata anche ai box plot.
- Se una metrica non è disponibile nel foglio `Esercitazioni`,
  viene mostrato un avviso chiaro.

### Period Load
- Tutti i giocatori sono selezionati di default.
- Dalla sidebar è possibile deselezionare quelli da escludere.


## Hotfix v2.5.7

- Corretto l'AttributeError nella sezione Drills.
- Gestite colonne mancanti e intestazioni duplicate.
- Sostituiti 3 accessi non sicuri basati su `.get(...).dropna()`.
- Le metriche non disponibili vengono saltate senza interrompere l'app.
- Tutti i giocatori restano selezionati di default nel Period Load.


## Correzioni v2.5.8

### Drills
- Corretto il riconoscimento di `Speed Events (n°/min)`.
- Il PAS riconosce anche varianti dell'intestazione come:
  - `Speed Events/min`
  - `speed events/min`
  - `speed events /min`
  - `Sprint/min`
- Aggiunta la stessa gestione robusta per ACC, DEC, Z3 e Z4 al minuto.

### Period Load
- All'apertura viene selezionata di default la modalità
  `Uno o più Match Cycle`.
- È selezionato automaticamente il ciclo gara più recente.
- L'intervallo di date resta disponibile come scelta manuale.


## Hotfix v2.5.9

### Drills
- Corretto il collegamento tra l'etichetta visibile
  `Speed Events (n°/min)` e la colonna reale del database
  `Speed Events/min`.
- Rimossa la falsa segnalazione di dato non disponibile.
- Mantenuto il riconoscimento delle varianti dell'intestazione.


## Modifica v2.5.10

### Panoramica del giorno
- La legenda dei Match Cycle non viene più mostrata nella schermata.
- I punti mantengono comunque i colori distinti per ciclo.
- Nel report PDF la legenda dei Match Cycle resta visibile.
- Interfaccia e PDF utilizzano due versioni dedicate dello stesso grafico.


## Modifica v2.5.11

### Panoramica del giorno
- Nella schermata tutti i punti storici hanno lo stesso colore.
- Il rombo della giornata selezionata resta evidenziato.
- Nel report PDF i punti mantengono colori diversi per Match Cycle.
- La legenda dei Match Cycle resta presente solo nel report.


## Novità v2.6.0 - Daily Planner

- Nuova sezione `Daily Planner` dopo Period Load.
- Calendario mensile cliccabile.
- Apertura e compilazione di ogni giornata.
- Attività disponibili:
  Field Session, Gym Session, Pre-Activation, Video Analysis,
  Official Match, Friendly Match, Recovery, Medical / RTP,
  Day Off e Other.
- Partecipanti selezionabili:
  - per l'intera giornata;
  - per ogni attività;
  - per ogni singola esercitazione della Field Session.
- Field Session con esercitazioni, durata e partecipanti.
- Possibilità di usare drill del database o nomi personalizzati.
- Salvataggio, modifica, duplicazione ed eliminazione della giornata.
- Daily Planner Report PDF.
- Backup e ripristino tramite file JSON.

### Persistenza
Il planner viene salvato in `data/daily_planner.json`.
Su Streamlit Community Cloud il filesystem può essere ricreato durante
riavvii o nuovi deploy: utilizzare il pulsante di esportazione JSON
per conservare un backup persistente.


## Ottimizzazione v2.6.1 - Daily Planner

### Prestazioni
- Rimossa la generazione simultanea di tutti i moduli attività e drill.
- Si modifica una sola attività e una sola esercitazione alla volta.
- Salvataggi tramite form, con meno rerun e meno componenti attivi.
- Calendario e editor separati in schede.

### Calendario
- Nuova griglia mensile 7x6 con celle uniformi.
- Ogni giorno mostra attività e partite programmate.
- Click sul giorno per aprire la giornata.

### Partite
- Nuova scheda `Partite in programma`.
- Inserimento rapido di data, tipo, avversario, sede, orario
  e competizione.
- Le partite compaiono automaticamente nel calendario.

### Stato giocatori
- Nuova tabella con tag:
  Full Training, Different Training, Return to Play,
  Individual Training, Gym Only, Medical, Not Available,
  National Team e Rest.
- Stato e note individuali salvati per ciascun giorno.
- I giocatori indisponibili non vengono proposti tra i partecipanti.


## Modifica v2.6.2 - Daily Planner

- Rimossa la scheda separata `Partite in programma`.
- Cliccando su un giorno del calendario si entra direttamente nella giornata.
- Nella giornata vuota si sceglie:
  - `Crea giornata di allenamento`
  - `Crea partita`
- Ripristinata la struttura allenamento con:
  attività, partecipanti, esercitazioni e minuti.
- Mantenuto l'editor leggero: una sola attività e una sola esercitazione
  vengono modificate alla volta.
- Le partite vengono inserite direttamente dentro la giornata selezionata.
- Pulsante dedicato per tornare al calendario.


## Novità v2.7.0 - Planner

- La sezione si chiama ora `Planner`.
- Calendario mensile cliccabile.
- Entrando nel giorno si sceglie:
  - Allenamento
  - Partita
- Interfaccia allenamento semplificata e lineare.
- Attività aggiungibili con pulsanti rapidi:
  Field Session, Gym Session, Pre-Activation,
  Video Analysis, Recovery e Other.
- Ogni attività è una card completa con:
  titolo, orario, durata, partecipanti e note.
- Field Session con esercitazioni e minuti.
- Stato giocatori compatto, con editor completo dentro un expander.
- Un solo pulsante `Salva giornata`.
- Duplica, PDF e salvataggio come template.
- Possibilità di applicare un template a una giornata vuota.


## Modifiche v2.7.1 - Planner

### Partecipanti di default
- Nelle attività `Field Session` e `Pre-Activation`
  vengono selezionati di default soltanto i giocatori con stato:
  - Full Training
  - Different Training
- Return to Play, Individual Training, Gym Only, Medical,
  Not Available, National Team e Rest non vengono inclusi
  automaticamente.
- Rimane possibile aggiungerli manualmente alla singola attività.

### Allegati
- Ogni attività può contenere un allegato.
- Formati supportati: PDF, Word, Excel, PowerPoint, TXT, CSV
  e immagini JPG/PNG.
- L'allegato può essere scaricato o rimosso.
- Il file viene incorporato nel backup JSON del Planner.
- Per prestazioni migliori sono consigliati file inferiori a 5 MB.


## Modifiche v2.7.2 - Planner

### Ordinamento automatico
- Le attività vengono ordinate automaticamente in base all'orario di inizio.
- L'ordine di creazione non influenza più la visualizzazione.
- Gli orari mancanti o non validi vengono posizionati in fondo.
- L'ordinamento viene applicato sia nella schermata sia al salvataggio.

### Partecipanti di default
- Per `Field Session` e `Pre-Activation` vengono inclusi automaticamente
  soltanto i giocatori con stato:
  - Full Training
  - Different Training
- Tutti gli altri stati non compaiono di default in queste due attività.
- Rimane comunque possibile aggiungere manualmente qualsiasi giocatore.


## Modifica v2.7.3 - Calendario Planner nella Dashboard

- Aggiunto un calendario Planner compatto in alto a destra nella Dashboard.
- Il calendario è esclusivamente in visualizzazione e non è modificabile.
- Mostra il mese corrente e le attività già programmate.
- Ogni giornata mostra fino a due attività, con colore coerente al tipo.
- Le giornate con più attività mostrano un indicatore aggiuntivo.
- La giornata odierna è evidenziata con un bordo discreto.
- Il componente è realizzato in HTML compatto per limitare l'impatto
  sulle prestazioni della Dashboard.


## Modifica v2.7.4 - Esercizi Gym e Pre-Activation

- Anche `Gym Session` e `Pre-Activation` possono contenere
  un elenco di esercizi.
- Per ogni esercizio è possibile inserire:
  - nome;
  - durata in minuti;
  - partecipanti.
- La durata totale dell'attività viene calcolata automaticamente
  dalla somma degli esercizi.
- `Field Session` continua a usare la dicitura `Esercitazioni`.
- `Gym Session` e `Pre-Activation` usano la dicitura `Esercizi`.
- Gli esercizi vengono inclusi nel Planner PDF tramite la stessa
  struttura già utilizzata per la Field Session.


## Modifica v2.7.5 - Navigazione calendario Dashboard

- Il calendario Planner compatto nella Dashboard permette ora
  di spostarsi tra i mesi.
- Aggiunti i pulsanti mese precedente e mese successivo.
- Il mese selezionato rimane memorizzato durante la sessione.
- Il calendario resta esclusivamente in visualizzazione:
  non è possibile modificare le giornate dalla Dashboard.
- Il componente mantiene dimensioni compatte in alto a destra.


## Modifica v2.7.6 - Mini calendario Dashboard

- Il calendario Planner è stato spostato visivamente più in alto.
- La colonna destra è stata ridotta dal 28% al 23% della larghezza.
- Celle, testi, margini e spazi sono stati ridotti.
- Ogni giorno mostra una sola attività e un indicatore `+N`
  quando ne sono presenti altre.
- Restano disponibili i pulsanti per cambiare mese.
- Il calendario rimane esclusivamente in visualizzazione.


## Modifica v2.7.7 - Dashboard e Planner

- Nel mini calendario della Dashboard puoi continuare a cambiare mese
  usando le frecce, senza entrare nel Planner.
- Aggiunto un pulsante separato `Apri Planner`.
- Solo quel pulsante apre il Planner.
- Il Planner si apre sul mese attualmente visualizzato nella Dashboard.
- Il mini calendario resta non modificabile.


## Hotfix v2.7.8 - Apertura Planner dalla Dashboard

- Corretto lo `StreamlitAPIException` del pulsante `Apri Planner`.
- La modifica della pagina viene ora eseguita tramite callback,
  prima che Streamlit ricrei il widget di navigazione.
- Le frecce del mini calendario continuano a cambiare mese
  senza aprire il Planner.
- Il pulsante apre il Planner sul mese visualizzato nella Dashboard.


## Novità v2.8.0

### Planner - partite
- La partita è mostrata come `AVVERSARIO (H)` o `AVVERSARIO (A)`.
- Il nome dell'avversario è in stampatello maiuscolo.
- Per sede neutra viene usato `(N)`.

### Planner - libreria esercizi
- È possibile creare un esercizio personalizzato al momento.
- L'esercizio può essere salvato solo nella seduta oppure aggiunto
  alla libreria del Planner.
- È possibile assegnare una categoria.
- Gli esercizi salvati in libreria compaiono nelle selezioni successive.
- La libreria è inclusa nel backup JSON.

### Drills Analysis
- Modalità di analisi per `Roles` oppure per `Players`.
- Selezione multipla dei ruoli, con colori differenti.
- Per i ruoli, ogni punto rappresenta la media del ruolo
  in una singola occorrenza Drill-Date.
- Team Average è la media di tutti i giocatori nell'occorrenza.
- Possibilità di vedere tutti i giocatori oppure uno o più giocatori.
- In modalità Players, ogni punto rappresenta il valore del singolo
  giocatore in una singola occorrenza Drill-Date.
- Più drill possono essere confrontati contemporaneamente.
- Riepilogo statistico e PDF aggiornati per ruolo o giocatore.

## Modifica v3.0.1 - Palette PAS nei box plot Drills

- Applicata la palette PAS ai box plot della sezione `Drills`.
- Ogni grafico usa il colore ufficiale associato alla metrica analizzata.
- La stessa palette è applicata sia nella schermata Streamlit sia nel report PDF.
- Nessuna modifica alla logica di calcolo, ai dati o alle altre visualizzazioni.



## Novità v3.0.3 - Riconoscibilità Roles / Players nei Drills

- La sezione `Drills` permette di scegliere la modalità di analisi `Roles` oppure `Players`.
- In modalità `Roles`, `Team Average` rappresenta la media di tutti i giocatori presenti nella singola occorrenza; gli altri ruoli rappresentano la media dei giocatori del ruolo nella stessa occorrenza.
- In modalità `Players`, ogni punto rappresenta il valore del singolo giocatore nella specifica coppia data-drill.
- Ogni punto dei box plot corrisponde a una sola occorrenza `Drill-Date`, identificata anche nell’hover.
- Il riepilogo statistico conta le occorrenze distinte e il report PDF riporta la modalità selezionata.
- La palette PAS introdotta nella v3.0.1 resta applicata per metrica, senza modifiche alle altre funzionalità.

### Riconoscibilità nei box plot Drills
- Il colore dei box e dei punti resta associato alla metrica secondo la palette PAS.
- In modalità `Roles`, ogni ruolo usa un simbolo distinto e viene indicato sopra il relativo box plot.
- In modalità `Players`, ogni giocatore usa un simbolo ciclico, un nome abbreviato sopra il box e il nome completo in legenda e hover.
- La stessa codifica visiva viene mantenuta nei grafici esportati nel report PDF.

## Novità v3.0.4 - Colori Roles / Players nei Drills

- I box plot continuano a usare il colore PAS previsto per ciascuna metrica.
- I punti delle occorrenze usano colori distinti e stabili per ogni ruolo o giocatore selezionato.
- Le etichette sopra i box e i valori medi a schermo riprendono il colore dell’entità per facilitarne il riconoscimento.
- La legenda chiarisce che il colore dei punti identifica il ruolo o il giocatore.
- La stessa codifica viene mantenuta nei grafici del Drills Analysis Report PDF.
- Calcoli, modalità Roles / Players e dati del database restano invariati.


## Novità v3.0.5 - Box plot colorati per Roles / Players nei Drills

- In modalità Roles, ogni box plot usa il colore assegnato al ruolo.
- In modalità Players, ogni box plot usa il colore assegnato al giocatore.
- I punti mantengono lo stesso colore del relativo box plot.
- La legenda associa chiaramente ogni colore al ruolo o al giocatore.
- Rimosse le etichette testuali sopra i box plot.
- La stessa rappresentazione viene utilizzata nella schermata e nel report PDF.

## PAS Intelligence Engine (v3.2.0)

PAS Intelligence può interpretare una richiesta dalla barra compatta e indirizzare automaticamente l’utente alla sezione più coerente del software. La prima versione gestisce Dashboard, Drills, Match Analysis, Period Load, Planner, Forecast e Return To Play.

Il motore riconosce giocatori, ruoli, metriche, drill, date, soglie, classifiche e richieste di storico. Quando possibile preconfigura i controlli già presenti nella sezione scelta; non genera componenti alternativi se esiste già una vista equivalente nel PAS. Le richieste individuali e storiche restano nella Player Overview della Dashboard finché la pagina Player Profiles non sarà sviluppata.

## PAS Intelligence in Period Load e Drills (v3.3.6)

PAS Intelligence è ora contestuale anche nelle sezioni **Period Load** e **Drills**.

- riconosce ciclo gara corrente, precedente, ultimi N cicli e cicli nominati;
- configura automaticamente uno o più Match Cycle in Period Load;
- applica giocatori, ruoli, Starters/No Starters e metrica dalla richiesta;
- mostra totali, ranking e confronti tra cicli con grafici coerenti con Period Load;
- nei Drills riconosce esercitazioni, giocatori, ruoli, S/NS e cicli gara;
- mostra ranking dei drill o confronti tra giocatori per occorrenza;
- non aggiunge nuovi filtri visibili: le condizioni vengono interpretate dal testo.

Esempi: `chi ha accumulato più Distance negli ultimi 2 cicli gara?`, `confronta Sarr e Suslov negli ultimi 3 cicli`, `quali drills hanno prodotto più accelerazioni nel ciclo gara attuale?`.

### Rifiniture report e grafici v3.5.3
- I grafici di dettaglio mantengono tutti i giocatori della giornata; il giocatore selezionato è evidenziato con un pallino giallo più grande.
- Nel Period Load Report le sigle S e NS compaiono una sola volta e sono centrate verticalmente sui rispettivi gruppi.
- I nomi dei giocatori sono mostrati integralmente nei Period Load e Session Report tramite adattamento automatico del font.


## v3.7.17 – Correzione visualizzazioni multi Match Cycle

- Corretto il crash nelle visualizzazioni con più Match Cycle quando i risultati statistici contengono più confronti pairwise per ciclo.
- Le annotazioni del grafico Totali gestiscono ora liste di confronti e mostrano tutti i simboli significativi disponibili.
- Il Performance Score per livello usa il confronto con p-value più basso e ne mostra esplicitamente la coppia.
- Nessuna modifica ai dati del database.

## v3.7.15 – Stampa grafici Performance Research
- Aggiunto un pannello visibile nella scheda Visualizzazioni di Performance Research.
- Selezione dei singoli grafici da includere.
- Generazione e download PDF A4 orizzontale con massimo 4 grafici per pagina.
- Conservazione di titoli, legende e annotazioni di significatività.


### GPExe Team Session Details (v3.7.43)

PAS Connect può ora scaricare il dettaglio delle Team Sessions già sincronizzate, includendo header, timing, stato, intestazioni metriche dinamiche e righe atleta. I dati vengono salvati esclusivamente in `.pas_data/pas_connect.sqlite3`; il database Excel e le analisi esistenti non vengono modificati.

## GPExe GraphQL Foundation (v4.2.0)

PAS Connect autentica l'utente mediante la mutation GraphQL `TokenAuth` sull'endpoint `https://e15.gpexe.com/ui/v2/`. Token JWT, refresh token e stato dell'account rimangono esclusivamente nella sessione Streamlit. Non vengono eseguite query dati non verificate: Team e TeamSession mostrano il messaggio “Query GraphQL Team/TeamSession da acquisire e verificare.” e tutte le sincronizzazioni remote restano disabilitate. Excel, calcoli, dashboard, grafici e report non sono modificati.
## PAS v4.11.0 — Relative Distance Provider Integration

Il Data Provider comune supporta **Relative Distance**: GPExe legge esclusivamente il database PAS Connect e risolve il KPI reale tramite il Metric Catalog, con filtri per data, Team, TeamSession e atleta e senza fallback silenzioso a Excel. Il provider è pronto per le viste che già trattano la metrica, mentre il collegamento operativo a Drills e Match è rinviato alle rispettive release dedicate.

Bridge Validation confronta Relative Distance con tolleranza configurabile. Distance Pilot e Bridge Validation sono strumenti tecnici disponibili esclusivamente in **Settings → PAS Connect → Developer Tools**; Excel resta la sorgente predefinita e la scelta Excel/GPExe rimane manuale. La Panoramica del giorno non espone una nuova card Relative Distance e conserva il comportamento precedente.
## PAS v4.12.0 — Day Overview Full Provider Integration

La **Panoramica del giorno** mantiene aspetto, filtri e calcoli esistenti ma diventa provider-aware. Excel resta predefinito e invariato; quando GPExe viene scelto manualmente, Duration, Distance, Acc Events, Dec Events, Max Speed, Speed Events e le metriche a soglia con profilo verificato vengono lette esclusivamente dal database PAS Connect. Valori mancanti non vengono completati con Excel.

Duration usa il `totalTime` della AthleteSession e viene normalizzata internamente in secondi; la card conserva la presentazione storica in minuti. Anaerobic Threshold Zone e High Intensity Training restano metriche Firstbeat e sono indicate come provider esterno. Settings → PAS Connect → Developer Tools include diagnostica di copertura e Bridge Validation multi-metrica con tolleranza e unità canonica.
