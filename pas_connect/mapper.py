"""Prime trasformazioni provider -> schema canonico PAS."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Mapping

from .exceptions import MappingError


def _required(payload: Mapping[str, Any], key: str) -> Any:
    value = payload.get(key)
    if value is None:
        raise MappingError(f"Campo GPExe obbligatorio mancante: {key}")
    return value


def map_team(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": "gpexe",
        "provider_team_id": int(_required(payload, "id")),
        "team_name": str(_required(payload, "name")).strip(),
        "club_id": payload.get("club"),
        "season": payload.get("season"),
        "sport": payload.get("sport"),
        "start_date": payload.get("start_date"),
        "end_date": payload.get("end_date"),
        "locked": bool(payload.get("locked", False)),
        "updated_at": payload.get("updated_on"),
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


def map_category(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "provider": "gpexe",
        "provider_category_id": int(_required(payload, "id")),
        "category_name": str(_required(payload, "name")).strip(),
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
    return {
        "provider": "gpexe",
        "provider_session_id": session_id,
        "team_id": payload.get("team"),
        "category_id": payload.get("category"),
        "session_name": str(payload.get("name") or "").strip() or f"GPExe Session {session_id}",
        "notes": payload.get("notes"),
        "start_timestamp": payload.get("start_timestamp"),
        "end_timestamp": payload.get("end_timestamp"),
        "total_time": payload.get("total_time"),
        "is_stats_valid": bool(payload.get("is_stats_valid", False)),
        "drill_enabled": bool(payload.get("drill_enabled", False)),
        "state": payload.get("state"),
        "submitted_by": payload.get("submitted_by"),
        "created_at": payload.get("created_on"),
        "updated_at": payload.get("updated_on"),
        "tags": payload.get("tags") if isinstance(payload.get("tags"), list) else [],
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
