"""Data Provider GPExe API separato dal provider Excel del PAS Core."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, MutableMapping
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
