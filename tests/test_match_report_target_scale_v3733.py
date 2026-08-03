from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.reporting import (  # noqa: E402
    _format_session_value,
    _report_metric_scale_max,
    build_session_report_pdf,
)


def test_scale_includes_target_and_preserves_gap():
    scale = _report_metric_scale_max(
        pd.Series([60.0]),
        target_values=pd.Series([100.0]),
        headroom=1.10,
    )
    assert round(scale, 6) == 110.0
    assert 60.0 / scale < 100.0 / scale
    assert round(60.0 / scale, 3) == 0.545
    assert round(100.0 / scale, 3) == 0.909


def test_mpe_zero_decimals_in_match_report():
    reporting = (ROOT / "modules" / "reporting.py").read_text(encoding="utf-8")
    version = (ROOT / "modules" / "version.py").read_text(encoding="utf-8")
    assert 'APP_BUILD_VERSION = "3.7.44"' in version
    assert '"MPE Rec Avg Time (s)",' in reporting
    assert "target_vals" in reporting
    assert "useful_span * 0.05" in reporting
    assert _format_session_value(18.7, 0, "number") == "19"

    data = pd.DataFrame({"Athlete": ["PLAYER A"], "MPE": [18.7]})
    targets = pd.DataFrame({"Athlete": ["PLAYER A"], "MPE": [31.6]})
    specs = {
        "MPE Rec Avg Time (s)": {
            "column": "MPE",
            "decimals": 1,
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
        selected_metrics=["MPE Rec Avg Time (s)"],
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
    out = ROOT / "tests" / "_match_target_scale_v3733.pdf"
    out.write_bytes(pdf)
    assert out.stat().st_size > 4000
