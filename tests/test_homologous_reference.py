from pathlib import Path


def test_dashboard_uses_compact_homologous_reference() -> None:
    source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
    assert "same_cycle_length = True" in source
    assert "vs media omologa · n=" in source
    assert "reference_count=int(" in source
    assert "Stesso Match Day:" in source
    assert "Stessa Length Cycle:" in source
    assert 'st.sidebar.checkbox(\n    "Storico: stessa Length Cycle"' not in source
