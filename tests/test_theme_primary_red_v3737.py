from pathlib import Path


def test_pas_primary_color_is_red():
    root = Path(__file__).resolve().parents[1]
    config = (root / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    assert 'primaryColor = "#D71920"' in config
    assert '#F4C430' not in config
