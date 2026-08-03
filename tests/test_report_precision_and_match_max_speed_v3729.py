from pathlib import Path


def test_report_relative_distance_precision_and_match_max_speed_percentage():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    reporting = (root / "modules" / "reporting.py").read_text(encoding="utf-8")
    version = (root / "modules" / "version.py").read_text(encoding="utf-8")

    assert 'APP_BUILD_VERSION = "3.8.1"' in version
    assert '"Relative Distance (m/min)",' in reporting
    assert 'report_decimals = (' in reporting
    assert 'match_max_speed_percentages = (' in app
    assert 'percentage_data=(\n                        match_max_speed_percentages' in app
    assert 'percentage_label=""' in app
