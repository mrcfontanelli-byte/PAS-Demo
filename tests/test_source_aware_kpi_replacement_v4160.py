from __future__ import annotations

import json
import sqlite3

import pytest

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.rest_mapper import map_rest_speed_zone
from pas_connect.rest_persistence import GPExeRESTPersistenceGate
from pas_connect.rest_service import RESTBundleResult


def _rest_result(distance: float = 100.0) -> RESTBundleResult:
    zone = map_rest_speed_zone({
        "zone_number": 9, "lower_bound": 5.5, "upper_bound": 7.0,
        "distance": distance, "time": 10,
    })
    metrics = [
        {"provider_name": "distance", "canonical_metric": "Distance", "value": distance,
         "unit": "m", "active": True, "provenance": "rest_detail", "raw": {}},
    ]
    session = {
        "provider_athlete_session_id": 100, "provider_session_id": 10,
        "athlete": {"provider_player_id": 20}, "track": {"provider_track_id": "30"},
        "state": "READY", "is_stats_valid": True, "total_time": 60,
        "kpis": metrics, "zones": {"speed_zones": [zone]},
        "raw": {"id": 100}, "provenance": "rest_detail",
    }
    bundle = {
        "provider_contract": "rest_v2", "requested_team_session_id": 10,
        "team_session": {
            "provider_session_id": 10, "team_id": 469,
            "category": {"id": 1, "name": "Training"}, "nature": "training",
            "start_timestamp": "2025-08-03T10:00:00Z", "total_time": 60,
            "is_stats_valid": True, "drill": {}, "raw": {"general": {"id": 10}},
        },
        "athlete_session_ids": (100,), "athlete_sessions": (session,),
    }
    return RESTBundleResult("READY", False, bundle, ())


def _sources(db: PASConnectDatabase) -> dict[str, list[tuple[str, str | None]]]:
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT source,name,value FROM gpexe_athlete_session_kpis ORDER BY source,position"
        ).fetchall()
    result: dict[str, list[tuple[str, str | None]]] = {}
    for source, name, value in rows:
        result.setdefault(source, []).append((name, value))
    return result


def _seed_graphql(db: PASConnectDatabase) -> None:
    with db.connect() as connection:
        connection.executemany(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json
            ) VALUES(100,?,?,?,?,?,?,?,?)""",
            [
                ("identifierKpi", 0, "legacy_identifier", "1", None, None, None, "{}"),
                ("kpi", 0, "legacy_kpi", "2", None, None, None, "{}"),
            ],
        )
        connection.commit()


def test_rest_replaces_only_rest_sources_and_is_idempotent(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    gate = GPExeRESTPersistenceGate(db)
    gate.publish(_rest_result(100), season="2025/2026")
    _seed_graphql(db)
    first = gate.publish(_rest_result(200), season="2025/2026")
    second = gate.publish(_rest_result(200), season="2025/2026")
    sources = _sources(db)
    assert first.kpis_count == second.kpis_count == 2
    assert sources["identifierKpi"] == [("legacy_identifier", "1")]
    assert sources["kpi"] == [("legacy_kpi", "2")]
    assert sources["rest_v2"] == [("distance", "200")]
    assert len(sources["rest_v2_speed_zone"]) == 1
    assert len([item for values in sources.values() for item in values]) == 4


def test_graphql_replaces_only_graphql_sources_and_preserves_rest(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    gate = GPExeRESTPersistenceGate(db)
    gate.publish(_rest_result(), season="2025/2026")
    parent, athletes, sessions = gate._adapt_bundle(_rest_result().bundle, season="2025/2026")
    sessions[0].pop("provider_kpis")
    sessions[0]["identifier_kpi"] = [{"name": "new_identifier", "value": 3}]
    sessions[0]["kpi"] = [{"name": "new_kpi", "value": 4}]
    db.upsert_graphql_team_session_bundle(parent, athletes, sessions, season="2025/2026")
    sources = _sources(db)
    assert sources["identifierKpi"] == [("new_identifier", "3")]
    assert sources["kpi"] == [("new_kpi", "4")]
    assert "rest_v2" in sources and "rest_v2_speed_zone" in sources


def test_source_aware_replace_rolls_back_all_sources_on_error(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    gate = GPExeRESTPersistenceGate(db)
    gate.publish(_rest_result(), season="2025/2026")
    _seed_graphql(db)
    before = _sources(db)
    parent, athletes, sessions = gate._adapt_bundle(_rest_result(999).bundle, season="2025/2026")
    sessions[0]["provider_kpis"].append(object())
    with pytest.raises(AttributeError):
        db.upsert_team_session_bundle(
            parent, athletes, sessions, season="2025/2026",
            replace_kpi_sources={"rest_v2", "rest_v2_speed_zone"},
        )
    assert _sources(db) == before


def test_speed_zone_family_and_schema_12(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    GPExeRESTPersistenceGate(db).publish(_rest_result(), season="2025/2026")
    with sqlite3.connect(db.path) as connection:
        group_name, raw_value = connection.execute(
            "SELECT kpi_group,raw_json FROM gpexe_athlete_session_kpis "
            "WHERE source='rest_v2_speed_zone'"
        ).fetchone()
    raw = json.loads(raw_value)["raw"]
    assert group_name == "Speed Zone Distance"
    assert raw["metric_family"] == "speed_zone_distance"
    assert raw["provider_zone_number"] == 9
    assert raw["threshold_snapshot"]["original_lower_bound_mps"] == 5.5
    assert raw["threshold_snapshot"]["canonical_lower_bound_kmh"] == 19.8
    assert SCHEMA_VERSION == 12
