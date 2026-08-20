from pathlib import Path


def test_v391_dashboard_and_pas_connect_ui_contract():
    app = Path("app.py").read_text(encoding="utf-8")
    version = Path("modules/version.py").read_text(encoding="utf-8")

    assert 'APP_BUILD_VERSION = "4.18.0"' in version
    assert '"Aggiungi box plot al report"' in app
    assert '"Includi nel report PDF"' not in app
    assert 'with st.expander("Visualizza dettagli giocatori", expanded=False):' in app
    assert 'key="pas_gpexe_export_upload"' in app
    assert 'Settings → PAS Connect' in app


def test_v391_report_selector_has_no_narrow_column_layout():
    app = Path("app.py").read_text(encoding="utf-8")
    start = app.index("def render_compact_report_selector")
    end = app.index("def reference_status", start)
    selector = app[start:end]

    assert "st.columns" not in selector
    assert 'st.checkbox(' in selector
