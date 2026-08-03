from pathlib import Path


def _reporting_source() -> str:
    return (Path(__file__).parents[1] / "modules" / "reporting.py").read_text(encoding="utf-8")


def test_report_values_do_not_shrink_to_short_bars():
    source = _reporting_source()
    assert "available_text_w = max(5.0, bw - 2.0)" not in source
    assert "value_font_size -= 0.25" not in source
    assert "value_font_size = 10.2 if team else value_font" in source


def test_max_speed_percentage_uses_bar_center():
    source = _reporting_source()
    percentage_section = source.split("if has_percentage:", 1)[1].split("pdf.setStrokeColor", 1)[0]
    assert "pdf.drawCentredString(\n                value_center_x," in percentage_section


def test_dashboard_loads_through_data_provider():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "data_provider = get_data_provider()" in app
    assert "raw = data_provider.load_performance_data(" in app
    assert "match_source = data_provider.load_match_analysis_data(" in app
