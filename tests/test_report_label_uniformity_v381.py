from pathlib import Path


def _reporting_source() -> str:
    return (Path(__file__).parents[1] / "modules" / "reporting.py").read_text(encoding="utf-8")


def test_report_values_do_not_shrink_to_short_bars():
    source = _reporting_source()
    assert "available_text_w = max(5.0, bw - 2.0)" not in source
    assert "value_font_size -= 0.25" not in source
    assert "value_font_size = 10.2 if team else value_font" in source


def test_report_labels_center_until_they_would_exit_left():
    source = _reporting_source()
    assert "value_would_exit_left" in source
    assert "percentage_would_exit_left" in source
    assert "value_center_x + value_text_width / 2 > value_right_bound" not in source
    assert "value_center_x + percentage_text_width / 2 > value_right_bound" not in source
    assert "pdf.drawString(value_left_bound, value_y, formatted)" in source
    assert "pdf.drawCentredString(value_center_x, value_y, formatted)" in source
    assert "pdf.drawCentredString(\n                    value_center_x," in source


def test_dashboard_loads_through_data_provider():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "data_provider = get_data_provider()" in app
    assert "raw = data_provider.load_performance_data(" in app
    assert "match_source = data_provider.load_match_analysis_data(" in app
