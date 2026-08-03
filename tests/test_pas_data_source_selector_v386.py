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
