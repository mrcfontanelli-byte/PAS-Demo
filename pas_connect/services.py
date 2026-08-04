"""Servizi applicativi tipizzati per le risorse GPExe Foundation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

from .client import GPExeClient
from .exceptions import APIRequestError

TEAM_SELECTOR_QUERY = """
query TeamSelector($sort: String, $active: Boolean, $offset: Int, $pageSize: Int, $after: String) {
  teams(sort: $sort, active: $active, offset: $offset, pageSize: $pageSize, after: $after) {
    id name season sport limitedClub { name } startDate
  }
}
"""

GET_TEAM_SESSIONS_QUERY = """
query GetTeamSessions($teamId: ID!, $startDate: Date!, $endDate: Date!, $offset: Int, $pageSize: Int, $after: String) {
  teamSessions(teamId: $teamId, startDate: $startDate, endDate: $endDate, offset: $offset, pageSize: $pageSize, after: $after) {
    id category startTimestamp duration athleteCount matchCycle nature tags notes
    state drill drillEnabled drillCount
  }
}
"""


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items", "objects"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, Mapping)]
        edges = payload.get("edges")
        if isinstance(edges, list):
            return [dict(edge["node"]) for edge in edges if isinstance(edge, Mapping) and isinstance(edge.get("node"), Mapping)]
    return []


def _page_state(payload: Any, received: int) -> tuple[bool, dict[str, object]]:
    """Restituisce se esiste un'altra pagina e le variabili per richiederla."""
    if not isinstance(payload, Mapping):
        return False, {}
    page_info = payload.get("pageInfo")
    if isinstance(page_info, Mapping):
        has_next = bool(page_info.get("hasNextPage"))
        cursor = page_info.get("endCursor")
        return has_next and cursor not in (None, ""), {"after": cursor} if has_next else {}
    count = payload.get("count")
    offset = payload.get("offset", 0)
    page_size = payload.get("pageSize", payload.get("limit", received))
    if isinstance(count, int) and isinstance(offset, int) and isinstance(page_size, int) and page_size > 0:
        next_offset = offset + page_size
        return next_offset < count, {"offset": next_offset, "pageSize": page_size}
    return False, {}


def _all_pages(
    client: GPExeClient, query: str, operation_name: str,
    variables: Mapping[str, object], root_field: str,
) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    seen: set[object] = set()
    page_variables = dict(variables)
    for _ in range(1000):
        response = client.graphql(
            query, variables=page_variables, operation_name=operation_name,
        )
        data = response.get("data")
        page = data.get(root_field) if isinstance(data, Mapping) else None
        rows = _items(page)
        for row in rows:
            identity = row.get("id")
            key: object = ("id", str(identity)) if identity not in (None, "") else ("row", repr(sorted(row.items())))
            if key not in seen:
                seen.add(key)
                collected.append(row)
        has_next, next_variables = _page_state(page, len(rows))
        if not has_next:
            return collected
        updated = {**page_variables, **next_variables}
        if updated == page_variables:
            return collected
        page_variables = updated
    raise APIRequestError(f"Paginazione GraphQL {operation_name} oltre il limite di sicurezza.")


@dataclass
class GPExeServices:
    client: GPExeClient

    def teams(self, **query: object) -> list[dict[str, Any]]:
        return _all_pages(
            self.client,
            TEAM_SELECTOR_QUERY,
            "TeamSelector",
            {"sort": "club__name,name,season", "active": True},
            "teams",
        )

    def team_sessions(
        self, *, team_id: object | None = None, start_date: object | None = None,
        end_date: object | None = None, **query: object,
    ) -> list[dict[str, Any]]:
        if team_id in (None, "") or start_date in (None, "") or end_date in (None, ""):
            raise APIRequestError("Team, data iniziale e data finale sono obbligatori.")
        return _all_pages(
            self.client,
            GET_TEAM_SESSIONS_QUERY,
            "GetTeamSessions",
            {"teamId": str(team_id), "startDate": str(start_date), "endDate": str(end_date)},
            "teamSessions",
        )

    def athletes(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Funzione disponibile in una release successiva.")

    def categories(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Categories da acquisire e verificare.")

    def tags(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Tags da acquisire e verificare.")

    def tracks(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Funzione disponibile in una release successiva.")
