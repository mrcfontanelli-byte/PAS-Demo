"""Mapping puro del contratto REST GPExe osservato verso strutture canoniche PAS."""
from __future__ import annotations

from typing import Any, Mapping

from .exceptions import MappingError

PROVENANCE = "gpexe_rest_athlete_session_detail"
ZONE_NAMES = (
    "speed_zones", "relative_speed_zones", "acc_zones", "dec_zones",
    "power_zones", "cardio_zones",
)
ACTIVE_CANONICAL_METRICS = {
    "distance": "Distance", "duration": "Duration",
    "acceleration_events": "Acc Events", "deceleration_events": "Dec Events",
    "speed_events": "Speed Events", "rpe": "RPE",
}
INACTIVE_PROVIDER_METRICS = {"max_values_speed": "Max Speed"}
NON_METRIC_FIELDS = {
    "id", "athlete", "track", "teamsession", "categories", "drill", "ground",
    "start_date", "end_date", "created_on", "updated_on", "state", "starter",
    "is_stats_valid", "need_reprocess", "tags", *ZONE_NAMES,
}


def _mapping(payload: object, label: str) -> Mapping[str, Any]:
    if not isinstance(payload, Mapping):
        raise MappingError(f"{label} REST GPExe deve essere un oggetto.")
    return payload


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise MappingError(f"{label} REST GPExe non valido.")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise MappingError(f"{label} REST GPExe non valido.") from exc
    if result <= 0:
        raise MappingError(f"{label} REST GPExe non valido.")
    return result


def map_rest_team_session(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = _mapping(payload, "TeamSession")
    general = _mapping(row.get("general"), "TeamSession.general")
    header = _mapping(row.get("header"), "TeamSession.header")
    timing = _mapping(row.get("timing"), "TeamSession.timing")
    category = _mapping(row.get("category"), "TeamSession.category")
    drill = _mapping(row.get("drill"), "TeamSession.drill")
    status = _mapping(row.get("status"), "TeamSession.status")
    match = _mapping(header.get("match") or {}, "TeamSession.match")
    return {
        "provider": "gpexe", "provider_contract": "rest_v2",
        "provider_session_id": _integer(general.get("id"), "TeamSession ID"),
        "team_id": _integer(general.get("team"), "Team ID"),
        "nature": general.get("nature"),
        "start_timestamp": header.get("start_timestamp") or timing.get("start_timestamp"),
        "end_timestamp": timing.get("end_timestamp"),
        "duration": timing.get("duration"),
        "total_time": header.get("total_time") or timing.get("total_time"),
        "category": {"id": category.get("id"), "name": category.get("name")},
        "tags": list(header.get("tags") or []), "drill": dict(drill),
        "match_cycle": match.get("cycle"), "athlete_count": header.get("athletes"),
        "is_stats_valid": status.get("is_stats_valid"), "processing_status": dict(status),
        "raw": dict(row), "provenance": "gpexe_rest_team_session_detail",
    }


def map_rest_athlete_session_list(payload: Mapping[str, Any]) -> list[int]:
    row = _mapping(payload, "AthleteSession list")
    values = row.get("athletesessions_id")
    if not isinstance(values, list):
        raise MappingError("AthleteSession list priva di athletesessions_id array.")
    result = [_integer(value, "AthleteSession ID") for value in values]
    if len(result) != len(set(result)):
        raise MappingError("AthleteSession list contiene ID duplicati.")
    return result


def map_rest_athlete_reference(value: object) -> dict[str, Any]:
    return {"provider_player_id": _integer(value, "Athlete ID"), "provenance": PROVENANCE}


def map_rest_track_reference(value: object) -> dict[str, Any]:
    return {"provider_track_id": str(_integer(value, "Track ID")), "provenance": PROVENANCE}


def _value_type(value: object) -> str:
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, str): return "string"
    return type(value).__name__


def map_rest_scalar_kpis(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    row = _mapping(payload, "AthleteSession detail")
    metrics: list[dict[str, Any]] = []
    for name, value in row.items():
        if name in NON_METRIC_FIELDS or isinstance(value, (Mapping, list)):
            continue
        canonical = ACTIVE_CANONICAL_METRICS.get(name)
        proposed = INACTIVE_PROVIDER_METRICS.get(name)
        value_type = _value_type(value)
        metrics.append({
            "provider_name": str(name), "value": value, "value_type": value_type,
            "unit": None, "canonical_metric": canonical,
            "proposed_canonical_metric": proposed, "active": canonical is not None,
            "provenance": PROVENANCE,
            "raw": {"name": str(name), "value": value, "type": value_type, "unit": None},
        })
    return metrics


def map_rest_zones(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    row = _mapping(payload, "AthleteSession detail")
    result: dict[str, list[dict[str, Any]]] = {}
    for zone_name in ZONE_NAMES:
        values = row.get(zone_name)
        if not isinstance(values, list):
            raise MappingError(f"{zone_name} REST GPExe deve essere un array.")
        result[zone_name] = [{
            "provider_name": zone_name, "zone_number": zone.get("zone_number"),
            "lower_bound": zone.get("lower_bound"), "upper_bound": zone.get("upper_bound"),
            "distance": zone.get("distance"), "time": zone.get("time"),
            "unit": None, "canonical_metric": None, "active": False,
            "provenance": PROVENANCE, "raw": dict(zone),
        } for zone in (_mapping(item, zone_name) for item in values)]
    return result


def map_rest_athlete_session(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = _mapping(payload, "AthleteSession detail")
    return {
        "provider": "gpexe", "provider_contract": "rest_v2",
        "provider_athlete_session_id": _integer(row.get("id"), "AthleteSession ID"),
        "provider_session_id": _integer(row.get("teamsession"), "TeamSession ID"),
        "athlete": map_rest_athlete_reference(row.get("athlete")),
        "track": map_rest_track_reference(row.get("track")),
        "duration": row.get("duration"), "total_time": row.get("total_time"),
        "state": row.get("state"), "starter": row.get("starter"),
        "is_stats_valid": row.get("is_stats_valid"),
        "kpis": map_rest_scalar_kpis(row), "zones": map_rest_zones(row),
        "raw": dict(row), "provenance": PROVENANCE,
    }
