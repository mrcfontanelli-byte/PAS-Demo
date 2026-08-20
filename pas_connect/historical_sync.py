"""Foundation resumable per lo storico GPExe, senza bulk executor."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence

from .database import PASConnectDatabase
from .mapper import map_many, map_team, map_team_session
from .rest_client import GPExeRESTClient, RESTProcessingResponse
from .rest_service import GPExeRESTService
from .sync import (
    RESTIdentitySyncResult, SessionSyncResult, SyncRequest,
    run_rest_identity_sync, run_rest_sync,
)
from .endpoints import TEAM_SESSIONS

REST_RATE_LIMIT_PER_MINUTE = 40
TEAM_SESSION_LIST_PAGE_SIZE = 500
SESSION_CONCURRENCY = 1


class HistoricalSyncAction(str, Enum):
    SKIP_COMPLETE = "SKIP_COMPLETE"
    COMPLETE_PARTIAL = "COMPLETE_PARTIAL"
    FETCH_NEW = "FETCH_NEW"
    DEFER_202 = "DEFER_202"
    RETRY_ERROR_ELIGIBLE = "RETRY_ERROR_ELIGIBLE"


@dataclass(frozen=True)
class HistoricalSyncPlanItem:
    team_id: int
    season: str
    team_session_id: int
    session_date: str
    action: HistoricalSyncAction
    last_attempt_at: str = ""


@dataclass(frozen=True)
class HistoricalCatalogResult:
    pages_fetched: int
    unique_remote_sessions: int
    counts_by_team: Mapping[int, int]
    inserted: int
    updated: int


@dataclass(frozen=True)
class HistoricalBatchAttempt:
    plan: HistoricalSyncPlanItem
    result: SessionSyncResult


@dataclass(frozen=True)
class HistoricalBatchResult:
    attempts: tuple[HistoricalBatchAttempt, ...]
    identity_state: RESTIdentitySyncResult


def persist_rest_team_references(
    client: GPExeRESTClient,
    database: PASConnectDatabase,
    *,
    target_contexts: Iterable[tuple[int, str]] | None = None,
) -> list[dict[str, Any]]:
    """Una sola roster Team REST; nessuna TeamSession o metrica viene richiesta."""
    payload = client.teams()
    if isinstance(payload, RESTProcessingResponse):
        return []
    if not isinstance(payload, list):
        raise ValueError("Team roster REST deve essere una lista diretta.")
    mapped = map_many(payload, map_team)
    targets = {
        (int(team_id), str(season).replace("-", "/"))
        for team_id, season in (target_contexts or ())
    }
    selected = [
        row for row in mapped
        if not targets or (
            int(row["provider_team_id"]), str(row.get("season") or "").replace("-", "/")
        ) in targets
    ]
    database.upsert_team_references(selected)
    return selected


def sync_historical_team_session_catalog(
    client: GPExeRESTClient,
    database: PASConnectDatabase,
    *,
    contexts: Mapping[int, str],
    expected_counts: Mapping[int, int] | None = None,
    max_pages: int = 100,
) -> HistoricalCatalogResult:
    """Scansiona e persiste solo metadata TeamSession, con checkpoint per pagina."""
    normalized_contexts = {int(key): str(value) for key, value in contexts.items()}
    expected = {int(key): int(value) for key, value in dict(expected_counts or {}).items()}
    seen: set[int] = set()
    counts = {team_id: 0 for team_id in normalized_contexts}
    inserted = updated = pages_fetched = 0
    for page in range(1, max_pages + 1):
        payload = client._request(
            TEAM_SESSIONS,
            query={
                "page": page,
                "page_size": TEAM_SESSION_LIST_PAGE_SIZE,
                "limit": TEAM_SESSION_LIST_PAGE_SIZE,
            },
        )
        if isinstance(payload, RESTProcessingResponse):
            break
        if isinstance(payload, list):
            raw_rows = payload
        elif isinstance(payload, Mapping):
            raw_rows = next(
                (payload[key] for key in ("results", "data", "items")
                 if isinstance(payload.get(key), list)),
                [],
            )
        else:
            raw_rows = []
        pages_fetched += 1
        page_rows: dict[int, list[dict[str, Any]]] = {
            team_id: [] for team_id in normalized_contexts
        }
        for raw in raw_rows:
            if not isinstance(raw, Mapping) or raw.get("id") in (None, ""):
                continue
            session_id = int(raw["id"])
            if session_id in seen:
                continue
            seen.add(session_id)
            team_value = raw.get("team")
            team_value = team_value.get("id") if isinstance(team_value, Mapping) else team_value
            if team_value in (None, ""):
                continue
            team_id = int(team_value)
            if team_id not in normalized_contexts:
                continue
            mapped = map_team_session(raw)
            mapped["team_id"] = team_id
            page_rows[team_id].append(mapped)
            counts[team_id] += 1
        for team_id, rows in page_rows.items():
            if not rows:
                continue
            outcome = database.upsert_historical_session_catalog(
                team_id=team_id,
                season=normalized_contexts[team_id],
                sessions=rows,
                page=page,
            )
            inserted += outcome["inserted"]
            updated += outcome["updated"]
        if expected and all(counts.get(team_id, 0) >= total for team_id, total in expected.items()):
            break
        if not raw_rows:
            break
    if expected and counts != expected:
        raise RuntimeError(f"Catalogo TeamSession incompleto: {counts} != {expected}")
    return HistoricalCatalogResult(
        pages_fetched=pages_fetched,
        unique_remote_sessions=sum(counts.values()),
        counts_by_team=counts,
        inserted=inserted,
        updated=updated,
    )


def plan_historical_sync(
    inventory: Iterable[Mapping[str, Any]],
) -> tuple[HistoricalSyncPlanItem, ...]:
    """Piano deterministico e idempotente; non contiene alcun fetch executor."""
    items: list[HistoricalSyncPlanItem] = []
    for row in inventory:
        if bool(row.get("performance_usable")):
            action = HistoricalSyncAction.SKIP_COMPLETE
        elif bool(row.get("deferred_202")):
            action = HistoricalSyncAction.DEFER_202
        elif str(row.get("sync_status") or "").upper() == "FAILED":
            action = HistoricalSyncAction.RETRY_ERROR_ELIGIBLE
        elif (str(row.get("sync_status") or "").upper() == "PARTIAL"
              or bool(row.get("locally_present"))):
            action = HistoricalSyncAction.COMPLETE_PARTIAL
        else:
            action = HistoricalSyncAction.FETCH_NEW
        items.append(HistoricalSyncPlanItem(
            team_id=int(row["team_id"]),
            season=str(row["season"]),
            team_session_id=int(row["team_session_id"]),
            session_date=str(row.get("session_date") or ""),
            action=action,
            last_attempt_at=str(row.get("last_attempt_at") or row.get("last_attempt") or ""),
        ))
    return tuple(sorted(items, key=lambda item: (item.session_date, item.team_session_id)))


_BATCH_PRIORITY = {
    HistoricalSyncAction.DEFER_202: 0,
    HistoricalSyncAction.COMPLETE_PARTIAL: 1,
    HistoricalSyncAction.RETRY_ERROR_ELIGIBLE: 2,
    HistoricalSyncAction.FETCH_NEW: 3,
}


def select_historical_batch(
    plans_by_context: Mapping[tuple[int, str], Sequence[HistoricalSyncPlanItem]],
    *,
    context_order: Sequence[tuple[int, str]],
    per_context_limit: int = 25,
    total_limit: int = 50,
) -> tuple[HistoricalSyncPlanItem, ...]:
    """Seleziona un batch esplicito; contesti non elencati non vengono toccati."""
    if per_context_limit < 1 or total_limit < 1:
        raise ValueError("I budget historical sync devono essere positivi.")
    selected: list[HistoricalSyncPlanItem] = []
    for raw_context in context_order:
        context = (int(raw_context[0]), str(raw_context[1]))
        eligible = [
            item for item in plans_by_context.get(context, ())
            if item.action in _BATCH_PRIORITY
        ]
        eligible.sort(key=lambda item: (
            _BATCH_PRIORITY[item.action], item.last_attempt_at,
            item.session_date, item.team_session_id,
        ))
        available = total_limit - len(selected)
        if available <= 0:
            break
        selected.extend(eligible[:min(per_context_limit, available)])
    return tuple(selected)


def run_historical_performance_batch(
    service: GPExeRESTService,
    database: PASConnectDatabase,
    plans: Sequence[HistoricalSyncPlanItem],
) -> HistoricalBatchResult:
    """Esegue serialmente un batch preselezionato con una sola identity roster."""
    identity_state = run_rest_identity_sync(service.client, database, set())
    attempts: list[HistoricalBatchAttempt] = []
    seen: set[tuple[int, str, int]] = set()
    for item in plans:
        key = (item.team_id, item.season, item.team_session_id)
        if key in seen or item.action is HistoricalSyncAction.SKIP_COMPLETE:
            continue
        seen.add(key)
        result = run_rest_sync(
            service,
            database,
            SyncRequest(
                team_id=item.team_id,
                season=item.season,
                selected_session_ids=(item.team_session_id,),
                force_refresh=item.action is not HistoricalSyncAction.FETCH_NEW,
                transport="REST",
            ),
            identity_state=identity_state,
        )
        attempts.append(HistoricalBatchAttempt(item, result.sessions[0]))
    return HistoricalBatchResult(tuple(attempts), identity_state)


def speed_profile_state(
    database: PASConnectDatabase,
    *,
    team_id: int,
    season: str,
) -> str:
    """Resta UNKNOWN finché il contesto non possiede zone REST verificate."""
    with database.connect() as connection:
        row = connection.execute(
            """SELECT 1 FROM gpexe_team_sessions s
            JOIN gpexe_athlete_session_details d
              ON d.provider_session_id=s.provider_session_id
            JOIN gpexe_athlete_session_kpis k
              ON k.provider_athlete_session_id=d.provider_athlete_session_id
            JOIN gpexe_athlete_team_memberships m
              ON m.provider_player_id=d.provider_player_id
             AND m.team_id=s.team_id AND m.season=?
            WHERE s.team_id=? AND k.source='rest_v2_speed_zone'
            LIMIT 1""",
            (str(season), int(team_id)),
        ).fetchone()
    return "VERIFIED" if row is not None else "UNKNOWN"
