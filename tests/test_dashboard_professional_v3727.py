from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "app.py").read_text(encoding="utf-8")
CHARTS = (ROOT / "modules" / "charts.py").read_text(encoding="utf-8")


def test_dashboard_professional_classes_present():
    assert "pas-dashboard-hero" in APP
    assert "pas-dashboard-card-marker" in APP
    assert "pas-card-stat-label" in APP
    assert "pas-card-stat-value" in APP


def test_dashboard_chart_style_is_opt_in():
    assert "dashboard_style: bool = False" in CHARTS
    assert "dashboard_style=True" in APP
    assert "show_cycle_legend=True" in APP
