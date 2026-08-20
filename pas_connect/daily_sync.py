"""Daily Sync GPExe operativo, isolato dallo storico multi-season."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from enum import Enum
import json
from typing import Any, Callable, Iterable, Mapping, Sequence

from .dashboard_sessions import canonical_gpexe_dashboard_category
from .database import PASConnectDatabase
from .mapper import map_team_session
from .rest_client import GPExeRESTClient, RESTProcessingResponse
from .rest_service import GPExeRESTService
from .sync import (
    RESTIdentitySyncResult,
    SessionSyncResult,
    SyncRequest,
    run_rest_identity_sync,
    run_rest_sync,
)


DAILY_TEAM_ID = 543
DAILY_SEASON = "2026/2027"
WINDOW_DAYS = 4
MAX_DAILY_ATTEMPTS = 10
MAX_OUTSIDE_WINDOW_NEW = 1
TEAM_SESSION_PAGE_SIZE = 500
MAX_CATALOG_PAGES = 20


class DailySyncAction(str, Enum):
    FETCH_NEW = "FETCH_NEW"
    RETRY = "RETRY"
    FETCH_TECHNICAL = "FETCH_TECHNICAL"
    RETRY_DEFERRED = "RETRY_DEFERRED"
    FETCH_UNSEEN_OUTSIDE_WINDOW = "FETCH_UNSEEN_OUTSIDE_WINDOW"


@dataclass(frozen=True)
class DailySyncCandidate:
    team_id: int
    season: str
    team_session_id: int
    session_date: str
    description: str
    canonical_category: str | None
    action: DailySyncAction
    priority: int
    next_retry_at: datetime | None = None


@dataclass(frozen=True)
class DailySyncPlan:
    candidates: tuple[DailySyncCandidate, ...]
    discovered: int
    already_complete: int
    deferred_cooldown: int
    technical_not_prioritized: int


@dataclass(frozen=True)
class DailyCatalogResult:
    pages_fetched: int
    remote_team_sessions: int
    inserted: int
    updated: int


@dataclass(frozen=True)
class DailySyncAttempt:
    candidate: DailySyncCandidate
    result: SessionSyncResult


@dataclass(frozen=True)
class DailySyncResult:
    catalog: DailyCatalogResult
    plan: DailySyncPlan
    attempts: tuple[DailySyncAttempt, ...]
    identity_state: RESTIdentitySyncResult
    ready_published: int
    deferred_202: int
    errors: int
    next_retry_at: datetime | None

    @property
    def summary(self) -> Mapping[str, Any]:
        return {
            "new_found": self.catalog.inserted,
            "candidates": len(self.plan.candidates),
            "attempted": len(self.attempts),
            "ready_published": self.ready_published,
            "already_complete": self.plan.already_complete,
            "deferred_202": self.deferred_202,
            "errors": self.errors,
            "technical_not_prioritized": self.plan.technical_not_prioritized,
            "next_retry_at": (
                self.next_retry_at.isoformat() if self.next_retry_at is not None else None
            ),
        }


DailyProgress = Callable[[str, int, int, str], None]


def _utc_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def next_retry_at(
    last_attempt: datetime | str,
    processing_attempts: int,
    retry_after_seconds: float | int | None = None,
) -> datetime:
    """Calcola il primo retry ammesso per una TeamSession processing."""
    attempted_at = _utc_datetime(last_attempt)
    if retry_after_seconds is not None:
        try:
            seconds = float(retry_after_seconds)
        except (TypeError, ValueError):
            seconds = -1.0
        if seconds >= 0:
            return attempted_at + timedelta(seconds=seconds)
    attempt = max(1, int(processing_attempts))
    minutes = (15, 30, 60, 120)[min(attempt, 4) - 1]
    return attempted_at + timedelta(minutes=minutes)


def retry_is_mature(retry_at: datetime | None, now: datetime) -> bool:
    return retry_at is None or _utc_datetime(now) >= _utc_datetime(retry_at)


def _payload_rows(payload: object) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, Mapping)]
    return []


def refresh_daily_catalog(
    client: GPExeRESTClient,
    database: PASConnectDatabase,
    *,
    max_pages: int = MAX_CATALOG_PAGES,
) -> DailyCatalogResult:
    """Aggiorna metadata-only il catalogo Team 543 usando l'API pubblica REST.

    GPExe non espone qui un filtro Team/data verificato: le pagine account-level
    vengono quindi lette serialmente e filtrate localmente, con limite esplicito.
    """
    pages = inserted = updated = 0
    seen: set[int] = set()
    for page in range(1, int(max_pages) + 1):
        payload = client.team_sessions_page(page=page, page_size=TEAM_SESSION_PAGE_SIZE)
        if isinstance(payload, RESTProcessingResponse):
            break
        raw_rows = _payload_rows(payload)
        pages += 1
        mapped_rows: list[dict[str, Any]] = []
        for raw in raw_rows:
            raw_id = raw.get("id")
            team = raw.get("team")
            team = team.get("id") if isinstance(team, Mapping) else team
            if raw_id in (None, "") or team in (None, ""):
                continue
            session_id = int(raw_id)
            if int(team) != DAILY_TEAM_ID or session_id in seen:
                continue
            seen.add(session_id)
            mapped = map_team_session(raw)
            mapped["team_id"] = DAILY_TEAM_ID
            mapped_rows.append(mapped)
        if mapped_rows:
            outcome = database.upsert_historical_session_catalog(
                team_id=DAILY_TEAM_ID,
                season=DAILY_SEASON,
                sessions=mapped_rows,
                page=page,
            )
            inserted += int(outcome["inserted"])
            updated += int(outcome["updated"])
        if not raw_rows:
            break
    return DailyCatalogResult(pages, len(seen), inserted, updated)


def _processing_history(
    rows: Iterable[Mapping[str, Any]],
) -> dict[int, tuple[int, float | None]]:
    result: dict[int, tuple[int, float | None]] = {}
    for row in rows:
        if int(row.get("team_id") or 0) != DAILY_TEAM_ID:
            continue
        if str(row.get("sync_season") or "") != DAILY_SEASON:
            continue
        try:
            diagnostics = json.loads(str(row.get("diagnostics_json") or "[]"))
        except (TypeError, ValueError, json.JSONDecodeError):
            diagnostics = []
        processing = False
        retry_after: float | None = None
        for item in diagnostics if isinstance(diagnostics, list) else ():
            if not isinstance(item, Mapping):
                continue
            processing = processing or bool(item.get("processing")) or (
                int(item.get("http_status") or 0) == 202
            )
            if item.get("retry_after_seconds") not in (None, ""):
                try:
                    retry_after = float(item["retry_after_seconds"])
                except (TypeError, ValueError):
                    pass
        if not processing:
            continue
        session_id = int(row["provider_session_id"])
        count, latest_retry = result.get(session_id, (0, None))
        result[session_id] = (
            count + 1,
            retry_after if count == 0 and retry_after is not None else latest_retry,
        )
    return result


def _session_day(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except (TypeError, ValueError):
        return None


def plan_daily_sync(
    inventory: Sequence[Mapping[str, Any]],
    sync_history: Sequence[Mapping[str, Any]] = (),
    *,
    today: date | None = None,
    now: datetime | None = None,
    max_attempts: int = MAX_DAILY_ATTEMPTS,
) -> DailySyncPlan:
    """Costruisce un piano Daily deterministico e isolato dal backfill storico."""
    current_day = today or date.today()
    current_time = _utc_datetime(now or datetime.now(timezone.utc))
    window_start = current_day - timedelta(days=WINDOW_DAYS - 1)
    processing = _processing_history(sync_history)
    candidates: list[DailySyncCandidate] = []
    outside: list[DailySyncCandidate] = []
    complete = cooldown = technical = 0
    seen: set[int] = set()
    for row in inventory:
        if int(row.get("team_id") or 0) != DAILY_TEAM_ID or str(row.get("season")) != DAILY_SEASON:
            continue
        session_id = int(row["team_session_id"])
        if session_id in seen:
            continue
        seen.add(session_id)
        if bool(row.get("performance_usable")) or (
            str(row.get("readiness") or "").upper() == "READY"
            and str(row.get("sync_status") or "").upper() in {"SUCCESS", "SKIPPED"}
        ):
            complete += 1
            continue
        session_day = _session_day(row.get("session_date"))
        recent = session_day is not None and window_start <= session_day <= current_day
        description = str(row.get("description") or "").strip()
        category = canonical_gpexe_dashboard_category(description)
        deferred = bool(row.get("deferred_202"))
        retry_at = None
        if deferred:
            attempts, retry_after = processing.get(session_id, (1, None))
            if not row.get("last_attempt"):
                cooldown += 1
                continue
            retry_at = next_retry_at(row["last_attempt"], attempts, retry_after)
            if not retry_is_mature(retry_at, current_time):
                cooldown += 1
                continue
        status = str(row.get("sync_status") or "").upper()
        attempted = bool(status or row.get("last_attempt"))
        unseen_outside = (
            not recent and not attempted and not bool(row.get("locally_present"))
        )
        if unseen_outside:
            action, priority = DailySyncAction.FETCH_UNSEEN_OUTSIDE_WINDOW, 5
        elif deferred:
            action, priority = DailySyncAction.RETRY_DEFERRED, 4
        elif category and attempted:
            action, priority = DailySyncAction.RETRY, 2
        elif category == "Full Training":
            action, priority = DailySyncAction.FETCH_NEW, 0
        elif category:
            action, priority = DailySyncAction.FETCH_NEW, 1
        elif recent:
            action, priority = DailySyncAction.FETCH_TECHNICAL, 3
            technical += 1
        else:
            continue
        candidate = DailySyncCandidate(
            DAILY_TEAM_ID, DAILY_SEASON, session_id,
            str(row.get("session_date") or ""), description, category,
            action, priority, retry_at,
        )
        if recent:
            candidates.append(candidate)
        elif action is DailySyncAction.FETCH_UNSEEN_OUTSIDE_WINDOW:
            outside.append(candidate)
    def ordering(item: DailySyncCandidate) -> tuple[int, int, int]:
        session_day = _session_day(item.session_date)
        return (
            item.priority,
            -(session_day.toordinal() if session_day is not None else 0),
            -item.team_session_id,
        )
    candidates.sort(key=ordering)
    outside.sort(key=ordering)
    eligible = candidates + outside[:MAX_OUTSIDE_WINDOW_NEW]
    return DailySyncPlan(
        tuple(eligible[:max(0, min(int(max_attempts), MAX_DAILY_ATTEMPTS))]),
        len(seen), complete, cooldown, technical,
    )


def run_daily_sync(
    client: GPExeRESTClient,
    database: PASConnectDatabase,
    *,
    today: date | None = None,
    now: datetime | None = None,
    progress: DailyProgress | None = None,
    max_catalog_pages: int = MAX_CATALOG_PAGES,
) -> DailySyncResult:
    """Autentica, scopre, pianifica ed esegue il solo Daily Team 543/2026-2027."""
    if not isinstance(client, GPExeRESTClient):
        raise TypeError("Daily Sync richiede GPExeRESTClient.")
    if not isinstance(database, PASConnectDatabase):
        raise TypeError("database deve essere PASConnectDatabase.")
    emit = progress or (lambda stage, index, total, message: None)
    client.authenticate()
    emit("catalog", 0, 1, "Aggiornamento catalogo Team 543 / 2026/2027")
    catalog = refresh_daily_catalog(client, database, max_pages=max_catalog_pages)
    inventory = database.historical_session_inventory(
        team_id=DAILY_TEAM_ID, season=DAILY_SEASON,
    )
    history = database.list_session_sync_results(team_id=DAILY_TEAM_ID)
    plan = plan_daily_sync(inventory, history, today=today, now=now)
    emit("plan", 0, len(plan.candidates), f"{len(plan.candidates)} candidate Daily")
    identity_state = run_rest_identity_sync(client, database, set())
    attempts: list[DailySyncAttempt] = []
    attempted_ids: set[int] = set()
    for index, candidate in enumerate(plan.candidates, start=1):
        if candidate.team_id != DAILY_TEAM_ID or candidate.season != DAILY_SEASON:
            raise ValueError("Candidato fuori dal contesto Daily autorizzato.")
        if candidate.team_session_id in attempted_ids:
            continue
        attempted_ids.add(candidate.team_session_id)
        emit(
            "session", index, len(plan.candidates),
            f"TeamSession {candidate.team_session_id}",
        )
        result = run_rest_sync(
            GPExeRESTService(client),
            database,
            SyncRequest(
                DAILY_TEAM_ID, DAILY_SEASON, mode="QUICK",
                selected_session_ids=(candidate.team_session_id,),
                force_refresh=candidate.action in {
                    DailySyncAction.RETRY, DailySyncAction.RETRY_DEFERRED,
                },
                transport="REST",
            ),
            identity_state=identity_state,
        ).sessions[0]
        attempts.append(DailySyncAttempt(candidate, result))
    processing_attempts = [item for item in attempts if item.result.processing]
    retry_times: list[datetime] = []
    if processing_attempts:
        post_history = database.list_session_sync_results(team_id=DAILY_TEAM_ID)
        post_processing = _processing_history(post_history)
        post_inventory = {
            int(row["team_session_id"]): row
            for row in database.historical_session_inventory(
                team_id=DAILY_TEAM_ID, season=DAILY_SEASON,
            )
        }
        for attempt in processing_attempts:
            session_id = attempt.candidate.team_session_id
            count, retry_after = post_processing.get(session_id, (1, None))
            last_attempt = post_inventory.get(session_id, {}).get("last_attempt")
            retry_times.append(next_retry_at(
                last_attempt or now or datetime.now(timezone.utc), count, retry_after,
            ))
    return DailySyncResult(
        catalog, plan, tuple(attempts), identity_state,
        sum(item.result.status == "SUCCESS" and item.result.readiness == "READY"
            for item in attempts),
        plan.deferred_cooldown + len(processing_attempts),
        sum(item.result.status == "FAILED" for item in attempts),
        min(retry_times) if retry_times else None,
    )
