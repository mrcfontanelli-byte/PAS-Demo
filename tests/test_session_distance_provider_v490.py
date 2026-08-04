import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

from modules.data_provider import DEFAULT_PROVIDER_ID, ExcelProvider, GPExeProvider
from modules.session_distance import (
    MISSING_DAY_MESSAGE,
    MISSING_DISTANCE_MESSAGE,
    UNSUPPORTED_DRILL_MESSAGE,
    SessionDistanceError,
    compare_session_distance,
)
from pas_connect.database import PASConnectDatabase


def _database(path, *, include_catalog=True):
    database = PASConnectDatabase(path)
    database.initialize()
    with database.connect() as connection:
        if include_catalog:
            connection.execute(
                """INSERT INTO pas_metric_catalog(
                canonical_metric, display_name, provider, acquisition_mode,
                provider_metric_name, category, metric_type, canonical_unit,
                provider_unit, value_type, requires_profile, active,
                is_contextual, created_at, updated_at
                ) VALUES('Distance', 'Distance', 'GPExe', 'api', 'total_distance',
                         'GPS', 'direct', 'm', 'm', 'decimal', 0, 1, 0, 'now', 'now')"""
            )
        for session_id, date, team_id in (
            (10, "2026-08-01T10:00:00", 469),
            (11, "2026-08-01T16:00:00", 469),
            (12, "2026-08-02T10:00:00", 999),
        ):
            connection.execute(
                """INSERT INTO gpexe_team_sessions(
                provider_session_id, team_id, session_name, start_timestamp,
                is_stats_valid, drill_enabled, synced_at, raw_json
                ) VALUES(?,?,?,?,1,1,'now','{}')""",
                (session_id, team_id, "Training", date),
            )
        for athlete_session, session_id, athlete_id, name, value, uom in (
            (20, 10, 7, " Mario   Rossi ", "5", "km"),
            (21, 11, 7, "MARIO ROSSI", "1000", "m"),
            (22, 10, 8, "LUCA BIANCHI", "4200", "m"),
        ):
            connection.execute(
                """INSERT OR IGNORE INTO gpexe_athletes(
                provider_player_id, player_name, synced_at, raw_json
                ) VALUES(?,?, 'now','{}')""",
                (athlete_id, name),
            )
            connection.execute(
                """INSERT INTO gpexe_athlete_session_details(
                provider_athlete_session_id, provider_session_id,
                provider_player_id, metrics_json, zones_json, synced_at, raw_json
                ) VALUES(?,?,?,'{}','{}','now','{}')""",
                (athlete_session, session_id, athlete_id),
            )
            connection.execute(
                """INSERT INTO gpexe_athlete_session_kpis(
                provider_athlete_session_id, source, position, name, value,
                kpi_group, uom, unit, raw_json
                ) VALUES(?, 'identifierKpi', 0, 'total_distance', ?, 'GPS', ?, 'distance', '{}')""",
                (athlete_session, value, uom),
            )
        connection.commit()
    return database.path


def test_excel_is_default_and_daily_contract_does_not_mutate_source():
    assert DEFAULT_PROVIDER_ID == "excel"
    source = pd.DataFrame({
        "Date": ["2026-08-01", "2026-08-02"],
        "Athlete": ["A", "B"],
        "distance (m)": [1000, 2000],
    })
    result = ExcelProvider().load_session_distance_data(source, "2026-08-01")
    assert result["Distance (m)"].tolist() == [1000]
    assert len(source) == 2


def test_gpexe_daily_distance_filters_date_team_and_sessions(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    result = GPExeProvider().load_session_distance_data(
        path, "2026-08-01", team_id="469", session_ids=[10, 11]
    )
    assert dict(zip(result["Athlete ID"], result["Distance (m)"])) == {7: 6000.0, 8: 4200.0}
    assert set(result["TeamSession ID"]) == {"10,11", "10"}


def test_full_training_is_the_verified_total_session_alias(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    result = GPExeProvider().load_session_distance_data(
        path, "2026-08-01", drill="Full Training", team_id=469
    )
    assert len(result) == 2
    assert result["Distance (m)"].notna().all()


def test_gpexe_athlete_id_filter_has_priority_over_name(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    result = GPExeProvider().load_session_distance_data(
        path, "2026-08-01", athlete_ids=[7], athletes=["LUCA BIANCHI"]
    )
    assert result["Athlete ID"].tolist() == [7]
    assert result.iloc[0]["Athlete"] == "MARIO ROSSI"


def test_missing_day_distance_catalog_and_drill_messages(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    provider = GPExeProvider()
    with pytest.raises(SessionDistanceError, match=MISSING_DAY_MESSAGE):
        provider.load_session_distance_data(path, "2026-07-01")
    with pytest.raises(SessionDistanceError, match=UNSUPPORTED_DRILL_MESSAGE):
        provider.load_session_distance_data(path, "2026-08-01", drill="Small Sided Game")
    no_catalog = _database(tmp_path / "no_catalog.sqlite3", include_catalog=False)
    with pytest.raises(SessionDistanceError, match=MISSING_DISTANCE_MESSAGE):
        provider.load_session_distance_data(no_catalog, "2026-08-01")


def test_daily_comparison_uses_ids_then_reports_differences_and_unmatched():
    excel = pd.DataFrame({
        "Date": ["2026-08-01", "2026-08-01", "2026-08-01"],
        "Athlete": ["Excel name", "ONLY EXCEL", "Same Name"],
        "Athlete ID": [7, 8, 9],
        "Distance (m)": [6000.0, 4000.0, 1000.0],
    })
    gpexe = pd.DataFrame({
        "Date": ["2026-08-01", "2026-08-01", "2026-08-01"],
        "Athlete": ["Different name", "ONLY GPEXE", "Same Name"],
        "Athlete ID": [7, 10, 9],
        "Distance (m)": [6000.05, 3000.0, 1001.0],
    })
    comparison = compare_session_distance(excel, gpexe, tolerance_m=0.1)
    assert comparison.comparisons["Stato"].tolist() == ["OK", "DIFFERENTE"]
    assert comparison.excel_only["Athlete ID"].tolist() == [8]
    assert comparison.gpexe_only["Athlete ID"].tolist() == [10]


def test_name_normalization_is_fallback_when_ids_are_unavailable():
    excel = pd.DataFrame({"Date": ["2026-08-01"], "Athlete": [" Mario  Rossi "], "Distance (m)": [1]})
    gpexe = pd.DataFrame({"Date": ["2026-08-01"], "Athlete": ["mario rossi"], "Distance (m)": [1]})
    result = compare_session_distance(excel, gpexe)
    assert result.comparisons["Stato"].tolist() == ["OK"]


def test_dashboard_scope_is_daily_distance_and_never_silently_falls_back():
    app = open("app.py", encoding="utf-8").read()
    assert "dashboard_uses_gpexe_distance = requested_provider_id == \"gpexe\"" in app
    assert "load_session_distance_data" in app
    assert "Verifica tecnica Distance Excel / GPExe" in app
    assert "dashboard_distance_error = str(exc)" in app
    assert 'dashboard_distance_current = day_selected_player_day' not in app
    assert 'st.session_state["pas_data_source"] = "gpexe"' not in app
    assert "elif accumulation_text:" in app
    assert 'dashboard_distance_current = day_selected_player_day' not in app


def test_clean_process_imports_bridge_session_distance_and_app_in_startup_order():
    script = (
        "import pas_connect.pas_bridge; "
        "import modules.session_distance; "
        "import app; "
        "print('IMPORT_SEQUENCE_OK')"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_SEQUENCE_OK" in result.stdout


def test_runtime_dashboard_gpexe_distance_card_and_player_detail_are_populated():
    script = r'''
from datetime import date
from streamlit.testing.v1 import AppTest
at = AppTest.from_file("app.py")
at.session_state["pas_demo_authenticated"] = True
at.session_state["pas_navigation"] = "🏠 Dashboard"
at.session_state["pas_data_source"] = "gpexe"
at.session_state["dashboard_reference_date"] = date(2025, 7, 30)
at.session_state["dashboard_selected_drill"] = "Full Training"
at.session_state["pas_gpexe_active_session_ids"] = []
at.run(timeout=60)
assert not at.exception, [str(item.value) for item in at.exception]
cards = [
    str(item.value) for item in at.markdown
    if "Distance (m)" in str(item.value) and "pas-card-value" in str(item.value)
]
assert len(cards) == 1
assert "pas-card-value\">N/D" not in cards[0]
assert "pas-card-accumulation-value" not in cards[0]
assert not any("Nessun giocatore disponibile" in str(item.value) for item in at.info)
assert any("24 atleti" in str(item.value) for item in at.success)
print("GP_EXE_DASHBOARD_RUNTIME_OK")
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "GP_EXE_DASHBOARD_RUNTIME_OK" in result.stdout
