# PAS Connect Specification — Foundation 1.0

## Scopo

PAS Connect separa le sorgenti dati dal PAS Core. La release 3.7.36 non attiva
alcuna chiamata remota e mantiene Excel come unica sorgente operativa.

## Principi

1. **Provider indipendenti**: Excel e GPExe devono produrre uno schema interno equivalente.
2. **Nessuna credenziale nel repository**: token, username e password saranno letti da `st.secrets` o variabili d'ambiente.
3. **Sincronizzazione prima, analisi dopo**: il PAS non interrogherà GPExe durante il rendering dei grafici.
4. **ID provider stabili**: atleti, team, sessioni e track sono riconosciuti tramite ID, non tramite nomi.
5. **Import incrementale**: quando disponibile si usa `updated_on`.
6. **Compatibilità Excel**: l'adapter attuale rimane invariato finché la parità dati non è dimostrata.

## Endpoint GPExe censiti

- `POST /rest/v2/auth/token/`
- `GET /rest/v2/team/` e `/team/{ID}/`
- `GET /rest/v2/athlete/` e `/athlete/{ID}/`
- `GET /rest/v2/session/category/`
- `GET /rest/v2/session/tags/`
- `GET /rest/v2/session/team/`
- `GET /rest/v2/session/team/{ID}/`
- `GET /rest/v2/session/team/{ID}/athlete_sessions/`
- `GET /rest/v2/session/athlete/{ID}/`
- `GET /rest/v2/track/` e `/track/{ID}/`

## Stato della release

Disponibili: configurazione, catalogo endpoint, autenticazione, client REST
isolato, mapper iniziali e piano di sincronizzazione. Non disponibili: UI,
persistenza SQL, sincronizzazione reale e uso dei dati GPExe nell'app.

## Persistenza reference data v3.7.41

Le anagrafiche normalizzate sono scritte nel database SQLite PAS Connect tramite
transazione e upsert. Token e password non vengono mai persistiti. L'Excel
operativo non viene aperto né modificato dalla sincronizzazione GPExe.
