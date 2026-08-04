"""Servizi applicativi GraphQL per le risorse GPExe verificate."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .client import GPExeClient
from .exceptions import APIRequestError


TEAM_SELECTOR_QUERY = """query TeamSelector(
  $clubId: ID
  $first: Int
  $skip: Int
  $sort: String
  $active: Boolean
) {
  res: teams(
    clubId: $clubId
    first: $first
    skip: $skip
    sort: $sort
    active: $active
  ) {
    content {
      id
      season
      limitedClub {
        name
        __typename
      }
      sport
      name
      startDate
      __typename
    }
    count
    offset
    pageSize
    __typename
  }
}"""


GET_TEAM_SESSIONS_QUERY = """fragment TeamSessionCategoryTypeFields on TeamSessionCategoryType {
  id
  createdOn
  updatedOn
  color
  occurrences
  isDeletable
  name
  __typename
}

query GetTeamSessions(
  $teamId: ID!
  $first: Int
  $skip: Int
  $startDate: Date
  $endDate: Date
  $sort: String
  $matchDistance: [Int]
  $matchCycle: [Int]
  $categoriesIds: [ID]
  $athleteIds: [ID]
  $types: [SessionType]
  $multipleFilters: String
) {
  res: teamSessions(
    teamId: $teamId
    first: $first
    skip: $skip
    startDate: $startDate
    endDate: $endDate
    sort: $sort
    matchDistance: $matchDistance
    matchCycle: $matchCycle
    categoriesIds: $categoriesIds
    athleteIds: $athleteIds
    types: $types
    multipleFilters: $multipleFilters
  ) {
    content {
      id
      category {
        ...TeamSessionCategoryTypeFields
        __typename
      }
      hasRpe
      totalTime {
        value
        uom
        unit
        __typename
      }
      startTimestamp
      drillEnabled
      drill
      originalTeamsession {
        id
        drill
        __typename
      }
      drillCount
      matchCycle
      nature
      tags {
        id
        name
        __typename
      }
      athleteCount
      notes
      duration
      rpeSet {
        id
        __typename
      }
      state
      __typename
    }
    count
    __typename
  }
}"""


def _all_pages(
    client: GPExeClient,
    graphql_query: str,
    operation_name: str,
    variables: Mapping[str, object],
    *,
    page_size: int,
    max_pages: int,
) -> list[dict[str, Any]]:
    """Recupera tutte le pagine GPExe mediante ``first`` e ``skip``."""
    if page_size <= 0:
        raise ValueError("La dimensione pagina GraphQL deve essere positiva.")
    collected: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    skip = 0
    for _ in range(max_pages):
        page_variables = {**variables, "first": page_size, "skip": skip}
        response = client.graphql(
            graphql_query,
            variables=page_variables,
            operation_name=operation_name,
        )
        data = response.get("data")
        result = data.get("res") if isinstance(data, Mapping) else None
        if not isinstance(result, Mapping):
            raise APIRequestError(f"La risposta GraphQL {operation_name} non contiene data.res.")
        content = result.get("content")
        if not isinstance(content, list):
            raise APIRequestError(f"La risposta GraphQL {operation_name} non contiene data.res.content.")
        rows = [dict(row) for row in content if isinstance(row, Mapping)]
        for row in rows:
            identity = row.get("id")
            key = str(identity) if identity not in (None, "") else repr(sorted(row.items()))
            if key not in seen_ids:
                seen_ids.add(key)
                collected.append(row)
        received = len(rows)
        if received == 0:
            return collected
        skip += received
        count = result.get("count")
        if isinstance(count, int) and skip >= count:
            return collected
        if not isinstance(count, int) and received < page_size:
            return collected
    raise APIRequestError(f"Paginazione GraphQL {operation_name} oltre il limite di sicurezza.")


@dataclass
class GPExeServices:
    client: GPExeClient
    page_size: int = 100
    max_pages: int = 1000

    def teams(self, *, active: bool = True, **query: object) -> list[dict[str, Any]]:
        return _all_pages(
            self.client,
            TEAM_SELECTOR_QUERY,
            "TeamSelector",
            {"sort": "club__name,name,season", "active": bool(active)},
            page_size=self.page_size,
            max_pages=self.max_pages,
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
            page_size=self.page_size,
            max_pages=self.max_pages,
        )

    def athletes(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Funzione disponibile in una release successiva.")

    def categories(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Categories da acquisire e verificare.")

    def tags(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Tags da acquisire e verificare.")

    def tracks(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Funzione disponibile in una release successiva.")
