"""Data Provider GPExe API separato dal provider Excel del PAS Core."""
from __future__ import annotations
from dataclasses import dataclass
import re
from typing import Any, MutableMapping
from .exceptions import APIRequestError
from .services import GPExeServices

@dataclass
class GPExeAPIDataProvider:
    services: GPExeServices
    provider_id: str = "gpexe_api"
    display_name: str = "GPExe API"

    def test_connection(self) -> bool:
        return self.services.client.test_connection()

    def get_teams(self, active: bool | None = True) -> list[dict[str, Any]]:
        active_states = (True, False) if active is None else (active,)
        teams: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for active_state in active_states:
            for team in self.services.teams(active=active_state):
                team_id = team.get("id")
                key = str(team_id) if team_id not in (None, "") else repr(sorted(team.items()))
                if key not in seen_ids:
                    seen_ids.add(key)
                    teams.append(team)
        return teams

    def get_team_sessions(
        self, team_id: object | None = None, *, start_date: object | None = None,
        end_date: object | None = None,
    ) -> list[dict[str, Any]]:
        return self.services.team_sessions(
            team_id=team_id, start_date=start_date, end_date=end_date,
        )

    def get_athletes(
        self, team_id: object, *, club_id: object | None = None,
        tab: str | None = "CURRENT",
    ) -> list[dict[str, Any]]:
        tabs = ("CURRENT", "EXPIRED") if tab is None else (str(tab).upper(),)
        athletes: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        total_count = 0
        total_server_received = 0
        total_team_matched = 0
        for athlete_tab in tabs:
            for athlete in self.services.athletes(
                team_id=team_id, club_id=club_id, tab=athlete_tab,
            ):
                athlete_id = athlete.get("id")
                key = str(athlete_id) if athlete_id not in (None, "") else repr(sorted(athlete.items()))
                if key not in seen_ids:
                    seen_ids.add(key)
                    athletes.append(athlete)
            count = self.services.last_diagnostics.get("count")
            if isinstance(count, int):
                total_count += count
            total_server_received += int(self.services.last_diagnostics.get("serverReceived") or 0)
            total_team_matched += int(self.services.last_diagnostics.get("teamMatched") or 0)
        self.services.last_diagnostics.update(
            {
                "operationName": "Athletes", "received": len(athletes), "count": total_count,
                "serverReceived": total_server_received, "teamMatched": total_team_matched,
                "teamId": str(team_id),
            }
        )
        return athletes

    def get_team_session_athlete_sessions(self, team_session_id: object, **options: object) -> dict[str, Any]:
        return self.services.team_session_athlete_sessions(
            team_session_id=team_session_id, **options,
        )


TEAM_FILTER_DEPENDENT_STATE_KEYS = (
    "pas_gpexe_teams",
    "pas_gpexe_selected_team_index",
    "pas_gpexe_team_sessions",
    "pas_gpexe_session_selection",
)


def invalidate_team_filter_state(state: MutableMapping[str, Any]) -> None:
    """Invalida soltanto lo stato dipendente dal filtro Team."""
    for key in TEAM_FILTER_DEPENDENT_STATE_KEYS:
        state.pop(key, None)
    state.pop("pas_gpexe_athlete_scope", None)


def invalidate_athlete_filter_state(state: MutableMapping[str, Any]) -> None:
    """Invalida soltanto elenco e selezione Athletes."""
    state.pop("pas_gpexe_athletes", None)
    state.pop("pas_gpexe_athlete_selection", None)
    state.pop("pas_gpexe_athletes_loaded", None)
    state.pop("pas_gpexe_athletes_diagnostics", None)


def invalidate_athlete_session_state(state: MutableMapping[str, Any]) -> None:
    """Invalida soltanto recupero e import AthleteSession/KPI."""
    state.pop("pas_gpexe_athlete_session_results", None)
    state.pop("pas_gpexe_athlete_session_errors", None)
    state.pop("pas_gpexe_last_athlete_session_import", None)


def invalidate_athlete_context_state(state: MutableMapping[str, Any]) -> None:
    """Invalida Athletes e AthleteSessions quando cambia il contesto remoto."""
    invalidate_athlete_filter_state(state)
    invalidate_athlete_session_state(state)


def resolve_team_club_id(team: MutableMapping[str, Any], manual_club_id: object | None = None) -> str | None:
    """Risolve il Club ID senza hardcode, preferendo l'eventuale valore manuale."""
    manual = str(manual_club_id or "").strip()
    if manual:
        return manual
    club_id = team.get("clubId")
    limited_club = team.get("limitedClub")
    if club_id in (None, "") and isinstance(limited_club, MutableMapping):
        club_id = limited_club.get("id")
    normalized = str(club_id or "").strip()
    return normalized or None


def store_athlete_fetch_result(
    state: MutableMapping[str, Any], athletes: list[dict[str, Any]], diagnostics: MutableMapping[str, Any],
) -> None:
    """Conserva risultato e diagnostica Athletes attraverso i rerun Streamlit."""
    state["pas_gpexe_athletes"] = list(athletes)
    state["pas_gpexe_athletes_diagnostics"] = dict(diagnostics)
    state["pas_gpexe_athletes_loaded"] = True
    state.pop("pas_gpexe_athlete_selection", None)


def athletes_from_team_session_results(
    results: list[MutableMapping[str, Any]],
) -> list[dict[str, Any]]:
    """Ricostruisce la rosa effettiva e le presenze dalle TeamSession richieste."""
    athletes: dict[str, dict[str, Any]] = {}
    appearances: dict[str, set[str]] = {}
    for bundle in results:
        team_session_id = str(bundle.get("team_session_id") or "")
        result = bundle.get("result")
        athlete_sessions = result.get("athleteSessions") if isinstance(result, MutableMapping) else []
        for athlete_session in athlete_sessions or []:
            if not isinstance(athlete_session, MutableMapping):
                continue
            athlete = athlete_session.get("athlete")
            if not isinstance(athlete, MutableMapping) or athlete.get("id") in (None, ""):
                continue
            athlete_id = str(athlete["id"])
            athletes.setdefault(athlete_id, dict(athlete))
            appearances.setdefault(athlete_id, set()).add(team_session_id)
    return [
        {**athlete, "teamSessionAppearances": len(appearances[athlete_id])}
        for athlete_id, athlete in athletes.items()
    ]


def team_session_error_diagnostic(
    error: Exception,
    *,
    team_session_id: object,
    template_id: object | None,
    drill: object | None,
    fields_limit: object | None,
    secrets: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Crea diagnostica UI strutturata senza header o segreti."""
    message = str(error)
    for secret in secrets:
        if secret:
            message = message.replace(secret, "[dato sensibile rimosso]")
    message = re.sub(
        r"(?i)\b(authorization|cookie|set-cookie)\s*[:=]\s*[^\s;]+",
        r"\1: [dato sensibile rimosso]",
        message,
    )
    status_match = re.search(r"\bHTTP\s+(\d{3})\b", message, flags=re.IGNORECASE)
    graphql_errors = None
    graphql_match = re.search(
        r"(?:errori? GraphQL|Errore GraphQL GPExe)\s*:\s*(.+?)(?:\.$|$)",
        message,
        flags=re.IGNORECASE,
    )
    if graphql_match:
        graphql_errors = graphql_match.group(1).strip()
    from .services import normalize_team_session_athlete_session_variables

    try:
        variables = normalize_team_session_athlete_session_variables(
            team_session_id=team_session_id,
            template_id=template_id,
            drill=drill,
            fields_limit=fields_limit,
        )
    except APIRequestError:
        variables = {
            "id": None,
            "templateId": None,
            "drill": None,
        }
    return {
        "operationName": "TeamSessionAthletesession",
        "httpStatus": int(status_match.group(1)) if status_match else None,
        "graphqlErrors": graphql_errors,
        "message": message,
        "teamSessionId": variables.get("id"),
        "templateId": variables.get("templateId"),
        "drill": variables.get("drill"),
        "fieldsLimit": variables.get("fieldsLimit"),
        "variables": variables,
    }


TEAM_SESSION_DIAGNOSTIC_COLUMNS = (
    "operationName", "httpStatus", "graphqlErrors", "message",
    "teamSessionId", "templateId", "drill", "fieldsLimit", "variables",
)


def normalize_team_session_error_diagnostics(
    records: object,
) -> list[dict[str, Any]]:
    """Rende leggibili insieme record diagnostici storici e correnti."""
    normalized: list[dict[str, Any]] = []
    for record in records if isinstance(records, (list, tuple)) else []:
        if isinstance(record, MutableMapping):
            item = dict(record)
        else:
            item = {"message": str(record)}
        for column in TEAM_SESSION_DIAGNOSTIC_COLUMNS:
            item.setdefault(column, None)
        if item["variables"] is None:
            item["variables"] = {
                "id": item["teamSessionId"],
                "templateId": item["templateId"],
                "drill": item["drill"],
                **(
                    {"fieldsLimit": item["fieldsLimit"]}
                    if item["fieldsLimit"] not in (None, "") else {}
                ),
            }
        normalized.append(item)
    return normalized
