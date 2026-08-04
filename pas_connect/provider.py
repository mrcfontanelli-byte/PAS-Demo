"""Data Provider GPExe API separato dal provider Excel del PAS Core."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from .services import GPExeServices

@dataclass
class GPExeAPIDataProvider:
    services: GPExeServices
    provider_id: str = "gpexe_api"
    display_name: str = "GPExe API"

    def test_connection(self) -> bool:
        return self.services.client.test_connection()

    def get_teams(self) -> list[dict[str, Any]]:
        return self.services.teams(page=1, page_size=250)

    def get_team_sessions(
        self, team_id: object | None = None, *, start_date: object | None = None,
        end_date: object | None = None,
    ) -> list[dict[str, Any]]:
        return self.services.team_sessions(
            team_id=team_id, start_date=start_date, end_date=end_date,
        )
