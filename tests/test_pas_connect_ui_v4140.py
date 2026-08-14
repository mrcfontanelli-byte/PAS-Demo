from pathlib import Path
import inspect


ROOT = Path(__file__).parents[1]


def _app_source() -> str:
    return (ROOT / "app.py").read_text(encoding="utf-8")


def test_release_version_and_pas_connect_panels_are_declared_in_target_order():
    app = _app_source()
    version = (ROOT / "modules" / "version.py").read_text(encoding="utf-8")
    assert 'APP_BUILD_VERSION = "4.17.3"' in version

    markers = (
        'pas_connect_main = st.container()',
        'st.expander("Opzioni GPExe", expanded=False)',
        'pas_connect_advanced = st.expander("Avanzate / Diagnostica", expanded=False)',
        'st.expander("Legacy — sola lettura", expanded=False)',
    )
    positions = [app.index(marker) for marker in markers]
    assert positions == sorted(positions)


def test_disconnected_state_does_not_create_empty_optional_expanders():
    app = _app_source()
    assert "show_gpexe_options = is_gpexe_connected or (" in app
    assert "if show_gpexe_options\n            else None" in app
    assert "show_legacy = is_gpexe_connected or any(legacy_counts.values())" in app
    assert "if show_legacy\n            else None" in app
    assert "if pas_connect_legacy is not None and not is_gpexe_connected:" in app
    assert "Dati legacy presenti nel database PAS Connect locale." in app


def test_login_uses_the_central_release_version_without_a_hardcoded_ui_version():
    app = _app_source()
    assert "from modules.version import APP_BUILD_VERSION, APP_EDITION" in app
    assert "{APP_EDITION} v{APP_BUILD_VERSION} · Accesso riservato" in app
    assert "Demo v4.13.0 · Accesso riservato" not in app


def test_daily_controls_and_last_sync_summary_remain_in_main_view():
    app = _app_source()
    for label in (
        '"Sorgente dati"',
        '"##### Connessione GPExe"',
        '"Connetti a GPExe"',
        '"Disconnetti GPExe"',
        '"Team"',
        '"Data iniziale"',
        '"Data finale"',
        '"🚀 Sincronizzazione completa GPExe"',
        '"##### Ultimo sync"',
    ):
        assert label in app
    for metric in ("Status", "Readiness", "TeamSession", "AthleteSession", "Track", "KPI"):
        assert f'"{metric}"' in app


def test_export_uploader_is_only_rendered_for_file_export_mode():
    app = _app_source()
    condition = 'if st.session_state.get("pas_gpexe_input_mode") == "File export":'
    start = app.index(condition)
    uploader = app.index('st.file_uploader(', start)
    next_section = app.index("with pas_connect_advanced:", uploader)
    assert start < uploader < next_section
    assert app.count('key="pas_gpexe_export_upload"') == 1


def test_advanced_tools_are_embedded_and_manual_or_redundant_actions_are_absent():
    app = _app_source()
    advanced = app[app.index("with pas_connect_advanced:"):]
    assert "render_metric_catalog_section" in advanced
    assert "render_metric_usage_section" in advanced
    assert "render_developer_tools(" in advanced
    assert "embedded=True" in advanced
    assert "Tracing C-01→C-05" in advanced
    assert "Configurazione Streamlit Secrets" in advanced
    assert '"Importa nel database PAS"' not in app
    assert '"Importa Athlete Sessions e KPI nel database PAS"' not in app
    assert 'st.markdown("##### GPExe GraphQL")' not in app

    catalog = (ROOT / "pas_connect" / "catalog_ui.py").read_text(encoding="utf-8")
    usage = (ROOT / "pas_connect" / "usage_ui.py").read_text(encoding="utf-8")
    assert "if embedded" in catalog and "st.container(border=True)" in catalog
    assert "if embedded" in usage and "st.container(border=True)" in usage


def test_all_embedded_renderers_expose_a_compatible_opt_in_signature():
    from modules.developer_tools import render_developer_tools
    from pas_connect.catalog_ui import render_metric_catalog_section
    from pas_connect.usage_ui import render_metric_usage_section

    for renderer in (
        render_metric_catalog_section,
        render_metric_usage_section,
        render_developer_tools,
    ):
        embedded = inspect.signature(renderer).parameters["embedded"]
        assert embedded.default is False
        assert embedded.kind is inspect.Parameter.KEYWORD_ONLY


def test_legacy_actions_are_grouped_and_read_only():
    app = _app_source()
    summary = app.index("with pas_connect_legacy:")
    start = app.index("with pas_connect_legacy:", summary + 1)
    end = app.index("with pas_connect_main:", start)
    legacy = app[start:end]
    for label in (
        "Sincronizza anagrafiche GPExe",
        "Sincronizza Team Sessions GPExe",
        "Sincronizza dettagli Team Sessions GPExe",
        "Sincronizza Athlete Sessions GPExe",
    ):
        assert label in legacy
    assert legacy.count("disabled=True") == 4


def test_existing_streamlit_state_keys_are_not_duplicated():
    app = _app_source()
    keys = (
        "pas_data_source",
        "pas_gpexe_input_mode",
        "pas_gpexe_export_upload",
        "pas_gpexe_connect",
        "pas_gpexe_disconnect",
        "pas_gpexe_get_sessions",
        "pas_gpexe_full_sync",
        "pas_gpexe_retry_one",
        "pas_gpexe_retry_errors",
    )
    for key in keys:
        assert app.count(f'key="{key}"') == 1


def test_local_sessions_default_to_explicit_selection_and_dashboard_uses_local_team():
    app = _app_source()
    assert 'if "pas_gpexe_active_session_ids" not in st.session_state:' in app
    assert 'session_key = "pas_gpexe_active_session_ids"' in app
    assert 'default=defaults' not in app
    assert 'f"{len(selected_ids)} selezionate."' in app
    assert 'f"{len(selected_ids) or len(api_sessions)} selezionate."' not in app
    assert 'Seleziona almeno una TeamSession locale per usare i dati GPExe.' in app
    assert 'gpexe_api_ready = bool(selected_api_sessions)' in app
    assert 'st.session_state["pas_gpexe_local_team_id"] = selected_local_team' in app
    assert 'st.session_state["pas_gpexe_local_season"] = selected_local_season' in app
    assert 'st.session_state.get("pas_gpexe_local_team_id")' in app
    assert 'if dashboard_session_ids else None' in app


def test_dashboard_player_widget_state_is_normalized_to_current_options():
    app = _app_source()
    assert 'selected_players_key = "dashboard_selected_players"' in app
    assert 'if player in available_players' in app
    assert 'overview_player_key = "dashboard_overview_player"' in app
    assert 'if st.session_state.get(overview_player_key) not in all_players:' in app
    assert 'st.session_state[overview_player_key] = all_players[0]' in app


def test_ui_release_does_not_change_client_or_legacy_service_engines():
    status = __import__("subprocess").run(
        ["git", "diff", "--name-only", "--", "pas_connect/client.py", "pas_connect/services.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout.strip() == ""


def test_full_sync_transports_are_explicit_and_separate():
    from pas_connect.sync import run_graphql_sync, run_rest_sync

    assert callable(run_graphql_sync)
    assert callable(run_rest_sync)


def test_graphql_database_entrypoint_remains_backward_compatible():
    from pas_connect.database import PASConnectDatabase

    assert callable(PASConnectDatabase.upsert_graphql_team_session_bundle)
