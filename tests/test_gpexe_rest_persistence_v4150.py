from __future__ import annotations

import inspect
import json
import sqlite3

import pytest

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.rest_persistence import GPExeRESTPersistenceGate
from pas_connect.rest_service import RESTBundleResult


def _metric(name, canonical, value, *, active=True):
    return {
        "provider_name": name, "canonical_metric": canonical, "value": value,
        "value_type": "null" if value is None else "number", "unit": None,
        "active": active, "provenance": "gpexe_rest_athlete_session_detail",
        "raw": {"name": name, "value": value, "unit": None},
    }


def _ready(team_session_id=143261, team_id=15, athlete_id=701, session_id=801, track_id=901):
    metrics = [
        _metric("distance", "Distance", 1234.5),
        _metric("duration", "Duration", 3600),
        _metric("acceleration_events", "Acc Events", 12),
        _metric("deceleration_events", "Dec Events", 11),
        _metric("speed_events", "Speed Events", 9),
        _metric("rpe", "RPE", None),
        _metric("max_values_speed", None, 31.2, active=False),
        _metric("provider_extra", None, 7, active=False),
    ]
    athlete_session = {
        "provider_athlete_session_id": session_id,
        "provider_session_id": team_session_id,
        "athlete": {"provider_player_id": athlete_id},
        "track": {"provider_track_id": str(track_id)},
        "state": "READY", "starter": True, "is_stats_valid": True,
        "total_time": 3600, "kpis": metrics,
        "raw": {"id": session_id, "provider_extra": 7},
        "provenance": "gpexe_rest_athlete_session_detail",
    }
    bundle = {
        "provider_contract": "rest_v2", "requested_team_session_id": team_session_id,
        "team_session": {
            "provider_session_id": team_session_id, "team_id": team_id,
            "category": {"id": 3, "name": "Training"}, "nature": "training",
            "start_timestamp": "2026-01-01T10:00:00Z", "end_timestamp": None,
            "total_time": 3600, "is_stats_valid": True, "drill": {"enabled": False},
            "raw": {"general": {"id": team_session_id}},
        },
        "athlete_session_ids": (session_id,), "athlete_sessions": (athlete_session,),
    }
    return RESTBundleResult("READY", False, bundle, ())


def _db(tmp_path):
    return PASConnectDatabase(tmp_path / "pas-connect.sqlite3")


def _count(db, table):
    with db.connect() as connection:
        return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_ready_is_persisted_idempotently_without_duplicates(tmp_path):
    db = _db(tmp_path)
    gate = GPExeRESTPersistenceGate(db)
    first = gate.publish(_ready(), season="2025/26")
    second = gate.publish(_ready(), season="2025/26")
    assert first.published and second.published
    assert (first.athlete_sessions_count, first.tracks_count, first.kpis_count) == (1, 1, 6)
    assert _count(db, "gpexe_team_sessions") == 1
    assert _count(db, "gpexe_athlete_session_details") == 1
    assert _count(db, "gpexe_tracks") == 1
    assert _count(db, "gpexe_athlete_session_kpis") == 6


@pytest.mark.parametrize("status,processing", [("INCOMPLETE", False), ("FAILED", False), ("INCOMPLETE", True)])
def test_non_ready_or_processing_is_never_published(tmp_path, status, processing):
    ready = _ready()
    result = RESTBundleResult(status, processing, ready.bundle, ({"redacted": True},))
    db = _db(tmp_path)
    published = GPExeRESTPersistenceGate(db).publish(result, season="2025/26")
    assert not published.published
    assert not db.path.exists()


def test_atomic_rollback_leaves_no_partial_bundle(tmp_path):
    db = _db(tmp_path)
    gate = GPExeRESTPersistenceGate(db)
    parent, athletes, sessions = gate._adapt_bundle(_ready().bundle)
    sessions[0]["provider_kpis"].append(object())
    with pytest.raises(AttributeError):
        db.upsert_team_session_bundle(parent, athletes, sessions, season="2025/26")
    for table in ("gpexe_team_sessions", "gpexe_athletes", "gpexe_tracks",
                  "gpexe_athlete_session_details", "gpexe_athlete_session_kpis"):
        assert _count(db, table) == 0


def test_last_ready_is_preserved_when_later_bundle_is_incomplete(tmp_path):
    db = _db(tmp_path)
    gate = GPExeRESTPersistenceGate(db)
    gate.publish(_ready(), season="2025/26")
    changed = _ready()
    changed.bundle["athlete_sessions"][0]["kpis"][0]["value"] = 9999
    rejected = RESTBundleResult("INCOMPLETE", False, changed.bundle, ({"redacted": True},))
    assert not gate.publish(rejected, season="2025/26").published
    with db.connect() as connection:
        value = connection.execute(
            "SELECT value FROM gpexe_athlete_session_kpis WHERE kpi_group='Distance'"
        ).fetchone()[0]
    assert value == "1234.5"


def test_team_season_membership_and_team_isolation(tmp_path):
    db = _db(tmp_path)
    gate = GPExeRESTPersistenceGate(db)
    gate.publish(_ready(), season="2025/26")
    gate.publish(_ready(143262, 16, 701, 802, 902), season="2026/27")
    with db.connect() as connection:
        memberships = connection.execute(
            "SELECT team_id, season FROM gpexe_athlete_team_memberships ORDER BY team_id"
        ).fetchall()
        sessions = connection.execute(
            "SELECT provider_session_id, team_id FROM gpexe_team_sessions ORDER BY provider_session_id"
        ).fetchall()
    assert [tuple(row) for row in memberships] == [(15, "2025/26"), (16, "2026/27")]
    assert [tuple(row) for row in sessions] == [(143261, 15), (143262, 16)]


def test_rpe_null_unknown_inactive_and_rest_provenance(tmp_path):
    db = _db(tmp_path)
    GPExeRESTPersistenceGate(db).publish(_ready(), season="2025/26")
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT source, name, value, raw_json FROM gpexe_athlete_session_kpis ORDER BY position"
        ).fetchall()
        detail_raw = json.loads(connection.execute(
            "SELECT raw_json FROM gpexe_athlete_session_details"
        ).fetchone()[0])
    assert {row["source"] for row in rows} == {"rest_v2"}
    assert {row["name"] for row in rows} == {
        "distance", "duration", "acceleration_events", "deceleration_events", "speed_events", "rpe"
    }
    assert next(row["value"] for row in rows if row["name"] == "rpe") is None
    assert detail_raw["provider_contract"] == "rest_v2"
    assert detail_raw["provenance"] == "gpexe_rest_athlete_session_detail"
    assert "graphql" not in json.dumps([dict(row) for row in rows] + [detail_raw]).lower()


def test_schema_12_unchanged_and_no_excel_fallback():
    assert SCHEMA_VERSION == 12
    source = inspect.getsource(GPExeRESTPersistenceGate).lower()
    assert "excel" not in source
    assert "run_full_sync" not in source
