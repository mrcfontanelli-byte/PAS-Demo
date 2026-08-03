from pathlib import Path


def test_settings_exposes_runtime_connection_state_and_disconnect():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Connetti a GPExe" in app
    assert "Disconnetti GPExe" in app
    assert "Stato connessione: non connesso" in app
    assert 'st.session_state["pas_gpexe_connected"] = True' in app
    assert 'st.session_state["pas_gpexe_runtime_token"] = runtime_token' in app
    assert "Excel resta la sorgente dati attiva" in app


def test_runtime_connection_does_not_persist_credentials_to_files():
    app = Path("app.py").read_text(encoding="utf-8")
    forbidden = ("write_text(gpexe", "open(\"secrets.toml\"", "password_file")
    assert not any(token in app for token in forbidden)
