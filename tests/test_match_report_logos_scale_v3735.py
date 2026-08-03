from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.reporting import (  # noqa: E402
    _resolve_match_header,
    _team_logo_path,
    build_session_report_pdf,
)


def test_real_match_label_resolves_visible_opponent_logo():
    resolved = _resolve_match_header("03/08/2026 · MD JUVENTUS (H)")
    assert resolved is not None
    assert resolved["opponent"] == "JUVENTUS"
    assert resolved["teams"][1]["logo"] == _team_logo_path("JUVENTUS")
    assert resolved["teams"][1]["logo"].is_file()


def test_label_without_md_prefix_is_supported():
    resolved = _resolve_match_header("03/08/2026 · ROMA (A)")
    assert resolved is not None
    assert resolved["venue"] == "A"
    assert resolved["teams"][0]["name"] == "ROMA"


def test_pdf_with_dark_opponent_logo_and_compact_scale_is_generated():
    data = pd.DataFrame({
        "Athlete": ["PLAYER A"],
        "Relative Distance": [90.0],
    })
    target = pd.DataFrame({
        "Athlete": ["PLAYER A"],
        "Relative Distance": [100.0],
    })
    specs = {
        "Relative Distance (m/min)": {
            "column": "Relative Distance",
            "decimals": 0,
            "format": "number",
            "color": "#54A24B",
        },
        "Acc Events (n°)": {"column": "Acc", "color": "#54A24B"},
        "Distance (m)": {"column": "Distance", "color": "#4C78A8"},
    }
    pdf = build_session_report_pdf(
        session_data=data,
        selected_metrics=["Relative Distance (m/min)"],
        metric_specs=specs,
        report_title="MATCH REPORT",
        session_context={
            "date": "03/08/2026",
            "match_day": "03/08/2026 · MD JUVENTUS (H)",
            "cycle": "Match",
            "drill": "Match",
            "time_of_day": "",
        },
        target_data=target,
        summary_mode="match_total",
        summary_label="TOTAL MATCH",
        summary_average_metrics={"Relative Distance (m/min)"},
        match_header_label="03/08/2026 · MD JUVENTUS (H)",
    )
    out = ROOT / "tests" / "_match_report_logos_scale_v3735.pdf"
    out.write_bytes(pdf)
    assert out.stat().st_size > 5000
