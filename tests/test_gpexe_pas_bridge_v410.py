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
