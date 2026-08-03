"""Piano e prima sincronizzazione anagrafica GPExe -> snapshot PAS."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping

from .client import GPExeClient
from .endpoints import ATHLETES, SESSION_CATEGORIES, SESSION_TAGS, TEAMS, TEAM_SESSIONS, TEAM_SESSION_DETAIL, ATHLETE_SESSION_DETAIL, Endpoint
from .mapper import map_athlete, map_category, map_many, map_tag, map_team, map_team_session, map_team_session_detail, map_athlete_session_detail


class SyncResource(str, Enum):
    TEAMS = "teams"
    CATEGORIES = "categories"
    TAGS = "tags"
    ATHLETES = "athletes"
    SESSIONS = "sessions"
    ATHLETE_SESSIONS = "athlete_sessions"
    TRACKS = "tracks"


@dataclass(frozen=True)
class SyncStep:
    order: int
    resource: SyncResource
    incremental: bool
    required_for_analysis: bool


@dataclass(frozen=True)
class SyncPlan:
    steps: tuple[SyncStep, ...]

    def validate(self) -> None:
        orders = [step.order for step in self.steps]
        if orders != sorted(orders) or len(orders) != len(set(orders)):
            raise ValueError("Ordine del piano di sincronizzazione non valido.")


def build_default_sync_plan() -> SyncPlan:
    plan = SyncPlan(
        steps=(
            SyncStep(1, SyncResource.TEAMS, True, True),
            SyncStep(2, SyncResource.CATEGORIES, False, True),
            SyncStep(3, SyncResource.TAGS, False, False),
            SyncStep(4, SyncResource.ATHLETES, False, True),
            SyncStep(5, SyncResource.SESSIONS, True, True),
            SyncStep(6, SyncResource.ATHLETE_SESSIONS, True, True),
            SyncStep(7, SyncResource.TRACKS, True, False),
        )
    )
    plan.validate()
    return plan


def _rows_from_response(payload: Any) -> tuple[list[Mapping[str, Any]], int | None]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, Mapping)], None
    if not isinstance(payload, Mapping):
        return [], None
    for key in ("results", "data", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            total = payload.get("count", payload.get("total", payload.get("total_count")))
            return [item for item in value if isinstance(item, Mapping)], int(total) if isinstance(total, (int, float)) else None
    return [], None


def fetch_all_pages(
    client: GPExeClient,
    endpoint: Endpoint,
    *,
    page_size: int = 100,
    max_pages: int = 1000,
    extra_query: Mapping[str, Any] | None = None,
) -> list[Mapping[str, Any]]:
    """Recupera endpoint lista, supportando sia array semplici sia risposte paginate."""
    collected: list[Mapping[str, Any]] = []
    for page in range(1, max_pages + 1):
        query = {"page": page, "page_size": page_size}
        if extra_query:
            query.update(dict(extra_query))
        payload = client.request(endpoint, query=query)
        rows, total = _rows_from_response(payload)
        collected.extend(rows)
        if isinstance(payload, list):
            break
        if not rows or len(rows) < page_size or (total is not None and len(collected) >= total):
            break
    else:  # pragma: no cover - guardia di sicurezza
        raise RuntimeError(f"Paginazione GPExe oltre {max_pages} pagine per {endpoint.path}.")
    return collected


def _fetch_non_paginated_or_paginated(client: GPExeClient, endpoint: Endpoint) -> list[Mapping[str, Any]]:
    payload = client.request(endpoint)
    rows, total = _rows_from_response(payload)
    if isinstance(payload, list):
        return rows
    if rows and (total is None or len(rows) >= total):
        return rows
    return fetch_all_pages(client, endpoint)


def sync_reference_data(client: GPExeClient) -> dict[str, Any]:
    """Sincronizza solo anagrafiche e classificazioni, senza toccare il DB Excel."""
    raw_teams = fetch_all_pages(client, TEAMS)
    raw_categories = _fetch_non_paginated_or_paginated(client, SESSION_CATEGORIES)
    raw_tags = _fetch_non_paginated_or_paginated(client, SESSION_TAGS)
    raw_athletes = fetch_all_pages(client, ATHLETES)

    snapshot = {
        "schema_version": 1,
        "provider": "gpexe",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "resources": {
            "teams": map_many(raw_teams, map_team),
            "categories": map_many(raw_categories, map_category),
            "tags": map_many(raw_tags, map_tag),
            "athletes": map_many(raw_athletes, map_athlete),
        },
    }
    snapshot["counts"] = {
        name: len(rows) for name, rows in snapshot["resources"].items()
    }
    return snapshot


def sync_team_sessions(client: GPExeClient, *, updated_since: str | None = None) -> dict[str, Any]:
    """Scarica le Team Sessions e le normalizza senza modificare il database Excel."""
    query: dict[str, Any] = {"limit": 999}
    if updated_since:
        query["updated_on_gte"] = updated_since
    raw_sessions = fetch_all_pages(
        client, TEAM_SESSIONS, page_size=999, extra_query=query
    )
    sessions = map_many(raw_sessions, map_team_session)
    synced_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 2,
        "provider": "gpexe",
        "resource": "team_sessions",
        "synced_at": synced_at,
        "updated_since": updated_since,
        "sessions": sessions,
        "count": len(sessions),
    }


def sync_team_session_details(
    client: GPExeClient,
    session_ids: list[int],
    *,
    all_params: bool = True,
    export_template: int | None = None,
) -> dict[str, Any]:
    """Scarica e normalizza il dettaglio delle Team Sessions indicate."""
    details: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for session_id in session_ids:
        query: dict[str, Any] = {"all_params": str(bool(all_params)).lower()}
        if export_template is not None:
            query["export_template"] = export_template
        try:
            payload = client.request(
                TEAM_SESSION_DETAIL,
                path_values={"id": int(session_id)},
                query=query,
            )
            details.append(map_team_session_detail(payload, provider_session_id=int(session_id)))
        except Exception as exc:
            errors.append({"provider_session_id": int(session_id), "error": str(exc)})
    return {
        "schema_version": 3,
        "provider": "gpexe",
        "resource": "team_session_details",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
        "errors": errors,
        "received": len(details),
        "failed": len(errors),
    }


def sync_athlete_session_details(
    client: GPExeClient,
    athlete_session_refs: list[tuple[int, int | None]],
) -> dict[str, Any]:
    """Scarica il dettaglio delle Athlete Sessions indicate.

    Ogni riferimento è ``(athlete_session_id, team_session_id)``; il secondo
    valore mantiene il collegamento anche quando il payload GPExe non lo espone.
    """
    details: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    for athlete_session_id, team_session_id in athlete_session_refs:
        try:
            payload = client.request(
                ATHLETE_SESSION_DETAIL,
                path_values={"id": int(athlete_session_id)},
            )
            details.append(
                map_athlete_session_detail(
                    payload,
                    provider_athlete_session_id=int(athlete_session_id),
                    provider_session_id=int(team_session_id) if team_session_id is not None else None,
                )
            )
        except Exception as exc:
            errors.append({
                "provider_athlete_session_id": int(athlete_session_id),
                "provider_session_id": int(team_session_id) if team_session_id is not None else None,
                "error": str(exc),
            })
    return {
        "schema_version": 4,
        "provider": "gpexe",
        "resource": "athlete_session_details",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "details": details,
        "errors": errors,
        "received": len(details),
        "failed": len(errors),
    }

@dataclass(frozen=True)
class FullSyncEvent:
    step: str
    index: int
    total: int
    status: str
    message: str


def run_full_sync(
    client: GPExeClient,
    database: "PASConnectDatabase",
    *,
    progress: Callable[[FullSyncEvent], None] | None = None,
) -> dict[str, Any]:
    """Esegue in sequenza la pipeline GPExe disponibile nella release.

    La pipeline comprende anagrafiche, Team Sessions, dettagli Team Sessions e
    Athlete Sessions. Ogni fase è persistita prima di passare alla successiva;
    un errore di singolo dettaglio resta isolato nei payload di sincronizzazione.
    """
    from .database import PASConnectDatabase
    if not isinstance(database, PASConnectDatabase):
        raise TypeError("database deve essere un PASConnectDatabase")

    steps = (
        "Anagrafiche",
        "Team Sessions",
        "Dettagli Team Sessions",
        "Athlete Sessions",
    )
    events: list[dict[str, Any]] = []

    def emit(index: int, status: str, message: str) -> None:
        event = FullSyncEvent(steps[index - 1], index, len(steps), status, message)
        events.append(event.__dict__.copy())
        if progress:
            progress(event)

    started_at = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {"started_at": started_at, "steps": {}, "events": events}

    emit(1, "running", "Sincronizzazione anagrafiche GPExe...")
    reference_payload = sync_reference_data(client)
    reference_result = database.replace_reference_data(reference_payload)
    result["steps"]["reference"] = {
        "counts": reference_result.counts,
        "sync_run_id": reference_result.sync_run_id,
    }
    emit(1, "success", "Anagrafiche sincronizzate.")

    emit(2, "running", "Sincronizzazione Team Sessions...")
    updated_since = database.latest_team_session_updated_at()
    sessions_payload = sync_team_sessions(client, updated_since=updated_since)
    sessions_result = database.upsert_team_sessions(sessions_payload)
    result["steps"]["team_sessions"] = {
        "received": sessions_result.received,
        "inserted": sessions_result.inserted,
        "updated": sessions_result.updated,
        "sync_run_id": sessions_result.sync_run_id,
    }
    emit(2, "success", "Team Sessions sincronizzate.")

    emit(3, "running", "Sincronizzazione dettagli Team Sessions...")
    session_ids = database.team_session_ids_for_detail_sync(only_missing=True)
    if session_ids:
        detail_payload = sync_team_session_details(client, session_ids)
        detail_result = database.upsert_team_session_details(detail_payload)
        detail_summary = {
            "requested": len(session_ids),
            "received": detail_result.received,
            "inserted": detail_result.inserted,
            "updated": detail_result.updated,
            "failed": detail_result.failed,
            "athlete_rows": detail_result.athlete_rows,
            "metric_headers": detail_result.metric_headers,
            "sync_run_id": detail_result.sync_run_id,
        }
    else:
        detail_summary = {"requested": 0, "received": 0, "inserted": 0, "updated": 0, "failed": 0}
    result["steps"]["team_session_details"] = detail_summary
    emit(3, "success", "Dettagli Team Sessions sincronizzati.")

    emit(4, "running", "Sincronizzazione Athlete Sessions...")
    athlete_refs = database.athlete_session_refs_for_detail_sync(only_missing=True)
    if athlete_refs:
        athlete_payload = sync_athlete_session_details(client, athlete_refs)
        athlete_result = database.upsert_athlete_session_details(athlete_payload)
        athlete_summary = {
            "requested": len(athlete_refs),
            "received": athlete_result.received,
            "inserted": athlete_result.inserted,
            "updated": athlete_result.updated,
            "failed": athlete_result.failed,
            "sync_run_id": athlete_result.sync_run_id,
        }
    else:
        athlete_summary = {"requested": 0, "received": 0, "inserted": 0, "updated": 0, "failed": 0}
    result["steps"]["athlete_sessions"] = athlete_summary
    emit(4, "success", "Athlete Sessions sincronizzate.")

    result["completed_at"] = datetime.now(timezone.utc).isoformat()
    result["status"] = "success"
    return result
