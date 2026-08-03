# Deploy su Streamlit Community Cloud

Configurazione consigliata:

- Repository: contenuto dello ZIP direttamente nella radice.
- Main file path: `app.py`.
- Python: **3.12**, selezionato in **Advanced settings** al momento del deploy.
- File dipendenze: `requirements.txt` nella radice.

Prima del caricamento eseguire:

```bash
python validate_release.py
```

Il controllo verifica che `requirements.txt` contenga solo requisiti validi, che i file essenziali siano presenti e che tutti i file Python siano compilabili.
