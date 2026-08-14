from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.reporting import build_session_report_pdf  # noqa: E402


def test_match_report_target_labels_and_bar_centering():
    reporting = (ROOT / "modules" / "reporting.py").read_text(encoding="utf-8")
    version = (ROOT / "modules" / "version.py").read_text(encoding="utf-8")

    assert 'APP_BUILD_VERSION = "4.17.4"' in version
    assert "target_label_y = bar_y + 0.45" in reporting
    assert "target_label_right" in reporting
    assert "value_center_x = cell_l + max(0.0, bw) / 2" in reporting

    data = pd.DataFrame(
        {
            "Athlete": ["PLAYER A", "PLAYER B"],
            "Distance": [8200.0, 5200.0],
            "Max Speed": [32.1, 28.4],
        }
    )
    targets = pd.DataFrame(
        {
            "Athlete": ["PLAYER A", "PLAYER B"],
            "Distance": [7600.0, 6100.0],
            "Max Speed": [31.4, 30.0],
        }
    )
    specs = {
        "Distance (m)": {
            "column": "Distance",
            "decimals": 0,
            "format": "number",
            "color": "#1F77B4",
        },
        "Max Speed (km/h)": {
            "column": "Max Speed",
            "decimals": 1,
            "format": "number",
            "color": "#00B8A9",
        },
        "Acc Events (n°)": {
            "column": "Acc Events",
            "decimals": 0,
            "format": "number",
            "color": "#54A24B",
        },
    }
    pdf = build_session_report_pdf(
        session_data=data,
        selected_metrics=["Distance (m)", "Max Speed (km/h)"],
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
        target_label="Individual Performance Model",
        summary_mode="match_total",
        summary_label="TOTAL MATCH",
        match_header_label="MD JUVENTUS (H)",
    )
    out = ROOT / "tests" / "_match_target_labels_v3732.pdf"
    out.write_bytes(pdf)
    assert out.stat().st_size > 5000
