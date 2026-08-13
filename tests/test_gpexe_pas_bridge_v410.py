import json
import sqlite3
from pathlib import Path

from pas_connect.database import PASConnectDatabase
from pas_connect.pas_bridge import available_sessions, has_compatible_performance_rows, load_pas_performance_frame


def test_gpexe_sqlite_bridge_builds_pas_frame(tmp_path: Path):
    db = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    db.initialize()
    with db.connect() as connection:
        connection.execute("INSERT INTO gpexe_team_sessions(provider_session_id, session_name, start_timestamp, is_stats_valid, drill_enabled, synced_at, raw_json) VALUES(1,'Training','2026-08-01T10:00:00Z',1,1,'now','{}')")
        connection.execute("INSERT INTO gpexe_session_athlete_rows(provider_session_id, provider_athlete_session_id, athlete_first_name, athlete_last_name, athlete_role, state, metrics_json, raw_json, synced_at) VALUES(1,10,'Mario','Rossi','Midfielder','valid',?,'{}','now')", (json.dumps({'Distance': 5000, 'Max Speed': 31.2}),))
        connection.commit()
    assert len(available_sessions(db.path)) == 1
    frame = load_pas_performance_frame(db.path, session_ids=[1])
    assert frame.iloc[0]['Athlete'] == 'MARIO ROSSI'
    assert frame.iloc[0]['distance (m)'] == 5000
    assert frame.iloc[0]['GPExe TeamSession ID'] == 1
    assert has_compatible_performance_rows(db.path, session_ids=[1]) is True


def test_partial_pas_connect_database_is_not_analytically_compatible(tmp_path: Path):
    db = PASConnectDatabase(tmp_path / "partial.sqlite3")
    db.initialize()
    with db.connect() as connection:
        connection.execute("INSERT INTO gpexe_team_sessions(provider_session_id, session_name, start_timestamp, is_stats_valid, drill_enabled, synced_at, raw_json) VALUES(1,'Training','2026-08-01T10:00:00Z',1,1,'now','{}')")
        connection.commit()

    assert len(available_sessions(db.path)) == 1
    assert has_compatible_performance_rows(db.path) is False


def test_bridge_projects_seven_rest_scalars_with_rest_ownership(tmp_path: Path):
    db = PASConnectDatabase(tmp_path / "source-aware.sqlite3")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_team_sessions(
            provider_session_id, session_name, start_timestamp, is_stats_valid,
            drill_enabled, synced_at, raw_json
            ) VALUES(1,'Training','2026-08-01T10:00:00Z',1,1,'now','{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_session_athlete_rows(
            provider_session_id, provider_athlete_session_id, athlete_first_name,
            athlete_last_name, athlete_role, state, metrics_json, raw_json, synced_at
            ) VALUES(1,10,'Technical','Athlete','Midfielder','valid',?,'{}','now')""",
            (json.dumps({"Distance": 9999, "RPE": 10, "Max Speed": 99}),),
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_details(
            provider_athlete_session_id, provider_session_id, provider_player_id,
            duration, starter, metrics_json, zones_json, synced_at, raw_json
            ) VALUES(10,1,100,3600,1,'{}','{}','now','{}')"""
        )
        values = [
            ("distance", "1234.5", "Distance", None),
            ("duration", "3600", "Duration", None),
            ("acceleration_events", "12", "Acc Events", ""),
            ("deceleration_events", "11", "Dec Events", ""),
            ("speed_events", "9", "Speed Events", ""),
            ("rpe", None, "RPE", ""),
            ("max_values_speed", "27", "Max Speed", "km/h"),
        ]
        for position, (name, value, group, unit) in enumerate(values):
            connection.execute(
                """INSERT INTO gpexe_athlete_session_kpis(
                provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json
                ) VALUES(10,'rest_v2',?,?,?,?,?,?,?)""",
                (position, name, value, group, unit, unit, json.dumps({"name": name, "value": value})),
            )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json
            ) VALUES(10,'kpi',0,'total_distance','8888','Distance','m','m','{}')"""
        )
        connection.commit()

    row = load_pas_performance_frame(db.path, session_ids=[1]).iloc[0]
    assert row["distance (m)"] == 1234.5
    assert row["Duration (dec)"] == 60
    assert row["acc events"] == 12
    assert row["dec events"] == 11
    assert row["speed events"] == 9
    assert row["RPE (CR10)"] is None
    assert row["max speed (km/h)"] == 27
    assert set(row["GPExe KPI Provenance"]) == {
        "Distance", "Duration", "Acc Events", "Dec Events", "Speed Events", "RPE", "Max Speed",
    }
    assert row["GPExe KPI Provenance"]["Distance"]["source"] == "rest_v2"
