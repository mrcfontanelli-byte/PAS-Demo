from __future__ import annotations

import json
from pathlib import Path

import pytest

from pas_connect import (
    GPExeConfig,
    GPExeRESTClient,
    RESTProcessingResponse,
    map_rest_athlete_reference,
    map_rest_athlete_session,
    map_rest_athlete_session_list,
    map_rest_scalar_kpis,
    map_rest_team_session,
    map_rest_track_reference,
    map_rest_zones,
)
from pas_connect.exceptions import RateLimitError
from pas_connect.rest_mapper import PROVENANCE, ZONE_NAMES

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def team_session():
    return load_fixture("gpexe_rest_team_session_143261_anonymized.json")


@pytest.fixture
def athlete_session_list():
    return load_fixture("gpexe_rest_athlete_sessions_143261_anonymized.json")


@pytest.fixture
def athlete_session():
    return load_fixture("gpexe_rest_athlete_session_anonymized.json")


def test_team_session_fixture_matches_observed_rest_contract(team_session):
    assert set(team_session) == {
        "general", "header", "timing", "category", "tags", "drill",
        "status", "counts", "table_data",
    }
    assert isinstance(team_session["general"]["id"], int)
    assert isinstance(team_session["general"]["team"], int)
    assert isinstance(team_session["header"]["start_timestamp"], str)
    assert isinstance(team_session["header"]["total_time"], str)
    assert isinstance(team_session["category"], dict)
    assert isinstance(team_session["drill"], dict)
    assert isinstance(team_session["status"]["KPI_completed"], bool)
    assert isinstance(team_session["table_data"]["headers"], list)
    assert isinstance(team_session["table_data"]["athlete_sessions"], list)


def test_athlete_session_list_fixture_is_object_with_scalar_ids(athlete_session_list):
    assert set(athlete_session_list) == {"athletesessions_id"}
    assert all(isinstance(value, int) for value in athlete_session_list["athletesessions_id"])
    assert map_rest_athlete_session_list(athlete_session_list) == [910001, 910002, 910003]


def test_athlete_session_fixture_matches_observed_flat_contract(athlete_session):
    required_types = {
        "id": int, "athlete": int, "track": int, "teamsession": int,
        "duration": float, "total_time": float, "distance": float,
        "acceleration_events": int, "deceleration_events": int,
        "speed_events": int, "rpe": type(None), "max_values_speed": float,
    }
    for key, expected_type in required_types.items():
        assert isinstance(athlete_session[key], expected_type)
    for name in ZONE_NAMES:
        assert isinstance(athlete_session[name], list)
        assert {"zone_number", "lower_bound", "upper_bound", "distance", "time"} <= set(
            athlete_session[name][0]
        )


def test_rest_team_session_mapper_preserves_contract_and_raw(team_session):
    mapped = map_rest_team_session(team_session)
    assert mapped["provider_session_id"] == 143261
    assert mapped["team_id"] == 469
    assert mapped["match_cycle"] == "ANONYMIZED"
    assert mapped["category"] == {"id": 1, "name": "TRAINING"}
    assert mapped["raw"] == team_session
    assert mapped["provenance"] == "gpexe_rest_team_session_detail"


def test_rest_athlete_and_track_are_scalar_references():
    assert map_rest_athlete_reference(810001) == {
        "provider_player_id": 810001, "provenance": PROVENANCE,
    }
    assert map_rest_track_reference(710001) == {
        "provider_track_id": "710001", "provenance": PROVENANCE,
    }


def test_scalar_kpi_mapping_activates_only_demonstrated_metrics(athlete_session):
    by_name = {row["provider_name"]: row for row in map_rest_scalar_kpis(athlete_session)}
    expected = {
        "distance": "Distance", "duration": "Duration",
        "acceleration_events": "Acc Events", "deceleration_events": "Dec Events",
        "speed_events": "Speed Events", "rpe": "RPE",
    }
    for provider_name, canonical in expected.items():
        assert by_name[provider_name]["canonical_metric"] == canonical
        assert by_name[provider_name]["active"] is True
        assert by_name[provider_name]["provenance"] == PROVENANCE
        assert by_name[provider_name]["raw"]["name"] == provider_name


def test_null_rpe_remains_null_and_is_never_zero(athlete_session):
    rpe = next(row for row in map_rest_scalar_kpis(athlete_session) if row["provider_name"] == "rpe")
    assert rpe["value"] is None
    assert rpe["value_type"] == "null"
    assert rpe["raw"]["value"] is None


def test_max_speed_is_canonicalized_and_unknown_provider_metrics_remain_inactive(athlete_session):
    athlete_session["future_provider_metric"] = 12.5
    athlete_session["anaerobic_threshold_zone"] = 4.0
    athlete_session["high_intensity_training"] = 99.0
    by_name = {row["provider_name"]: row for row in map_rest_scalar_kpis(athlete_session)}
    assert by_name["max_values_speed"]["active"] is True
    assert by_name["max_values_speed"]["canonical_metric"] == "Max Speed"
    assert by_name["max_values_speed"]["value"] == pytest.approx(30.24)
    assert by_name["max_values_speed"]["provider_unit"] == "m/s"
    assert by_name["max_values_speed"]["unit"] == "km/h"
    assert by_name["future_provider_metric"]["active"] is False
    assert by_name["future_provider_metric"]["canonical_metric"] is None
    assert by_name["future_provider_metric"]["value_type"] == "number"
    assert by_name["anaerobic_threshold_zone"]["active"] is False
    assert by_name["high_intensity_training"]["active"] is False


def test_zones_preserve_bounds_and_expose_dynamic_speed_descriptor(athlete_session):
    zones = map_rest_zones(athlete_session)
    assert set(zones) == set(ZONE_NAMES)
    speed = zones["speed_zones"][0]
    assert speed["lower_bound"] is None
    assert speed["upper_bound"] == 36.0
    assert speed["distance"] == 1000.0
    assert speed["threshold_unit"] == "km/h"
    assert speed["unit"] == "m"
    assert speed["canonical_metric"] == "speed_zone_distance:km/h::36"
    assert speed["display_label"] == "Distance <36 km/h (m)"
    assert speed["active"] is True
    assert speed["raw"] == athlete_session["speed_zones"][0]
    assert all(zone["metric_family"] == "Speed Zone Distance" for zone in zones["speed_zones"])


def test_complete_rest_athlete_session_mapping_has_raw_provenance(athlete_session):
    mapped = map_rest_athlete_session(athlete_session)
    assert mapped["provider_athlete_session_id"] == 910001
    assert mapped["provider_session_id"] == 143261
    assert mapped["athlete"]["provider_player_id"] == 810001
    assert mapped["track"]["provider_track_id"] == "710001"
    assert mapped["raw"] == athlete_session
    assert mapped["provenance"] == PROVENANCE


def test_http_202_returns_processing_state_without_polling():
    calls = []

    def transport(*_):
        calls.append(True)
        return 202, b'{"status":"processing"}', {"Retry-After": "5"}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="token", max_retries=3),
        transport=transport,
    )
    result = client.team_session(143261, all_params=True)
    assert result == RESTProcessingResponse(
        payload={"status": "processing"}, retry_after_seconds=5.0,
    )
    assert calls == [True]


def test_official_rate_limit_waits_before_request_41():
    now = [0.0]
    sleeps = []
    calls = []

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="token", max_retries=0),
        transport=lambda *_: (calls.append(True) or (200, b'{"athletesessions_id":[]}', {})),
        sleep=sleep,
        clock=lambda: now[0],
    )
    for _ in range(41):
        client.athlete_sessions(143261)
    assert len(calls) == 41
    assert sleeps == [60.0]


def test_429_retry_after_contract_is_preserved():
    delays = []
    calls = []

    def transport(*_):
        calls.append(True)
        return 429, b"{}", {"Retry-After": "3"}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="token", max_retries=1),
        transport=transport,
        sleep=delays.append,
    )
    with pytest.raises(RateLimitError):
        client.athlete_sessions(143261)
    assert calls == [True, True]
    assert delays == [3.0]


def test_rest_mapping_has_no_excel_fallback_or_operational_sync_dependency():
    import pas_connect.rest_mapper as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    assert "excel" not in source
    assert "run_full_sync" not in source
    assert "pasconnectdatabase" not in source
