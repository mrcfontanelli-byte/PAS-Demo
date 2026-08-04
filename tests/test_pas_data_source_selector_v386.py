from pathlib import Path


def test_pas_connect_uses_central_provider_catalog():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.markdown("#### PAS Connect")' in app
    assert '"Sorgente dati"' in app
    assert 'provider_catalog = get_available_data_providers()' in app
    assert 'options=provider_ids' in app
    assert 'format_func=provider_labels.get' in app
    assert 'key="pas_data_source"' in app


def test_gpexe_selection_uses_controlled_excel_fallback():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'provider_selection = resolve_data_provider(requested_provider_id)' in app
    assert 'data_provider = provider_selection.provider' in app
    assert 'if current_selection.fallback_applied:' in app
    assert 'st.warning(current_selection.requested.status_message)' in app


def test_partial_gpexe_data_falls_back_to_excel_without_blocking_the_ui():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "has_compatible_performance_rows(" in app
    assert 'st.session_state["pas_data_source"] = "excel"' in app
    assert "I dati GPExe sono stati importati nel database PAS Connect" in app
    assert "Il PAS continua " in app
    assert "temporaneamente a utilizzare Excel." in app
    fallback = app.index("if prefer_gpexe_api and gpexe_api_has_sessions:")
    excel_load = app.index("raw = excel_provider.load_performance_data", fallback)
    blocking_error = app.index('st.error("Errore nel caricamento del database.")')
    assert fallback < excel_load < blocking_error


def test_gpexe_import_does_not_change_analytic_source_or_navigation():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    start = app.index('if st.button("Importa Athlete Sessions e KPI nel database PAS"')
    block = app[start:app.index("st.divider()", start)]
    assert 'pas_data_source' not in block
    assert 'pas_navigation' not in block
    assert 'st.rerun()' not in block


def test_unexpected_synchronized_api_failure_is_confined_to_excel_fallback():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    start = app.index("if using_gpexe and prefer_gpexe_api and gpexe_api_ready:")
    end = app.index("elif using_gpexe and uploaded_database is not None:", start)
    block = app[start:end]
    assert "try:" in block
    assert "except Exception:" in block
    assert 'st.session_state["pas_data_source"] = "excel"' in block
    assert "excel_provider.load_performance_data" in block
    assert "st.error" not in block
