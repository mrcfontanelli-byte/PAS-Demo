"""Servizi applicativi GraphQL per le risorse GPExe verificate."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

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

ATHLETES_QUERY = """fragment DeviceTypeFields on DeviceType {
  id createdOn updatedOn deviceId serialId __typename
}

fragment AthleteTypeFields_with_deviceSet on AthleteType {
  id createdOn updatedOn lastName firstName name shortName birthdate thumbnail
  playerSet { id team { id __typename } number __typename }
  isDeletable hasTracks customId
  deviceSet { ...DeviceTypeFields __typename }
  isActive __typename
}

query Athletes(
  $teamId: ID
  $onDate: Date
  $clubId: ID
  $first: Int
  $skip: Int
  $sort: String
  $hasAthletesession: Boolean
  $tab: AthletesTabType
) {
  res: athletes(
    teamId: $teamId onDate: $onDate clubId: $clubId first: $first skip: $skip
    sort: $sort hasAthletesession: $hasAthletesession tab: $tab
  ) {
    content { ...AthleteTypeFields_with_deviceSet __typename }
    count offset pageSize __typename
  }
}"""

TEAM_SESSION_ATHLETESESSION_QUERY = """query TeamSessionAthletesession(
  $id: ID!
  $templateId: ID = null
  $drill: ID = null
  $fieldsLimit: Int
) {
  res: teamSession(id: $id, drill: $drill, templateId: $templateId, fieldsLimit: $fieldsLimit) {
    id drill team { id __typename }
    athleteSessions {
      id masterAthleteSession drill state isStatsValid starter
      track { id hasCardio athlete { id name lastName firstName __typename } __typename }
      totalTime { value uom unit __typename }
      athlete {
        id lastName firstName name shortName role
        playerSet { number team { id __typename } __typename }
        __typename
      }
      identifierKpi { name value group uom unit __typename }
      kpi { name value group uom unit __typename }
      __typename
    }
    __typename
  }
}"""

TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY = """query TeamSessionAthletesessionNoKpi(
  $id: ID!
  $templateId: ID = null
  $drill: ID = null
  $fieldsLimit: Int
) {
  res: teamSession(id: $id, drill: $drill, templateId: $templateId, fieldsLimit: $fieldsLimit) {
    id drill team { id __typename }
    athleteSessions {
      id masterAthleteSession drill state isStatsValid starter
      track { id hasCardio athlete { id name lastName firstName __typename } __typename }
      totalTime { value uom unit __typename }
      athlete {
        id lastName firstName name shortName role
        playerSet { number team { id __typename } __typename }
        __typename
      }
      __typename
    }
    __typename
  }
}"""


def normalize_team_session_athlete_session_variables(
    *,
    team_session_id: object,
    template_id: object | None = None,
    drill: object | None = None,
    fields_limit: object | None = None,
) -> dict[str, object]:
    """Normalizza i tipi scalari verificati nel traffico GraphQL GPExe."""
    if team_session_id is None or str(team_session_id).strip() == "":
        raise APIRequestError("TeamSession ID obbligatorio.")
    try:
        variables: dict[str, object] = {"id": int(str(team_session_id).strip())}
        variables["templateId"] = (
            None if template_id is None or str(template_id).strip() == ""
            else int(str(template_id).strip())
        )
        variables["drill"] = (
            None if drill is None or str(drill).strip() == ""
            else int(str(drill).strip())
        )
        if fields_limit is not None and str(fields_limit).strip() != "":
            variables["fieldsLimit"] = int(str(fields_limit).strip())
    except (TypeError, ValueError) as exc:
        raise APIRequestError(
            "I parametri TeamSessionAthletesession devono essere ID numerici interi."
        ) from exc
    return variables


def _all_pages(
    client: GPExeClient,
    graphql_query: str,
    operation_name: str,
    variables: Mapping[str, object],
    *,
    page_size: int,
    max_pages: int,
    diagnostics: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Recupera tutte le pagine GPExe mediante ``first`` e ``skip``."""
    if page_size <= 0:
        raise ValueError("La dimensione pagina GraphQL deve essere positiva.")
    collected: list[dict[str, Any]] = []
    if diagnostics is not None:
        diagnostics.clear()
        diagnostics.update({"operationName": operation_name, "received": 0, "count": None})
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
        count = result.get("count")
        if diagnostics is not None:
            diagnostics["received"] = len(collected)
            diagnostics["count"] = count
        if received == 0:
            return collected
        skip += received
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
    last_diagnostics: dict[str, Any] = field(init=False, default_factory=dict)

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

    def athletes(
        self, *, team_id: object | None = None, club_id: object | None = None,
        tab: str = "CURRENT", **query: object,
    ) -> list[dict[str, Any]]:
        if team_id in (None, ""):
            raise APIRequestError("Team obbligatorio per recuperare gli Athletes.")
        normalized_tab = str(tab).upper()
        if normalized_tab not in {"CURRENT", "EXPIRED"}:
            raise APIRequestError("Filtro Athletes non valido.")
        if normalized_tab == "EXPIRED" and club_id in (None, ""):
            raise APIRequestError("Club ID non disponibile per recuperare gli Athletes Expired.")
        variables: dict[str, object] = {
            "teamId": str(team_id), "sort": "last_name,first_name", "tab": normalized_tab,
        }
        if normalized_tab == "EXPIRED":
            variables["clubId"] = str(club_id)
        athletes = _all_pages(
            self.client, ATHLETES_QUERY, "Athletes", variables,
            page_size=min(self.page_size, 50), max_pages=self.max_pages,
            diagnostics=self.last_diagnostics,
        )
        server_received = len(athletes)
        if normalized_tab == "EXPIRED":
            selected_team_id = str(team_id)
            athletes = [
                athlete for athlete in athletes
                if any(
                    isinstance(membership, Mapping)
                    and isinstance(membership.get("team"), Mapping)
                    and str(membership["team"].get("id")) == selected_team_id
                    for membership in (
                        athlete.get("playerSet")
                        if isinstance(athlete.get("playerSet"), list)
                        else [athlete.get("playerSet")]
                    )
                )
            ]
        self.last_diagnostics.update({
            "serverReceived": server_received,
            "teamMatched": len(athletes),
            "teamId": str(team_id),
            "received": len(athletes),
        })
        return athletes

    def team_session_athlete_sessions(
        self, *, team_session_id: object, template_id: object | None = None,
        drill: object | None = None, fields_limit: object | None = None,
        trace: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        variables = normalize_team_session_athlete_session_variables(
            team_session_id=team_session_id,
            template_id=template_id,
            drill=drill,
            fields_limit=fields_limit,
        )
        if trace:
            trace("C-03", {"operationName": "TeamSessionAthletesession", "variables": variables})
            trace("C-04", {"operationName": "TeamSessionAthletesession", "variables": variables})
        try:
            response = self.client.graphql(
                TEAM_SESSION_ATHLETESESSION_QUERY,
                variables=variables,
                operation_name="TeamSessionAthletesession",
            )
        except Exception as exc:
            if trace:
                trace("C-05", {
                    "status": "ERROR", "errorType": type(exc).__name__, "message": str(exc),
                    "graphqlErrors": list(getattr(exc, "graphql_errors", ())),
                })
            raise
        data = response.get("data")
        result = data.get("res") if isinstance(data, Mapping) else None
        if not isinstance(result, Mapping):
            raise APIRequestError("La risposta TeamSessionAthletesession non contiene data.res.")
        if trace:
            trace("C-05", {"status": "SUCCESS", "hasDataRes": True})
        return dict(result)

    def team_session_athlete_sessions_without_kpis(
        self, *, team_session_id: object, template_id: object | None = None,
        drill: object | None = None, fields_limit: object | None = None,
        trace: Callable[[str, Mapping[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Recupera il bundle strutturale dopo un errore confinato ai resolver KPI."""
        variables = normalize_team_session_athlete_session_variables(
            team_session_id=team_session_id,
            template_id=template_id,
            drill=drill,
            fields_limit=fields_limit,
        )
        if trace:
            trace("C-04-KPI-FALLBACK", {
                "operationName": "TeamSessionAthletesessionNoKpi", "variables": variables,
            })
        try:
            response = self.client.graphql(
                TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY,
                variables=variables,
                operation_name="TeamSessionAthletesessionNoKpi",
            )
        except Exception as exc:
            if trace:
                trace("C-05-KPI-FALLBACK", {
                    "status": "ERROR", "errorType": type(exc).__name__, "message": str(exc),
                    "graphqlErrors": list(getattr(exc, "graphql_errors", ())),
                })
            raise
        data = response.get("data")
        result = data.get("res") if isinstance(data, Mapping) else None
        if not isinstance(result, Mapping):
            raise APIRequestError(
                "La risposta TeamSessionAthletesessionNoKpi non contiene data.res."
            )
        if trace:
            trace("C-05-KPI-FALLBACK", {"status": "SUCCESS", "hasDataRes": True})
        return dict(result)

    def categories(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Categories da acquisire e verificare.")

    def tags(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Tags da acquisire e verificare.")

    def tracks(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Funzione disponibile in una release successiva.")
