from pathlib import Path
import sqlite3

import pytest

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.pas_bridge import available_athletes
from pas_connect.mapper import map_graphql_athlete, map_graphql_athlete_session, map_team_session


def _mapped_bundle(value=100):
    raw_session = {"id": 10, "team": 543, "name": "FULL TRAINING", "startTimestamp": "2026-07-31"}
    athlete = {"id": 20, "firstName": "Ada", "lastName": "Rossi"}
    raw_athlete_session = {
        "id": 30, "athlete": athlete, "track": {"id": "40", "athlete": {"id": 20}},
        "identifierKpi": [{"name": "athlete", "value": 20}],
        "kpi": [{"name": "total_distance", "value": value, "unit": "m"}],
    }
    return (
        map_team_session(raw_session),
        [map_graphql_athlete(athlete, team_id=543)],
        [map_graphql_athlete_session(raw_athlete_session, team_session_id=10, template_id=None)],
    )


def test_schema_10_to_12_is_additive(tmp_path: Path):
    path = tmp_path / "pas.sqlite3"
    database = PASConnectDatabase(path)
    database.initialize()
    with database.connect() as connection:
        connection.execute("UPDATE pas_connect_meta SET value='10' WHERE key='schema_version'")
        connection.execute("INSERT INTO gpexe_team_sessions(provider_session_id,session_name,synced_at,raw_json) VALUES(1,'legacy','now','{}')")
        connection.commit()
    database.initialize()
    with database.connect() as connection:
        assert connection.execute("SELECT value FROM pas_connect_meta WHERE key='schema_version'").fetchone()[0] == "12"
        assert connection.execute("SELECT session_name FROM gpexe_team_sessions WHERE provider_session_id=1").fetchone()[0] == "legacy"
        assert connection.execute("SELECT name FROM sqlite_master WHERE name='gpexe_session_sync_results'").fetchone()
        columns = {row[1] for row in connection.execute("PRAGMA table_info(gpexe_sync_runs)")}
        assert {"provider", "team_id", "season", "mode", "retry_of_run_id", "summary_json"} <= columns
        assert connection.execute(
            "SELECT name FROM sqlite_master WHERE name='gpexe_athlete_team_memberships'"
        ).fetchone()
    assert SCHEMA_VERSION == 12


def test_schema_11_migrates_legacy_athlete_team_without_loss(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute("DROP TABLE gpexe_athlete_team_memberships")
        connection.execute("UPDATE pas_connect_meta SET value='11' WHERE key='schema_version'")
        connection.execute(
            """INSERT INTO gpexe_athletes(
            provider_player_id,player_name,team_id,synced_at,raw_json)
            VALUES(77,'ATLETA LEGACY',469,'legacy-time','{}')"""
        )
        connection.commit()
    database.initialize()
    with database.connect() as connection:
        assert connection.execute(
            "SELECT value FROM pas_connect_meta WHERE key='schema_version'"
        ).fetchone()[0] == "12"
        assert [tuple(row) for row in connection.execute(
            """SELECT provider_player_id,team_id,season
            FROM gpexe_athlete_team_memberships"""
        ).fetchall()] == [(77, 469, "")]
        assert tuple(connection.execute(
            "SELECT player_name,team_id FROM gpexe_athletes WHERE provider_player_id=77"
        ).fetchone()) == ("ATLETA LEGACY", 469)


def test_schema_11_backfills_historical_membership_from_unique_team_profile(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute("DROP TABLE gpexe_athlete_team_memberships")
        connection.execute("UPDATE pas_connect_meta SET value='11' WHERE key='schema_version'")
        connection.execute(
            "INSERT INTO gpexe_athletes(provider_player_id,player_name,team_id,synced_at,raw_json) "
            "VALUES(77,'ATLETA STORICO',543,'legacy-time','{}')"
        )
        connection.execute(
            "INSERT INTO gpexe_team_sessions(provider_session_id,team_id,session_name,synced_at,raw_json) "
            "VALUES(10,469,'SESSIONE STORICA','legacy-time','{}')"
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_details(
            provider_athlete_session_id,provider_session_id,provider_player_id,
            metrics_json,zones_json,synced_at,raw_json)
            VALUES(20,10,77,'{}','{}','legacy-time','{}')"""
        )
        connection.execute(
            """INSERT INTO pas_metric_profiles(
            team_id,team_name,season,canonical_metric,provider_metric_name,
            threshold_unit,source,created_at,updated_at)
            VALUES('469','TEAM','2025-2026','Distance','distance','m','GPExe','now','now')"""
        )
        connection.commit()
    database.initialize()
    with database.connect() as connection:
        assert connection.execute(
            """SELECT COUNT(*) FROM gpexe_athlete_team_memberships
            WHERE provider_player_id=77 AND team_id=469 AND season='2025/2026'"""
        ).fetchone()[0] == 1


def test_atomic_bundle_rollback_preserves_last_valid_kpis(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    parent, athletes, sessions = _mapped_bundle(100)
    assert database.upsert_graphql_team_session_bundle(parent, athletes, sessions) == (1, 1, 2)
    broken = [dict(sessions[0], kpi=[{"name": "total_distance", "value": 999}, object()])]
    with pytest.raises(AttributeError):
        database.upsert_graphql_team_session_bundle(parent, athletes, broken)
    with database.connect() as connection:
        values = [row[0] for row in connection.execute(
            "SELECT value FROM gpexe_athlete_session_kpis WHERE provider_athlete_session_id=30 AND source='kpi'"
        )]
    assert values == ["100"]


def test_partial_structural_bundle_never_replaces_last_valid_bundle(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    parent, athletes, sessions = _mapped_bundle(100)
    assert database.upsert_graphql_team_session_bundle(parent, athletes, sessions) == (1, 1, 2)
    incomplete_parent = dict(parent, session_name="INCOMPLETE SHOULD NOT PUBLISH")
    incomplete_sessions = [dict(sessions[0], identifier_kpi=[], kpi=[])]
    assert database.upsert_graphql_team_session_bundle(
        incomplete_parent, athletes, incomplete_sessions, replace_kpis=False,
    ) == (0, 0, 0)
    with database.connect() as connection:
        assert connection.execute(
            "SELECT session_name FROM gpexe_team_sessions WHERE provider_session_id=10"
        ).fetchone()[0] == "FULL TRAINING"
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_athlete_session_kpis WHERE provider_athlete_session_id=30"
        ).fetchone()[0] == 2


def test_same_provider_athlete_supports_multiple_teams_and_seasons_idempotently(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    parent_469, athletes_469, sessions_469 = _mapped_bundle(100)
    parent_469 = dict(parent_469, team_id=469)
    athletes_469 = [dict(athletes_469[0], team_id=469)]
    athletes_543 = [dict(athletes_469[0], team_id=543)]
    shared_id = athletes_469[0]["provider_player_id"]
    assert database.upsert_graphql_team_session_bundle(
        parent_469, athletes_469, sessions_469, season="2025/2026",
    ) == (1, 1, 2)

    parent_543 = dict(parent_469, provider_session_id=11, team_id=543)
    sessions_543 = [dict(
        sessions_469[0], provider_athlete_session_id=31, provider_session_id=11,
        track=dict(sessions_469[0]["track"], id="41"), track_id="41",
    )]
    database.upsert_graphql_team_session_bundle(
        parent_543, athletes_543, sessions_543, season="2026/2027",
    )
    database.upsert_graphql_team_session_bundle(
        parent_543, athletes_543, sessions_543, season="2027/2028",
    )
    before_second = database.counts()
    database.upsert_graphql_team_session_bundle(
        parent_543, athletes_543, sessions_543, season="2027/2028",
    )
    assert database.counts() == before_second

    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_athletes WHERE provider_player_id=?", (shared_id,)
        ).fetchone()[0] == 1
        assert connection.execute(
            "SELECT team_id FROM gpexe_athletes WHERE provider_player_id=?", (shared_id,)
        ).fetchone()[0] == 469
        assert [tuple(row) for row in connection.execute(
            """SELECT team_id,season FROM gpexe_athlete_team_memberships
            WHERE provider_player_id=? ORDER BY team_id,season""", (shared_id,)
        ).fetchall()] == [
            (469, "2025/2026"), (543, "2026/2027"), (543, "2027/2028"),
        ]
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_athlete_session_details"
        ).fetchone()[0] == 2
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_athlete_session_kpis"
        ).fetchone()[0] == 4
    assert [row["provider_player_id"] for row in available_athletes(
        database.path, team_id=469, season="2025/2026", selected_session_ids=[10],
    )] == [shared_id]
    assert [row["provider_player_id"] for row in available_athletes(
        database.path, team_id=543, season="2026/2027", selected_session_ids=[11],
    )] == [shared_id]
    assert available_athletes(
        database.path, team_id=543, season="2026/2027", selected_session_ids=[],
    ) == []
    assert [row["provider_player_id"] for row in available_athletes(
        database.path, team_id=543, season="2026/2027", selected_session_ids=[10, 11],
    )] == [shared_id]
