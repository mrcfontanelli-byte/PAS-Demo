import pandas as pd

from modules.bridge_validation import compare_distance_sources


def _frame(rows, source):
    return pd.DataFrame([
        {
            "Date": date,
            "Athlete": athlete,
            "Distance (m)": distance,
            "TeamSession ID": session_id,
            "AthleteSession ID": athlete_session_id,
            "Source": source,
        }
        for date, session_id, athlete_session_id, athlete, distance in rows
    ])


def test_validation_compares_only_common_dates_and_athletes():
    excel = _frame([
        ("2026-08-01", None, None, "MARIO ROSSI", 5000.0),
        ("2026-08-01", None, None, "LUCA BIANCHI", 4000.0),
        ("2026-08-02", None, None, "SOLO EXCEL", 1000.0),
    ], "Excel")
    gpexe = _frame([
        ("2026-08-01 10:00", 10, 20, "mario rossi", 5000.05),
        ("2026-08-01 10:00", 10, 21, "LUCA BIANCHI", 4100.0),
        ("2026-08-03", 11, 22, "SOLO GPEXE", 2000.0),
    ], "GPExe")

    result = compare_distance_sources(excel, gpexe, tolerance_m=0.1)

    assert result.summary == {
        "sedute_confrontate": 1,
        "atleti_confrontati": 2,
        "atleti_coincidenti": 1,
        "atleti_differenti": 1,
    }
    assert result.comparisons.set_index("Atleta").loc["MARIO ROSSI", "Stato"] == "OK"
    assert result.comparisons.set_index("Atleta").loc["LUCA BIANCHI", "Stato"] == "DIFFERENTE"
    assert set(result.non_comparable_sessions["Presente solo in"]) == {"Excel", "GPExe"}


def test_validation_uses_team_session_when_both_sources_provide_it():
    excel = _frame([
        ("2026-08-01", 10, None, "MARIO ROSSI", 5000),
        ("2026-08-01", 12, None, "MARIO ROSSI", 1000),
    ], "Excel")
    gpexe = _frame([
        ("2026-08-01", 10, 20, "MARIO ROSSI", 5000),
        ("2026-08-01", 11, 21, "MARIO ROSSI", 9999),
    ], "GPExe")

    result = compare_distance_sources(excel, gpexe)

    assert result.summary["sedute_confrontate"] == 1
    assert result.comparisons.iloc[0]["TeamSession ID"] == "10"
    assert result.comparisons.iloc[0]["Stato"] == "OK"
    assert set(result.non_comparable_sessions["TeamSession ID"]) == {"11", "12"}


def test_validation_aggregates_rows_per_athlete_without_total_only_comparison():
    excel = _frame([
        ("2026-08-01", None, None, "MARIO ROSSI", 2000),
        ("2026-08-01", None, None, "MARIO ROSSI", 3000),
        ("2026-08-01", None, None, "LUCA BIANCHI", 4000),
    ], "Excel")
    gpexe = _frame([
        ("2026-08-01", None, 20, "MARIO ROSSI", 5000),
        ("2026-08-01", None, 21, "LUCA BIANCHI", 4001),
    ], "GPExe")

    result = compare_distance_sources(excel, gpexe, tolerance_m=0)

    rows = result.comparisons.set_index("Atleta")
    assert rows.loc["MARIO ROSSI", "Distance Excel"] == 5000
    assert rows.loc["MARIO ROSSI", "Stato"] == "OK"
    assert rows.loc["LUCA BIANCHI", "Stato"] == "DIFFERENTE"


def test_validation_empty_sources_are_non_blocking():
    columns = ["Date", "Athlete", "Distance (m)"]
    empty = pd.DataFrame(columns=columns)
    result = compare_distance_sources(empty, empty)
    assert result.comparisons.empty
    assert result.non_comparable_sessions.empty
    assert all(value == 0 for value in result.summary.values())


def test_bridge_validation_ui_is_isolated_from_existing_dashboards():
    app = open("app.py", encoding="utf-8").read()
    assert '"🧪 Bridge Validation"' in app
    block = app[app.index('if page == "🧪 Bridge Validation"'):]
    assert "compare_distance_sources" in block
    assert "Sedute non confrontabili" in block
    assert "DIFFERENTE" in block
