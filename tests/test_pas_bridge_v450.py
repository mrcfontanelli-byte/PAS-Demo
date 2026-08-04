import sqlite3

import pandas as pd
import pytest

from modules.data_provider import DEFAULT_PROVIDER_ID, ExcelProvider, GPExeProvider, get_data_provider
from pas_connect.database import PASConnectDatabase


def _build_pilot_database(path):
    database = PASConnectDatabase(path)
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_team_sessions(
            provider_session_id, session_name, start_timestamp, is_stats_valid,
            drill_enabled, synced_at, raw_json
            ) VALUES(10, 'Training', '2026-08-01T10:00:00', 1, 1, 'now', '{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athletes(
            provider_player_id, player_name, synced_at, raw_json
            ) VALUES(7, 'MARIO ROSSI', 'now', '{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_details(
            provider_athlete_session_id, provider_session_id, provider_player_id,
            metrics_json, zones_json, synced_at, raw_json
            ) VALUES(20, 10, 7, '{}', '{}', 'now', '{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id, source, position, name, value,
            kpi_group, uom, unit, raw_json
            ) VALUES(20, 'identifierKpi', 0, 'total_distance', '5000',
                     'GPS', 'm', 'distance', '{}')"""
        )
        connection.commit()
    return database.path


def test_excel_remains_default_and_sources_share_distance_contract(tmp_path):
    assert DEFAULT_PROVIDER_ID == "excel"
    assert isinstance(get_data_provider(), ExcelProvider)
    assert isinstance(get_data_provider("gpexe"), GPExeProvider)

    excel_source = pd.DataFrame({
        "Date": [pd.Timestamp("2026-08-01T10:00:00")],
        "Athlete": ["MARIO ROSSI"],
        "distance (m)": [5000.0],
    })
    excel = ExcelProvider().load_pilot_distance_data(excel_source)
    gpexe = GPExeProvider().load_pilot_distance_data(
        _build_pilot_database(tmp_path / "pas_connect.sqlite3")
    )

    common_columns = ["Date", "Athlete", "Distance (m)"]
    pd.testing.assert_frame_equal(
        excel[common_columns],
        gpexe[common_columns],
        check_dtype=False,
    )
    assert excel.iloc[0]["Source"] == "Excel"
    assert gpexe.iloc[0]["Source"] == "GPExe"


def test_gpexe_pilot_reads_only_pas_connect_sqlite(tmp_path):
    export = tmp_path / "gpexe.csv"
    export.write_text("Distance\n5000\n", encoding="utf-8")
    with pytest.raises(Exception, match="esclusivamente il database PAS Connect"):
        GPExeProvider().load_pilot_distance_data(export)


def test_gpexe_distance_prefers_identifier_kpi_and_converts_km(tmp_path):
    path = _build_pilot_database(tmp_path / "pas_connect.sqlite3")
    with sqlite3.connect(path) as connection:
        connection.execute(
            """UPDATE gpexe_athlete_session_kpis
               SET value='5', uom='km'
               WHERE provider_athlete_session_id=20 AND source='identifierKpi'"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
               provider_athlete_session_id, source, position, name, value,
               kpi_group, uom, unit, raw_json
               ) VALUES(20, 'kpi', 0, 'Distance', '9999', 'GPS', 'm', 'distance', '{}')"""
        )
        connection.commit()
    frame = GPExeProvider().load_pilot_distance_data(path)
    assert len(frame) == 1
    assert frame.iloc[0]["Distance (m)"] == 5000.0


def test_distance_pilot_is_the_only_new_analytic_view():
    app = open("app.py", encoding="utf-8").read()
    assert '"📏 Distance Pilot"' in app
    assert "load_pilot_distance_data" in app
    assert 'st.session_state["pas_data_source"] = "excel"' not in app
