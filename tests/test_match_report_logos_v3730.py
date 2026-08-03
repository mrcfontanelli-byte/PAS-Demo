from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules.reporting import (  # noqa: E402
    _resolve_match_header,
    build_session_report_pdf,
)


def _assert_order(label: str, expected: list[str]) -> None:
    resolved = _resolve_match_header(label)
    assert resolved is not None
    assert [team["name"] for team in resolved["teams"]] == expected
    assert all(team["logo"] and Path(team["logo"]).is_file() for team in resolved["teams"])


def main() -> None:
    _assert_order(
        "12/09/2026 · MD JUVENTUS (H)",
        ["HELLAS VERONA", "JUVENTUS"],
    )
    _assert_order(
        "19/09/2026 · MD INTER (A)",
        ["INTER", "HELLAS VERONA"],
    )

    data = pd.DataFrame({"Athlete": ["PLAYER A"], "Max Speed": [31.2]})
    specs = {
        "Max Speed (km/h)": {
            "column": "Max Speed",
            "decimals": 1,
            "format": "number",
            "color": "#00B8A9",
        }
    }
    for venue, opponent in (("H", "JUVENTUS"), ("A", "INTER")):
        label = f"12/09/2026 · MD {opponent} ({venue})"
        pdf = build_session_report_pdf(
            session_data=data,
            selected_metrics=["Max Speed (km/h)"],
            metric_specs=specs,
            report_title="MATCH REPORT",
            session_context={
                "date": "12/09/2026",
                "match_day": label,
                "cycle": "Match",
                "drill": "Match",
                "time_of_day": "",
            },
            summary_mode="match_total",
            summary_label="TOTAL MATCH",
            match_header_label=label,
        )
        out = ROOT / "tests" / f"_match_header_{venue}.pdf"
        out.write_bytes(pdf)
        assert out.stat().st_size > 5000

    print("MATCH REPORT LOGOS TEST OK")


if __name__ == "__main__":
    main()
