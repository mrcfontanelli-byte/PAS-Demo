# PAS Demo v2.5.11 — Performance Analysis System

Prima versione funzionale costruita sul database Hellas Verona 2025-26.

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
