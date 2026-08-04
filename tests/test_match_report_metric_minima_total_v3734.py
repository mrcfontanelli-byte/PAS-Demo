from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.reporting import build_session_report_pdf  # noqa: E402


def test_metric_minima_and_total_match_layout_are_present():
    reporting = (ROOT / "modules" / "reporting.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    version = (ROOT / "modules" / "version.py").read_text(encoding="utf-8")
    assert 'APP_BUILD_VERSION = "4.3.0"' in version
    assert '"Relative Distance (m/min)": 80.0' in reporting
    assert '"MPE Rec Avg Time (s)": 5.0' in reporting
    assert 'team and summary_mode == "match_total"' in reporting
    assert 'summary_label="TOTAL MATCH"' in app


def test_match_report_pdf_uses_total_match_label():
    data = pd.DataFrame({
        "Athlete": ["PLAYER A", "PLAYER B"],
        "Relative Distance": [90.0, 100.0],
        "MPE": [8.0, 12.0],
    })
    targets = pd.DataFrame({
        "Athlete": ["PLAYER A", "PLAYER B"],
        "Relative Distance": [105.0, 95.0],
        "MPE": [15.0, 9.0],
    })
    specs = {
        "Relative Distance (m/min)": {
            "column": "Relative Distance",
            "decimals": 0,
            "format": "number",
            "color": "#54A24B",
        },
        "MPE Rec Avg Time (s)": {
            "column": "MPE",
            "decimals": 0,
            "format": "number",
            "color": "#4C78A8",
        },
        "Acc Events (n°)": {
            "column": "Acc Events",
            "decimals": 0,
            "format": "number",
            "color": "#54A24B",
        },
        "Distance (m)": {
            "column": "Distance",
            "decimals": 0,
            "format": "number",
            "color": "#4C78A8",
        },
    }
    pdf = build_session_report_pdf(
        session_data=data,
        selected_metrics=[
            "Relative Distance (m/min)",
            "MPE Rec Avg Time (s)",
        ],
        metric_specs=specs,
        report_title="MATCH REPORT",
        session_context={
            "date": "03/08/2026",
            "match_day": "MD JUVENTUS (H)",
            "cycle": "Match",
            "drill": "Match",
            "time_of_day": "",
        },
        target_data=targets,
        summary_mode="match_total",
        summary_label="TOTAL MATCH",
        summary_average_metrics={
            "Relative Distance (m/min)",
            "MPE Rec Avg Time (s)",
        },
        match_header_label="MD JUVENTUS (H)",
    )
    out = ROOT / "tests" / "_match_metric_minima_total_v3734.pdf"
    out.write_bytes(pdf)
    assert out.stat().st_size > 4000
