import json
import sqlite3
from pathlib import Path

from modules.data_loader import aggregate_player_day
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
        connection.execute(
            """INSERT INTO gpexe_athletes(
            provider_player_id,first_name,last_name,player_name,synced_at,raw_json
            ) VALUES(100,NULL,NULL,'Fallback Label','now','{}')"""
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
    assert row["Athlete"] == "TECHNICAL ATHLETE"
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


def test_rest_only_session_builds_dashboard_frame_without_legacy_rows(tmp_path: Path):
    db = PASConnectDatabase(tmp_path / "rest-only.sqlite3")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_team_sessions(
            provider_session_id,team_id,session_name,start_timestamp,is_stats_valid,
            drill_enabled,state,synced_at,raw_json
            ) VALUES(143261,543,'FULL TRAINING','2026-07-31T10:19:42',1,1,
            'READY','now','{}')"""
        )
        for index in range(27):
            athlete_session_id = 200000 + index
            player_id = 300000 + index
            connection.execute(
                """INSERT INTO gpexe_athletes(
                provider_player_id,first_name,last_name,player_name,synced_at,raw_json
                ) VALUES(?,?,?,?,?,'{}')""",
                (player_id, None, None, f"GPExe Athlete {player_id}", "now"),
            )
            connection.execute(
                """INSERT INTO gpexe_athlete_session_details(
                provider_athlete_session_id,provider_session_id,provider_player_id,
                duration,state,starter,metrics_json,zones_json,synced_at,raw_json
                ) VALUES(?,143261,?,3600,'READY',1,'{}','{}','now','{}')""",
                (athlete_session_id, player_id),
            )
            metrics = (
                ("distance", 1200, "Distance", "m"),
                ("duration", 3600, "Duration", "s"),
                ("acceleration_events", 12, "Acc Events", ""),
                ("deceleration_events", 11, "Dec Events", ""),
                ("speed_events", 9, "Speed Events", ""),
                ("rpe", None, "RPE", ""),
            )
            for position, (name, value, group, unit) in enumerate(metrics):
                connection.execute(
                    """INSERT INTO gpexe_athlete_session_kpis(
                    provider_athlete_session_id,source,position,name,value,kpi_group,
                    uom,unit,raw_json) VALUES(?,'rest_v2',?,?,?,?,?,?, '{}')""",
                    (athlete_session_id, position, name, value, group, unit, unit),
                )
        connection.commit()

    assert has_compatible_performance_rows(db.path, session_ids=[143261]) is True
    frame = load_pas_performance_frame(db.path, session_ids=[143261])
    assert len(frame) == 27
    assert set(frame["Date"].dt.date) == {__import__("datetime").date(2026, 7, 31)}
    assert set(frame["GPExe TeamSession ID"]) == {143261}
    assert set(frame["Team ID"]) == {543}
    assert frame["Athlete ID"].notna().all()
    assert frame["Athlete"].str.strip().ne("").all()
    assert frame["Athlete"].nunique() == 27
    player_day = aggregate_player_day(frame)
    assert len(player_day) == 27
    assert player_day["Athlete"].nunique() == 27
    for column in ("distance (m)", "Duration (dec)", "acc events", "dec events", "speed events"):
        assert frame[column].notna().all()
    assert frame["RPE (CR10)"].isna().all()
    assert "max speed (km/h)" not in frame or frame["max speed (km/h)"].isna().all()
    assert __import__("datetime").date(2026, 7, 31) in set(frame["Date"].dt.date.unique())


def test_rest_only_bridge_falls_back_to_provider_player_id_without_athlete_lookup(tmp_path: Path):
    db = PASConnectDatabase(tmp_path / "missing-athlete.sqlite3")
    db.initialize()
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_team_sessions(
            provider_session_id,session_name,start_timestamp,is_stats_valid,
            drill_enabled,synced_at,raw_json
            ) VALUES(1,'Training','2026-08-01T10:00:00Z',1,1,'now','{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_details(
            provider_athlete_session_id,provider_session_id,provider_player_id,
            duration,starter,metrics_json,zones_json,synced_at,raw_json
            ) VALUES(10,1,3752,3600,1,'{}','{}','now','{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,
            uom,unit,raw_json
            ) VALUES(10,'rest_v2',0,'distance','1200','Distance','m','m','{}')"""
        )
        connection.commit()

    row = load_pas_performance_frame(db.path, session_ids=[1]).iloc[0]
    assert row["Athlete"] == "GPEXE ATHLETE 3752"
