"""Piano e prima sincronizzazione anagrafica GPExe -> snapshot PAS."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping

from .client import GPExeClient
from .endpoints import ATHLETES, SESSION_CATEGORIES, SESSION_TAGS, TEAMS, TEAM_SESSIONS, Endpoint
from .mapper import map_athlete, map_category, map_many, map_tag, map_team, map_team_session


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
