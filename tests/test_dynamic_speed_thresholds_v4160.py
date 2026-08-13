from __future__ import annotations

import inspect
import json
import sqlite3

import pytest

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.rest_mapper import map_rest_speed_zone, map_rest_zones, speed_bound_mps_to_kmh
from pas_connect.rest_persistence import GPExeRESTPersistenceGate
from pas_connect.rest_service import RESTBundleResult
from pas_connect.speed_zone_metrics import aggregate_speed_zone_values, descriptor_from_snapshot


def _zone(lower, upper, distance, number=3):
    return map_rest_speed_zone({
        "zone_number": number, "lower_bound": lower, "upper_bound": upper,
        "distance": distance, "time": 10,
    })


@pytest.mark.parametrize("lower,upper,label", [
    (5.5, 7, "Distance 19.8–25.2 km/h (m)"),
    (7, None, "Distance >25.2 km/h (m)"),
    (5.555555555555555, 6.944444444444445, "Distance 20–25 km/h (m)"),
    (6.944444444444445, None, "Distance >25 km/h (m)"),
    (None, 4, "Distance <14.4 km/h (m)"),
])
def test_dynamic_mapping_and_labels(lower, upper, label):
    mapped = _zone(lower, upper, 0)
    assert mapped["active"] is True
    assert mapped["display_label"] == label
    assert mapped["threshold_unit"] == "km/h"
    assert mapped["value_unit"] == "m"
    assert mapped["value"] == 0


def test_null_invalid_and_float_noise_contracts():
    assert not _zone(None, None, 10)["active"]
    assert not _zone(20, 25, None)["active"]
    noisy = _zone(5.499999999999, 6.999999999999, 5)
    assert noisy["display_label"] == "Distance 19.8–25.2 km/h (m)"
    assert noisy["original_lower_bound_mps"] == 5.499999999999
    assert noisy["original_upper_bound_mps"] == 6.999999999999


def test_central_numeric_conversion_and_non_equivalence():
    assert speed_bound_mps_to_kmh(5.5) == 19.8
    assert speed_bound_mps_to_kmh(7) == 25.2
    assert speed_bound_mps_to_kmh(5.555555555555555) == 20
    assert speed_bound_mps_to_kmh(6.944444444444445) == 25
    assert speed_bound_mps_to_kmh(5.4999999998) == 19.8
    assert speed_bound_mps_to_kmh(6.944444) == 25
    assert speed_bound_mps_to_kmh(20 / 3.6) != 19.8
    assert speed_bound_mps_to_kmh(25 / 3.6) != 25.2


def test_exact_identity_no_interpolation_or_zone_number_identity():
    serie_a = _zone(5.5, 7, 100, number=99)
    serie_b = _zone(20 / 3.6, 25 / 3.6, 100, number=99)
    same_bounds_other_number = _zone(5.5, 7, 100, number=1)
    assert serie_a["canonical_metric"] != serie_b["canonical_metric"]
    assert serie_a["canonical_metric"] == same_bounds_other_number["canonical_metric"]
    assert serie_a["display_label"] != serie_b["display_label"]
    source = inspect.getsource(map_rest_zones) + inspect.getsource(map_rest_speed_zone)
    assert "zone_number ==" not in source
    assert "19.8" not in inspect.getsource(map_rest_speed_zone)
    assert "25.2" not in inspect.getsource(map_rest_speed_zone)


def _result(team_id, season, team_session_id, athlete_session_id, zones):
    row = {
        "provider_athlete_session_id": athlete_session_id,
        "provider_session_id": team_session_id,
        "athlete": {"provider_player_id": athlete_session_id + 1000},
        "track": {"provider_track_id": str(athlete_session_id + 2000)},
        "state": "READY", "starter": True, "is_stats_valid": True,
        "total_time": 60, "kpis": [], "zones": {"speed_zones": zones},
        "raw": {"id": athlete_session_id},
        "provenance": "gpexe_rest_athlete_session_detail",
    }
    bundle = {
        "provider_contract": "rest_v2", "requested_team_session_id": team_session_id,
        "team_session": {
            "provider_session_id": team_session_id, "team_id": team_id,
            "category": {"id": 1, "name": "Training"}, "nature": "training",
            "start_timestamp": f"{season[:4]}-08-01T10:00:00Z", "total_time": 60,
            "is_stats_valid": True, "drill": {}, "raw": {"general": {"id": team_session_id}},
        },
        "athlete_session_ids": (athlete_session_id,), "athlete_sessions": (row,),
    }
    return RESTBundleResult("READY", False, bundle, ())


def test_schema12_persistence_idempotency_team_season_and_historical_snapshot(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    gate = GPExeRESTPersistenceGate(db)
    a = _result(469, "2025/2026", 100, 1000, [_zone(5.5, 7, 111), _zone(7, None, 22)])
    b = _result(543, "2026/2027", 200, 2000, [_zone(20/3.6, 25/3.6, 333), _zone(25/3.6, None, 44)])
    changed = _result(469, "2025/2026", 101, 1001, [_zone(20/3.6, 25/3.6, 555)])
    assert gate.publish(a, season="2025/2026").kpis_count == 2
    assert gate.publish(a, season="2025/2026").kpis_count == 2
    gate.publish(b, season="2026/2027")
    gate.publish(changed, season="2025/2026")
    assert SCHEMA_VERSION == 12
    with db.connect() as connection:
        rows = connection.execute(
            "SELECT d.provider_session_id,k.* FROM gpexe_athlete_session_kpis k "
            "JOIN gpexe_athlete_session_details d USING(provider_athlete_session_id) "
            "WHERE k.kpi_group='Speed Zone Distance' ORDER BY d.provider_session_id,k.position"
        ).fetchall()
    assert len(rows) == 5
    descriptors = [descriptor_from_snapshot(dict(row)) for row in rows]
    labels_by_session = {}
    for row, descriptor in zip(rows, descriptors):
        labels_by_session.setdefault(row["provider_session_id"], []).append(descriptor.label)
    assert labels_by_session[100] == ["Distance 19.8–25.2 km/h (m)", "Distance >25.2 km/h (m)"]
    assert labels_by_session[200] == ["Distance 20–25 km/h (m)", "Distance >25 km/h (m)"]
    assert labels_by_session[101] == ["Distance 20–25 km/h (m)"]
    first = descriptors[0]
    assert (first.team_id, first.season, first.team_session_id, first.athlete_session_id) == (
        469, "2025/2026", 100, 1000,
    )
    assert sorted(descriptors, key=lambda item: item.sort_key)[0].lower_bound == 19.8
    assert aggregate_speed_zone_values([111, 22, None]) == 133


def test_raw_provenance_and_provider_zone_number_are_snapshot_only(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    GPExeRESTPersistenceGate(db).publish(
        _result(469, "2025/2026", 100, 1000, [_zone(5.5, 7, 1, number=77)]),
        season="2025/2026",
    )
    with sqlite3.connect(db.path) as connection:
        raw = json.loads(connection.execute(
            "SELECT raw_json FROM gpexe_athlete_session_kpis WHERE kpi_group='Speed Zone Distance'"
        ).fetchone()[0])
    assert raw["source"] == "rest_v2_speed_zone"
    assert raw["raw"]["provider_contract"] == "rest_v2"
    assert raw["raw"]["metric_family"] == "speed_zone_distance"
    assert raw["raw"]["provider_zone_number"] == 77
    snapshot = raw["raw"]["threshold_snapshot"]
    assert snapshot["original_lower_bound_mps"] == 5.5
    assert snapshot["original_upper_bound_mps"] == 7
    assert snapshot["canonical_lower_bound_kmh"] == 19.8
    assert snapshot["canonical_upper_bound_kmh"] == 25.2
    assert snapshot["provider_threshold_unit"] == "m/s"
    assert snapshot["canonical_threshold_unit"] == "km/h"
    assert raw["raw"]["context_snapshot"] == {
        "team_id": 469, "season": "2025/2026",
        "team_session_id": 100, "athlete_session_id": 1000,
    }


def test_excel_static_semantics_only_match_exact_bounds():
    excel_z3 = (19.8, 25.2)
    assert (_zone(5.5, 7, 1)["lower_bound"], _zone(5.5, 7, 1)["upper_bound"]) == excel_z3
    assert (_zone(20/3.6, 25/3.6, 1)["lower_bound"], _zone(20/3.6, 25/3.6, 1)["upper_bound"]) != excel_z3


def test_payload_order_is_normalized_by_canonical_bounds():
    payload = {"speed_zones": [
        {"zone_number": 9, "lower_bound": 7, "upper_bound": None, "distance": 1},
        {"zone_number": 1, "lower_bound": None, "upper_bound": 4, "distance": 2},
        {"zone_number": 7, "lower_bound": 5.5, "upper_bound": 7, "distance": 3},
    ], "relative_speed_zones": [], "acc_zones": [], "dec_zones": [],
       "power_zones": [], "cardio_zones": []}
    zones = map_rest_zones(payload)["speed_zones"]
    assert [z["display_label"] for z in zones] == [
        "Distance <14.4 km/h (m)", "Distance 19.8–25.2 km/h (m)",
        "Distance >25.2 km/h (m)",
    ]
