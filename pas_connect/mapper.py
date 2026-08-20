"""Prime trasformazioni provider -> schema canonico PAS."""
from __future__ import annotations

from datetime import datetime
import re
from typing import Any, Iterable, Mapping

from modules.session_categories import canonical_session_category
from .exceptions import MappingError


def _required(payload: Mapping[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value is None:
        raise MappingError(f"Campo GPExe obbligatorio mancante: {key}")
    return value


def _normalize_season(value: object) -> object:
    text = str(value or "").strip()
    match = re.fullmatch(r"(\d{4})\s*[-/ ]\s*(\d{4})", text)
    return f"{match.group(1)}/{match.group(2)}" if match else (text or None)


def map_team(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": "gpexe",
        "provider_team_id": int(_required(payload, "id")),
        "team_name": str(_required(payload, "name")).strip(),
        "club_id": payload.get("club"),
        "season": _normalize_season(payload.get("season")),
        "sport": payload.get("sport"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "locked": bool(payload.get("locked", False)),
        "updated_at": payload.get("updated_on"),
        "raw": dict(payload),
    }


def map_athlete(payload: Mapping[str, Any]) -> dict[str, Any]:
    athlete_id = int(_required(payload, "id"))
    first_name = str(payload.get("first_name") or "").strip()
    last_name = str(payload.get("last_name") or "").strip()
    display_name = str(payload.get("name") or payload.get("short_name") or "").strip()
    if not display_name:
        display_name = " ".join(part for part in (last_name, first_name) if part).strip()
    if not display_name:
        raise MappingError(f"Atleta GPExe {athlete_id} privo di nome.")
    return {
        "provider": "gpexe",
        "provider_player_id": athlete_id,
        "external_player_id": payload.get("custom_id"),
        "first_name": first_name or None,
        "last_name": last_name or None,
        "player_name": display_name,
        "short_name": payload.get("short_name"),
        "birth_date": payload.get("birthdate"),
        "club_id": payload.get("club"),
        "photo_url": payload.get("picture"),
        "v0": payload.get("v0"),
        "a0": payload.get("a0"),
    }


def map_graphql_athlete(payload: Mapping[str, Any], *, team_id: object | None = None) -> dict[str, Any]:
    athlete_id = int(_required(payload, "id"))
    player_set = payload.get("playerSet")
    memberships = player_set if isinstance(player_set, list) else [player_set] if isinstance(player_set, Mapping) else []
    membership = next(
        (item for item in memberships if isinstance(item, Mapping) and str((item.get("team") or {}).get("id")) == str(team_id)),
        memberships[0] if memberships else {},
    )
    first_name = str(payload.get("firstName") or "").strip()
    last_name = str(payload.get("lastName") or "").strip()
    name = str(payload.get("name") or " ".join(x for x in (last_name, first_name) if x)).strip()
    return {
        "provider_player_id": athlete_id,
        "external_player_id": payload.get("customId"),
        "first_name": first_name or None,
        "last_name": last_name or None,
        "player_name": name or f"GPExe Athlete {athlete_id}",
        "short_name": payload.get("shortName"),
        "birth_date": payload.get("birthdate"),
        "photo_url": payload.get("thumbnail"),
        "team_id": int(team_id) if team_id not in (None, "") else None,
        "jersey_number": membership.get("number") if isinstance(membership, Mapping) else None,
        "is_active": payload.get("isActive"),
        "has_tracks": payload.get("hasTracks"),
        "raw": dict(payload),
    }


def map_graphql_athlete_session(
    payload: Mapping[str, Any], *, team_session_id: object, template_id: object | None,
) -> dict[str, Any]:
    session_id = int(_required(payload, "id"))
    athlete = payload.get("athlete") if isinstance(payload.get("athlete"), Mapping) else {}
    track = payload.get("track") if isinstance(payload.get("track"), Mapping) else {}
    total_time = payload.get("totalTime") if isinstance(payload.get("totalTime"), Mapping) else {}
    return {
        "provider_athlete_session_id": session_id,
        "provider_session_id": int(team_session_id),
        "provider_player_id": int(athlete["id"]) if athlete.get("id") not in (None, "") else None,
        "track_id": str(track.get("id")) if track.get("id") not in (None, "") else None,
        "master_athlete_session": payload.get("masterAthleteSession"),
        "drill_id": payload.get("drill"),
        "state": payload.get("state"),
        "is_stats_valid": payload.get("isStatsValid"),
        "starter": payload.get("starter"),
        "total_time": dict(total_time),
        "template_id": str(template_id) if template_id not in (None, "") else None,
        "track": dict(track),
        "identifier_kpi": [dict(item) for item in payload.get("identifierKpi", []) if isinstance(item, Mapping)],
        "kpi": [dict(item) for item in payload.get("kpi", []) if isinstance(item, Mapping)],
        "raw": dict(payload),
    }


def map_category(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": "gpexe",
        "provider_category_id": int(_required(payload, "id")),
        "category_name": canonical_session_category(str(_required(payload, "name"))),
        "team_id": payload.get("team"),
        "provider_color": payload.get("color"),
    }


def map_tag(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": "gpexe",
        "provider_tag_id": int(_required(payload, "id")),
        "tag_name": str(_required(payload, "name")).strip(),
        "team_id": payload.get("team"),
    }



def map_team_session(payload: Mapping[str, Any]) -> dict[str, Any]:
    session_id = int(_required(payload, "id"))
    category = payload.get("category")
    category_id = category.get("id") if isinstance(category, Mapping) else category
    category_name = canonical_session_category(
        category.get("name") if isinstance(category, Mapping) else category
    )
    duration = payload.get("duration")
    return {
        "provider": "gpexe",
        "provider_session_id": session_id,
        "team_id": payload.get("team"),
        "category_id": category_id if isinstance(category_id, (int, float)) else None,
        "session_name": canonical_session_category(
            str(payload.get("name") or category_name or payload.get("nature") or "").strip()
        ) or f"GPExe Session {session_id}",
        "notes": payload.get("notes"),
        "start_timestamp": payload.get("startTimestamp") or payload.get("start_timestamp"),
        "end_timestamp": payload.get("end_timestamp"),
        "total_time": duration if duration is not None else payload.get("total_time"),
        "is_stats_valid": bool(payload.get("is_stats_valid", False)),
        "drill_enabled": bool(payload.get("drillEnabled", payload.get("drill_enabled", False))),
        "state": payload.get("state"),
        "submitted_by": payload.get("submitted_by"),
        "created_at": payload.get("created_on"),
        "updated_at": payload.get("updated_on"),
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
        "athlete_count": payload.get("athleteCount"),
        "match_cycle": payload.get("matchCycle"),
        "drill": payload.get("drill"),
        "drill_count": payload.get("drillCount"),
        "raw": dict(payload),
    }

def parse_headers_table(table_data: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Converte gli array posizionali GPExe usando le intestazioni restituite.

    Non assume indici fissi: l'ordine può cambiare in base all'export template.
    """
    headers = table_data.get("headers")
    rows = table_data.get("athlete_sessions")
    if not isinstance(headers, list) or not isinstance(rows, list):
        raise MappingError("table_data GPExe privo di headers o athlete_sessions.")

    labels: list[str] = []
    for header in headers:
        if not isinstance(header, Mapping):
            raise MappingError("Header GPExe non valido.")
        label = str(header.get("label") or header.get("name") or "").strip()
        if not label:
            raise MappingError("Header GPExe senza label.")
        labels.append(label)

    normalized: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        values = row.get("values")
        if not isinstance(values, list):
            continue
        metrics = {label: values[index] if index < len(values) else None for index, label in enumerate(labels)}
        athlete = row.get("athlete") if isinstance(row.get("athlete"), Mapping) else {}
        normalized.append(
            {
                "provider_athlete_session_id": row.get("id"),
                "athlete": dict(athlete),
                "metrics": metrics,
                "state": row.get("state"),
            }
        )
    return normalized



def map_team_session_detail(payload: Mapping[str, Any], *, provider_session_id: int) -> dict[str, Any]:
    """Normalizza il dettaglio Team Session mantenendo header dinamici e righe atleta."""
    if not isinstance(payload, Mapping):
        raise MappingError("Dettaglio Team Session GPExe non valido.")
    general = payload.get("general") if isinstance(payload.get("general"), Mapping) else {}
    header = payload.get("header") if isinstance(payload.get("header"), Mapping) else {}
    table_data = payload.get("table_data") if isinstance(payload.get("table_data"), Mapping) else {}
    timing = payload.get("timing") if isinstance(payload.get("timing"), Mapping) else {}
    status = payload.get("status") if isinstance(payload.get("status"), Mapping) else {}
    counts = payload.get("counts") if isinstance(payload.get("counts"), Mapping) else {}
    category = payload.get("category") if isinstance(payload.get("category"), Mapping) else {}
    drill = payload.get("drill") if isinstance(payload.get("drill"), Mapping) else {}

    headers = table_data.get("headers") if isinstance(table_data.get("headers"), list) else []
    normalized_headers = []
    for index, item in enumerate(headers):
        if not isinstance(item, Mapping):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        if not label:
            continue
        normalized_headers.append({
            "position": index,
            "label": label,
            "unit": item.get("unit"),
            "raw": dict(item),
        })

    athlete_rows = parse_headers_table(table_data) if headers else []
    return {
        "provider": "gpexe",
        "provider_session_id": int(provider_session_id),
        "provider_general_id": general.get("id"),
        "team_id": general.get("team") or header.get("team"),
        "nature": general.get("nature"),
        "start_timestamp": header.get("start_timestamp") or timing.get("start_timestamp"),
        "category_id": category.get("id") or header.get("category_id"),
        "category_name": category.get("name") or header.get("category"),
        "athlete_count": header.get("athletes"),
        "total_time": header.get("total_time") or timing.get("total_time"),
        "notes": header.get("notes"),
        "weather": header.get("weather"),
        "match": header.get("match"),
        "cycle": header.get("cycle"),
        "tags": header.get("tags") if isinstance(header.get("tags"), list) else [],
        "drills": header.get("drills") if isinstance(header.get("drills"), list) else [],
        "drill": dict(drill),
        "timing": dict(timing),
        "status": dict(status),
        "counts": dict(counts),
        "headers": normalized_headers,
        "athlete_rows": athlete_rows,
        "raw": dict(payload),
    }


def _scalar_metrics(payload: Mapping[str, Any], excluded: set[str]) -> dict[str, Any]:
    """Estrae metriche scalari mantenendo fuori metadati e strutture complesse."""
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if key in excluded or isinstance(value, Mapping):
            continue
        if isinstance(value, list):
            continue
        result[str(key)] = value
    return result


def map_athlete_session_detail(
    payload: Mapping[str, Any],
    *,
    provider_athlete_session_id: int,
    provider_session_id: int | None = None,
) -> dict[str, Any]:
    """Normalizza il dettaglio atleta-sessione conservando tutte le metriche grezze.

    GPExe può estendere il payload con nuove metriche; per questo il mapping salva
    sia un dizionario di metriche scalari sia il JSON completo del provider.
    """
    if not isinstance(payload, Mapping):
        raise MappingError("Dettaglio Athlete Session GPExe non valido.")
    athlete = payload.get("athlete") if isinstance(payload.get("athlete"), Mapping) else {}
    timing = payload.get("timing") if isinstance(payload.get("timing"), Mapping) else {}
    status = payload.get("status") if isinstance(payload.get("status"), Mapping) else {}
    excluded = {
        "id", "athlete", "session", "team_session", "teamsession", "drill", "track",
        "timing", "status", "created_on", "updated_on", "state", "starter",
        "is_stats_valid", "need_reprocess",
    }
    metrics = _scalar_metrics(payload, excluded)
    zones = {
        str(key): value for key, value in payload.items()
        if isinstance(value, list) and (str(key).endswith("_zones") or str(key).endswith("_events"))
    }
    athlete_id = athlete.get("id") or payload.get("athlete_id")
    linked_session = (
        provider_session_id
        if provider_session_id is not None
        else payload.get("team_session") or payload.get("teamsession") or payload.get("session")
    )
    total_time = payload.get("totalTime")
    total_time_value = total_time.get("value") if isinstance(total_time, Mapping) else None
    return {
        "provider": "gpexe",
        "provider_athlete_session_id": int(provider_athlete_session_id),
        "provider_session_id": int(linked_session) if linked_session not in (None, "") else None,
        "provider_player_id": int(athlete_id) if athlete_id not in (None, "") else None,
        "drill_id": payload.get("drill"),
        "track_id": payload.get("track"),
        "start_timestamp": payload.get("start_timestamp") or timing.get("start_timestamp"),
        "end_timestamp": payload.get("end_timestamp") or timing.get("end_timestamp"),
        "duration": (
            payload.get("duration") or payload.get("total_time")
            or total_time_value or timing.get("duration")
        ),
        "state": payload.get("state") or status.get("state"),
        "starter": payload.get("starter"),
        "is_stats_valid": payload.get("is_stats_valid", status.get("is_stats_valid")),
        "need_reprocess": payload.get("need_reprocess", status.get("need_reprocess")),
        "updated_at": payload.get("updated_on") or timing.get("updated_on"),
        "metrics": metrics,
        "zones": zones,
        "athlete": dict(athlete),
        "raw": dict(payload),
    }

def parse_iso_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise MappingError(f"Timestamp GPExe non valido: {value!r}") from exc


def map_many(items: Iterable[Mapping[str, Any]], mapper) -> list[dict[str, Any]]:
    return [mapper(item) for item in items]
