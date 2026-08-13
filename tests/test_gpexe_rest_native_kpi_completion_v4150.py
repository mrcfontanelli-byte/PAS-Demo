from __future__ import annotations

import inspect

from pas_connect.database import SCHEMA_VERSION
from pas_connect.rest_mapper import map_rest_scalar_kpis, map_rest_zones
from pas_connect.rest_persistence import APPROVED_CANONICAL_METRICS, GPExeRESTPersistenceGate


def _payload(speed_zones):
    return {
        "max_values_speed": 8.4,
        "speed_zones": speed_zones,
        "relative_speed_zones": [], "acc_zones": [], "dec_zones": [],
        "power_zones": [], "cardio_zones": [],
    }


def test_max_values_speed_has_no_contract_unit_and_remains_inactive():
    metric = map_rest_scalar_kpis(_payload([]))[0]
    assert metric["provider_name"] == "max_values_speed"
    assert metric["value"] == 8.4
    assert metric["unit"] is None
    assert metric["canonical_metric"] is None
    assert metric["proposed_canonical_metric"] == "Max Speed"
    assert metric["active"] is False


def test_real_configurable_bounds_do_not_equal_pas_thresholds():
    real_bounds = [
        (None, 2.7777777777777777), (2.7777777777777777, 4.444444444444445),
        (4.444444444444445, 5.555555555555555),
        (5.555555555555555, 6.944444444444445),
        (6.944444444444445, None),
    ]
    assert (5.5, 7.0) not in real_bounds
    assert (7.0, None) not in real_bounds
    assert 5.5 * 3.6 == 19.8
    assert 7.0 * 3.6 == 25.2


def test_exact_and_open_ended_bounds_become_dynamic_metrics():
    zones = map_rest_zones(_payload([
        {"zone_number": 91, "lower_bound": 5.5, "upper_bound": 7.0,
         "distance": 321.0, "time": 20.0},
        {"zone_number": 17, "lower_bound": 7.0, "upper_bound": None,
         "distance": 45.0, "time": 4.0},
    ]))["speed_zones"]
    assert [(z["lower_bound"], z["upper_bound"]) for z in zones] == [(19.8, 25.2), (25.2, None)]
    assert [z["display_label"] for z in zones] == [
        "Distance 19.8–25.2 km/h (m)", "Distance >25.2 km/h (m)",
    ]
    assert all(z["unit"] == "m" and z["active"] for z in zones)


def test_missing_or_different_zones_keep_exact_dynamic_identity():
    missing = map_rest_zones(_payload([]))["speed_zones"]
    different = map_rest_zones(_payload([
        {"zone_number": 3, "lower_bound": 5.555555555555555,
         "upper_bound": 6.944444444444445, "distance": 100.0, "time": 10.0},
    ]))["speed_zones"]
    assert missing == []
    assert different[0]["canonical_metric"] == "speed_zone_distance:km/h:20:25"
    assert different[0]["distance"] == 100.0


def test_zone_mapping_does_not_select_a_hardcoded_zone_number():
    source = inspect.getsource(map_rest_zones)
    assert "zone_number ==" not in source
    assert "zone_number] ==" not in source


def test_phase_five_keeps_six_persistable_metrics_and_schema_12():
    assert APPROVED_CANONICAL_METRICS == {
        "Distance", "Duration", "Acc Events", "Dec Events", "Speed Events", "RPE",
    }
    assert SCHEMA_VERSION == 12
    source = inspect.getsource(GPExeRESTPersistenceGate).lower()
    assert "run_full_sync" not in source
    assert "excel" not in source
