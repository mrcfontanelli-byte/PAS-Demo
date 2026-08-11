from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_sync_manager_is_graphql_contextual_and_read_only_diagnostics_are_wired():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "SyncRequest(" in app
    assert "Tracing C-01→C-05" in app
    assert "Riprova sessione" in app
    assert "Riprova tutti gli errori" in app
    assert "disabled=not bool(selected_team)" in app
    assert "available_contexts" in app


def test_gpexe_provider_does_not_filter_with_hellas_roster():
    provider = (ROOT / "modules" / "data_provider.py").read_text(encoding="utf-8")
    gpexe = provider[provider.index("class GPExeProvider"):provider.index("DEFAULT_PROVIDER_ID")]
    assert "PLAYERS_HELLAS" not in gpexe
    assert "load_pas_performance_frame" in gpexe


def test_full_sync_entry_point_cannot_reactivate_rest_implicitly():
    sync = (ROOT / "pas_connect" / "sync.py").read_text(encoding="utf-8")
    body = sync[sync.index("def run_full_sync("):]
    assert "run_graphql_sync" in body
    assert "sync_reference_data(client)" not in body
    assert "richiede Team, stagione e intervallo espliciti" in body
