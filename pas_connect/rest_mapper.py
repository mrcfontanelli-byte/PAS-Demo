"""Mapping puro del contratto REST GPExe osservato verso strutture canoniche PAS."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from typing import Any, Mapping

from modules.session_categories import canonical_session_category
from .dashboard_sessions import canonical_gpexe_dashboard_category
from .exceptions import MappingError

PROVENANCE = "gpexe_rest_athlete_session_detail"
ZONE_NAMES = (
    "speed_zones", "relative_speed_zones", "acc_zones", "dec_zones",
    "power_zones", "cardio_zones",
)
ACTIVE_CANONICAL_METRICS = {
    "distance": "Distance", "duration": "Duration",
    "acceleration_events": "Acc Events", "deceleration_events": "Dec Events",
    "speed_events": "Speed Events", "rpe": "RPE", "max_values_speed": "Max Speed",
}
CANONICAL_ACCUMULATION = {
    "Distance": "sum", "Duration": "sum", "Acc Events": "sum",
    "Dec Events": "sum", "Speed Events": "sum", "RPE": "mean", "Max Speed": "max",
}
REST_CANONICAL_UNITS = {
    "Distance": "m", "Duration": "s", "Acc Events": "", "Dec Events": "",
    "Speed Events": "", "RPE": "", "Max Speed": "km/h",
}
INACTIVE_PROVIDER_METRICS: dict[str, str] = {}
SPEED_ZONE_FAMILY = "Speed Zone Distance"
SPEED_PROVIDER_THRESHOLD_UNIT = "m/s"
SPEED_THRESHOLD_UNIT = "km/h"
SPEED_ZONE_VALUE_UNIT = "m"
SPEED_BOUND_NORMALIZATION_TOLERANCE = Decimal("0.000002")
NON_METRIC_FIELDS = {
    "id", "athlete", "track", "teamsession", "categories", "drill", "ground",
    "start_date", "end_date", "created_on", "updated_on", "state", "starter",
    "is_stats_valid", "need_reprocess", "tags", *ZONE_NAMES,
}


def _mapped_session_category(value: object) -> object:
    canonical = canonical_gpexe_dashboard_category(value)
    if isinstance(value, str) and value.lstrip().startswith("[") and canonical is not None:
        return canonical
    return canonical_session_category(value)


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
        "category": {
            "id": category.get("id"),
            "name": _mapped_session_category(category.get("name")),
        },
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


def _identity_text(value: object) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def map_rest_athlete_identity(
    payload: Mapping[str, Any],
    *,
    provenance: str = "gpexe_rest_athlete_roster",
) -> dict[str, Any]:
    """Mappa una riga roster senza introdurre dipendenze da TeamSession."""
    row = _mapping(payload, "Athlete roster row")
    athlete_id = _integer(row.get("id"), "Athlete ID")
    first_name = _identity_text(row.get("first_name"))
    last_name = _identity_text(row.get("last_name"))
    short_name = _identity_text(row.get("short_name"))
    provider_name = _identity_text(row.get("name"))
    full_name = " ".join(part for part in (first_name, last_name) if part) or None
    return {
        "provider_player_id": athlete_id,
        "first_name": first_name,
        "last_name": last_name,
        "short_name": short_name,
        "provider_name": provider_name,
        "player_name": provider_name or full_name or f"GPExe Athlete {athlete_id}",
        "provider_contract": "rest_v2",
        "identity_source": "rest_v2",
        "provenance": provenance,
        "raw": dict(row),
    }


def index_rest_athlete_identities(payload: object) -> dict[int, dict[str, Any]]:
    """Indicizza la prima pagina roster, fondendo duplicati in modo deterministico."""
    if not isinstance(payload, list):
        raise MappingError("Athlete roster REST deve essere una lista diretta.")
    result: dict[int, dict[str, Any]] = {}
    for raw in payload:
        mapped = map_rest_athlete_identity(_mapping(raw, "Athlete roster row"))
        athlete_id = int(mapped["provider_player_id"])
        existing = result.get(athlete_id)
        if existing is None:
            result[athlete_id] = mapped
            continue
        merged = dict(existing)
        for field in ("first_name", "last_name", "short_name", "provider_name"):
            if mapped.get(field) is not None:
                merged[field] = mapped[field]
        full_name = " ".join(
            part for part in (merged.get("first_name"), merged.get("last_name")) if part
        ) or None
        merged["player_name"] = (
            merged.get("provider_name") or full_name or f"GPExe Athlete {athlete_id}"
        )
        merged["raw"] = mapped["raw"]
        result[athlete_id] = merged
    return result


def map_rest_track_reference(value: object) -> dict[str, Any]:
    return {"provider_track_id": str(_integer(value, "Track ID")), "provenance": PROVENANCE}


def _value_type(value: object) -> str:
    if value is None: return "null"
    if isinstance(value, bool): return "boolean"
    if isinstance(value, int): return "integer"
    if isinstance(value, float): return "number"
    if isinstance(value, str): return "string"
    return type(value).__name__


def _finite_number(value: object) -> float | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _provider_bound(value: object) -> float | None:
    number = _finite_number(value)
    return number


def speed_bound_mps_to_kmh(value: object) -> float | None:
    """Converte un bound GPExe m/s in km/h normalizzando solo il rumore numerico."""
    number = _provider_bound(value)
    if number is None:
        return None
    try:
        converted = Decimal(str(number)) * Decimal("3.6")
        nearest_tenth = converted.quantize(Decimal("0.1"))
        if abs(converted - nearest_tenth) <= SPEED_BOUND_NORMALIZATION_TOLERANCE:
            converted = nearest_tenth
        else:
            converted = converted.quantize(Decimal("0.000001"))
        return float(converted.normalize())
    except InvalidOperation:
        return None


def _format_bound(value: float) -> str:
    return format(Decimal(str(value)).normalize(), "f")


def speed_zone_metric_key(lower_bound: float | None, upper_bound: float | None) -> str:
    lower = "" if lower_bound is None else _format_bound(lower_bound)
    upper = "" if upper_bound is None else _format_bound(upper_bound)
    return f"speed_zone_distance:{SPEED_THRESHOLD_UNIT}:{lower}:{upper}"


def speed_zone_label(lower_bound: float | None, upper_bound: float | None) -> str:
    if lower_bound is None and upper_bound is not None:
        interval = f"<{_format_bound(upper_bound)}"
    elif upper_bound is None and lower_bound is not None:
        interval = f">{_format_bound(lower_bound)}"
    else:
        interval = f"{_format_bound(lower_bound)}{chr(0x2013)}{_format_bound(upper_bound)}"
    return f"Distance {interval} {SPEED_THRESHOLD_UNIT} ({SPEED_ZONE_VALUE_UNIT})"


def map_rest_speed_zone(zone: Mapping[str, Any]) -> dict[str, Any]:
    raw = dict(_mapping(zone, "speed_zones"))
    original_lower = _provider_bound(raw.get("lower_bound"))
    original_upper = _provider_bound(raw.get("upper_bound"))
    lower = speed_bound_mps_to_kmh(original_lower)
    upper = speed_bound_mps_to_kmh(original_upper)
    distance = _finite_number(raw.get("distance"))
    valid_bounds = (lower is not None or upper is not None) and not (
        lower is not None and upper is not None and lower >= upper
    )
    active = valid_bounds and distance is not None
    return {
        "provider_name": "speed_zones",
        "provider_zone_number": raw.get("zone_number"),
        "zone_number": raw.get("zone_number"),
        "lower_bound": lower, "upper_bound": upper,
        "original_lower_bound_mps": original_lower,
        "original_upper_bound_mps": original_upper,
        "canonical_lower_bound_kmh": lower,
        "canonical_upper_bound_kmh": upper,
        "provider_threshold_unit": SPEED_PROVIDER_THRESHOLD_UNIT,
        "canonical_threshold_unit": SPEED_THRESHOLD_UNIT,
        "threshold_unit": SPEED_THRESHOLD_UNIT,
        "distance": distance, "value": distance, "value_unit": SPEED_ZONE_VALUE_UNIT,
        "time": raw.get("time"), "unit": SPEED_ZONE_VALUE_UNIT,
        "metric_family": SPEED_ZONE_FAMILY,
        "canonical_metric": speed_zone_metric_key(lower, upper) if valid_bounds else None,
        "display_label": speed_zone_label(lower, upper) if valid_bounds else None,
        "accumulation": "sum", "active": active,
        "provenance": PROVENANCE, "raw": raw,
    }


def _speed_zone_sort_key(zone: Mapping[str, Any]) -> tuple[float, float]:
    lower = zone.get("canonical_lower_bound_kmh")
    upper = zone.get("canonical_upper_bound_kmh")
    return (
        float("-inf") if lower is None else float(lower),
        float("inf") if upper is None else float(upper),
    )


def map_rest_scalar_kpis(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    row = _mapping(payload, "AthleteSession detail")
    metrics: list[dict[str, Any]] = []
    for name, value in row.items():
        if name in NON_METRIC_FIELDS or isinstance(value, (Mapping, list)):
            continue
        canonical = ACTIVE_CANONICAL_METRICS.get(name)
        proposed = INACTIVE_PROVIDER_METRICS.get(name)
        raw_value = value
        unit = REST_CANONICAL_UNITS.get(canonical)
        provider_unit = None
        conversion = None
        if name == "max_values_speed":
            provider_unit = "m/s"
            conversion = "x3.6"
            number = _finite_number(value)
            value = number * 3.6 if number is not None else None
        value_type = _value_type(value)
        raw = {"name": str(name), "value": raw_value, "type": _value_type(raw_value), "unit": provider_unit}
        if name == "max_values_speed":
            raw.update({
                "provider_metric_name": str(name), "provider_value": raw_value,
                "provider_unit": provider_unit, "canonical_value": value,
                "canonical_unit": unit, "conversion": conversion,
            })
        metrics.append({
            "provider_name": str(name), "value": value, "value_type": value_type,
            "unit": unit, "provider_unit": provider_unit, "conversion": conversion,
            "canonical_metric": canonical,
            "accumulation": CANONICAL_ACCUMULATION.get(canonical),
            "proposed_canonical_metric": proposed, "active": canonical is not None,
            "provenance": PROVENANCE,
            "raw": raw,
        })
    return metrics


def map_rest_zones(payload: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    row = _mapping(payload, "AthleteSession detail")
    result: dict[str, list[dict[str, Any]]] = {}
    for zone_name in ZONE_NAMES:
        values = row.get(zone_name)
        if not isinstance(values, list):
            raise MappingError(f"{zone_name} REST GPExe deve essere un array.")
        if zone_name == "speed_zones":
            result[zone_name] = sorted(
                (map_rest_speed_zone(_mapping(item, zone_name)) for item in values),
                key=_speed_zone_sort_key,
            )
            continue
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
