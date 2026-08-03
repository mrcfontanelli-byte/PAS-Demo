from pathlib import Path


def test_pas_connect_exposes_excel_and_gpexe_sources():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'st.markdown("#### PAS Connect")' in app
    assert '"Sorgente dati"' in app
    assert 'options=("Excel", "GPExe")' in app
    assert 'index=0' in app
    assert 'key="pas_data_source"' in app


def test_gpexe_selection_remains_non_operational():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert 'if selected_data_source == "GPExe":' in app
    assert 'Il PAS continua a utilizzare Excel.' in app
    assert 'data_provider = get_data_provider()' in app
    assert 'get_data_provider(st.session_state' not in app
