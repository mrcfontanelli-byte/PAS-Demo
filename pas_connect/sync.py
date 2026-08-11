"""Piano e prima sincronizzazione anagrafica GPExe -> snapshot PAS."""
from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import re
from typing import Any, Callable, Mapping

from .client import GPExeClient
from .endpoints import ATHLETES, SESSION_CATEGORIES, SESSION_TAGS, TEAMS, TEAM_SESSIONS, TEAM_SESSION_DETAIL, ATHLETE_SESSION_DETAIL, TRACKS, Endpoint
from .mapper import map_athlete, map_category, map_many, map_tag, map_team, map_team_session, map_team_session_detail, map_athlete_session_detail, map_graphql_athlete, map_graphql_athlete_session
from .services import GPExeServices
from .exceptions import APIRequestError


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


SYNC_MODES = {"MANUAL", "QUICK", "FROM_LAST_SESSION"}


@dataclass(frozen=True)
class SyncRequest:
    team_id: int
    season: str
    mode: str = "MANUAL"
    date_from: str | None = None
    date_to: str | None = None
    selected_session_ids: tuple[int, ...] = ()
    force_refresh: bool = False
    retry_of_run_id: int | None = None

    def validate(self) -> "SyncRequest":
        if int(self.team_id) <= 0:
            raise ValueError("Team ID obbligatorio e positivo.")
        if not str(self.season).strip():
            raise ValueError("Stagione obbligatoria.")
        if self.mode not in SYNC_MODES:
            raise ValueError(f"Modalità sync non valida: {self.mode}")
        if any(int(item) <= 0 for item in self.selected_session_ids):
            raise ValueError("Gli ID TeamSession devono essere interi positivi e non vuoti.")
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValueError("Intervallo date non valido.")
        if self.mode == "MANUAL" and not self.selected_session_ids and not (self.date_from and self.date_to):
            raise ValueError("MANUAL richiede un intervallo o TeamSession esplicite.")
        return self

    def resolved_dates(self, latest_date: str | None = None) -> tuple[str, str]:
        if self.date_from and self.date_to:
            return self.date_from, self.date_to
        today = date.today()
        if self.mode == "QUICK":
            return (today - timedelta(days=7)).isoformat(), today.isoformat()
        if self.mode == "FROM_LAST_SESSION" and latest_date:
            return latest_date[:10], today.isoformat()
        if self.selected_session_ids:
            return "1970-01-01", today.isoformat()
        raise ValueError("Impossibile risolvere l'intervallo di sincronizzazione.")


@dataclass(frozen=True)
class SessionSyncResult:
    provider_session_id: int
    status: str
    readiness: str
    athlete_sessions_count: int = 0
    tracks_count: int = 0
    kpis_count: int = 0
    error_message: str | None = None
    diagnostics: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class SyncRunResult:
    sync_run_id: int
    status: str
    sessions: tuple[SessionSyncResult, ...]

    @property
    def counts(self) -> dict[str, int]:
        return {name.lower() + "_count": sum(item.status == name for item in self.sessions)
                for name in ("SUCCESS", "PARTIAL", "FAILED", "SKIPPED")}


@dataclass(frozen=True)
class SyncProgressEvent:
    checkpoint: str
    provider_session_id: int | None
    detail: Mapping[str, Any]


def _redacted_trace_message(message: str) -> str:
    return re.sub(
        r"(?i)\b(authorization|cookie|set-cookie|token|password)\s*[:=]\s*[^\s;,]+",
        r"\1: [dato sensibile rimosso]", message,
    )


def _redacted_trace(
    target: list[dict[str, Any]], checkpoint: str, detail: Mapping[str, Any],
    *, session_id: int | None, progress: Callable[[SyncProgressEvent], None] | None,
) -> None:
    def redact(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {key: redact(item) for key, item in value.items()
                    if key.lower() not in {"authorization", "cookie", "token", "password"}}
        if isinstance(value, (list, tuple)):
            return [redact(item) for item in value]
        if isinstance(value, str):
            return re.sub(
                r"(?i)\b(authorization|cookie|set-cookie|token|password)\s*[:=]\s*[^\s;,]+",
                r"\1: [dato sensibile rimosso]", value,
            )
        return value

    safe = redact(detail)
    record = {"checkpoint": checkpoint, **safe}
    target.append(record)
    if progress:
        progress(SyncProgressEvent(checkpoint, session_id, safe))


def _is_kpi_resolver_error(error: Mapping[str, Any]) -> bool:
    path = error.get("path")
    return (
        isinstance(path, (list, tuple))
        and len(path) == 4
        and path[0] == "res"
        and path[1] == "athleteSessions"
        and isinstance(path[2], int)
        and path[3] in {"identifierKpi", "kpi"}
    )


def _kpi_only_graphql_errors(exc: BaseException) -> tuple[dict[str, Any], ...]:
    raw_errors = tuple(getattr(exc, "graphql_errors", ()))
    return tuple(dict(item) for item in raw_errors) if raw_errors and all(
        isinstance(item, Mapping) and _is_kpi_resolver_error(item) for item in raw_errors
    ) else ()


def run_graphql_sync(
    services: GPExeServices, database: "PASConnectDatabase", request: SyncRequest,
    *, progress: Callable[[SyncProgressEvent], None] | None = None,
) -> SyncRunResult:
    """Sincronizza bundle GPExe per TeamSession usando esclusivamente GraphQL."""
    from .database import PASConnectDatabase
    if not isinstance(database, PASConnectDatabase):
        raise TypeError("database deve essere un PASConnectDatabase")
    request.validate()
    date_from, date_to = request.resolved_dates(database.latest_team_session_updated_at())
    discovered = services.team_sessions(
        team_id=request.team_id, start_date=date_from, end_date=date_to,
    )
    selected = {int(item) for item in request.selected_session_ids}
    sessions = [item for item in discovered if not selected or int(item.get("id")) in selected]
    if selected - {int(item.get("id")) for item in sessions}:
        missing = sorted(selected - {int(item.get("id")) for item in sessions})
        raise ValueError(f"TeamSession non trovate nel contesto Team/date: {missing}")
    run_id = database.create_sync_run({
        "team_id": request.team_id, "season": request.season, "mode": request.mode,
        "date_from": date_from, "date_to": date_to, "requested_count": len(sessions),
        "retry_of_run_id": request.retry_of_run_id,
    })
    prior_ready = set(database.latest_ready_session_ids(team_id=request.team_id))
    results: list[SessionSyncResult] = []
    for raw_session in sessions:
        session_id = int(raw_session["id"])
        started_at = datetime.now(timezone.utc).isoformat()
        trace: list[dict[str, Any]] = []
        emit = lambda checkpoint, detail: _redacted_trace(
            trace, checkpoint, detail, session_id=session_id, progress=progress,
        )
        emit("C-01", {"selectedTeamSessionId": session_id, "pythonType": type(session_id).__name__})
        emit("C-02", {"providerTeamSessionId": session_id})
        if session_id in prior_ready and not request.force_refresh:
            result = SessionSyncResult(session_id, "SKIPPED", "READY", diagnostics=tuple(trace))
        else:
            try:
                kpi_provider_errors: tuple[dict[str, Any], ...] = ()
                try:
                    bundle = services.team_session_athlete_sessions(
                        team_session_id=session_id, trace=emit,
                    )
                except APIRequestError as exc:
                    kpi_provider_errors = _kpi_only_graphql_errors(exc)
                    if not kpi_provider_errors:
                        raise
                    emit("KPI-PROVIDER-ERROR", {
                        "status": "PARTIAL", "reason": "provider KPI error",
                        "graphqlErrors": list(kpi_provider_errors),
                    })
                    bundle = services.team_session_athlete_sessions_without_kpis(
                        team_session_id=session_id, trace=emit,
                    )
                raw_athlete_sessions = [
                    item for item in bundle.get("athleteSessions", []) if isinstance(item, Mapping)
                ]
                athletes_by_id: dict[int, Mapping[str, Any]] = {}
                for item in raw_athlete_sessions:
                    athlete = item.get("athlete") if isinstance(item.get("athlete"), Mapping) else None
                    if athlete and athlete.get("id") not in (None, ""):
                        athletes_by_id[int(athlete["id"])] = athlete
                mapped_parent = map_team_session({**raw_session, "team": request.team_id})
                mapped_athletes = [
                    map_graphql_athlete(item, team_id=request.team_id)
                    for item in athletes_by_id.values()
                ]
                mapped_sessions = [
                    map_graphql_athlete_session(item, team_session_id=session_id, template_id=None)
                    for item in raw_athlete_sessions
                ]
                tracks = sum(bool(item.get("track") and item["track"].get("id") not in (None, ""))
                             for item in mapped_sessions)
                kpis = sum(len(item.get("identifier_kpi") or []) + len(item.get("kpi") or [])
                           for item in mapped_sessions)
                structurally_complete = bool(mapped_sessions) and tracks == len(mapped_sessions)
                ready = structurally_complete and not kpi_provider_errors
                if ready:
                    database.upsert_graphql_team_session_bundle(
                        mapped_parent, mapped_athletes, mapped_sessions, season=request.season,
                    )
                elif structurally_complete and kpi_provider_errors:
                    database.upsert_graphql_team_session_bundle(
                        mapped_parent, mapped_athletes, mapped_sessions, replace_kpis=False,
                        season=request.season,
                    )
                status = "SUCCESS" if ready else "PARTIAL"
                provider_error = None
                if kpi_provider_errors:
                    messages = sorted({str(item.get("message") or "provider KPI error")
                                       for item in kpi_provider_errors})
                    provider_error = _redacted_trace_message(
                        "provider KPI error: " + "; ".join(messages)
                    )
                result = SessionSyncResult(
                    session_id, status, "READY" if ready else "INCOMPLETE",
                    len(mapped_sessions), tracks, 0 if kpi_provider_errors else kpis,
                    error_message=provider_error, diagnostics=tuple(trace),
                )
            except Exception as exc:
                safe_error = _redacted_trace_message(str(exc))
                result = SessionSyncResult(
                    session_id, "FAILED", "INCOMPLETE", error_message=safe_error, diagnostics=tuple(trace),
                )
        database.record_session_sync_result({
            "sync_run_id": run_id, "provider_session_id": session_id, "team_id": request.team_id,
            "status": result.status, "readiness": result.readiness,
            "athlete_sessions_count": result.athlete_sessions_count,
            "tracks_count": result.tracks_count, "kpis_count": result.kpis_count,
            "operation_name": "TeamSessionAthletesession", "variables": {"id": session_id},
            "diagnostics": list(result.diagnostics), "error_message": result.error_message,
            "started_at": started_at,
        })
        results.append(result)
    counts = {name.lower() + "_count": sum(item.status == name for item in results)
              for name in ("SUCCESS", "PARTIAL", "FAILED", "SKIPPED")}
    aggregate = "success" if results and not counts["failed_count"] and not counts["partial_count"] else (
        "partial" if counts["partial_count"] or counts["success_count"] or counts["skipped_count"] else "failed"
    )
    database.complete_sync_run(run_id, {"status": aggregate, **counts})
    return SyncRunResult(run_id, aggregate, tuple(results))


def retry_sync_session(
    services: GPExeServices, database: "PASConnectDatabase", request: SyncRequest,
    session_id: int, *, run_id: int,
) -> SyncRunResult:
    return run_graphql_sync(
        services, database,
        replace(request, selected_session_ids=(int(session_id),), force_refresh=True, retry_of_run_id=run_id),
    )


def retry_sync_errors(
    services: GPExeServices, database: "PASConnectDatabase", request: SyncRequest,
    *, run_id: int,
) -> SyncRunResult:
    session_ids = tuple(database.retryable_session_ids(run_id))
    if not session_ids:
        raise ValueError("Nessuna TeamSession FAILED/PARTIAL da ritentare.")
    return run_graphql_sync(
        services, database,
        replace(request, selected_session_ids=session_ids, force_refresh=True, retry_of_run_id=run_id),
    )


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


def sync_tracks(client: GPExeClient) -> dict[str, Any]:
    """Scarica i Tracks GPExe come risorsa separata, senza modificare Excel."""
    raw_tracks = fetch_all_pages(client, TRACKS)
    return {
        "schema_version": 5,
        "provider": "gpexe",
        "resource": "tracks",
        "synced_at": datetime.now(timezone.utc).isoformat(),
        "tracks": [dict(row) for row in raw_tracks],
        "count": len(raw_tracks),
    }

@dataclass(frozen=True)
class FullSyncEvent:
    step: str
    index: int
    total: int
    status: str
    message: str


def run_full_sync(
    client: GPExeClient | GPExeServices,
    database: "PASConnectDatabase",
    *,
    progress: Callable[[FullSyncEvent], None] | None = None,
    request: SyncRequest | None = None,
) -> SyncRunResult:
    """Entry point compatibile, ora esclusivamente GraphQL."""
    if request is None:
        raise ValueError("Il Full Sync GraphQL richiede Team, stagione e intervallo espliciti.")
    services = client if hasattr(client, "team_session_athlete_sessions") else GPExeServices(client)

    def bridge(event: SyncProgressEvent) -> None:
        if progress:
            progress(FullSyncEvent(
                event.checkpoint, 1, 1, "running",
                f"TeamSession {event.provider_session_id}: {dict(event.detail)}",
            ))

    return run_graphql_sync(services, database, request, progress=bridge)
