"""Catalogo centralizzato degli endpoint GPExe documentati."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Endpoint:
    method: str
    path: str

    def format(self, **values: object) -> str:
        return self.path.format(**values)


TEAMS = Endpoint("GET", "/rest/v2/team/")
TEAM_DETAIL = Endpoint("GET", "/rest/v2/team/{id}/")
ATHLETES = Endpoint("GET", "/rest/v2/athlete/")
ATHLETE_DETAIL = Endpoint("GET", "/rest/v2/athlete/{id}/")
SESSION_CATEGORIES = Endpoint("GET", "/rest/v2/session/category/")
SESSION_TAGS = Endpoint("GET", "/rest/v2/session/tags/")
TEAM_SESSIONS = Endpoint("GET", "/rest/v2/session/team/")
TEAM_SESSION_DETAIL = Endpoint("GET", "/rest/v2/session/team/{id}/")
TEAM_SESSION_ATHLETES = Endpoint(
    "GET", "/rest/v2/session/team/{id}/athlete_sessions/"
)
ATHLETE_SESSION_DETAIL = Endpoint("GET", "/rest/v2/session/athlete/{id}/")
TRACKS = Endpoint("GET", "/rest/v2/track/")
TRACK_DETAIL = Endpoint("GET", "/rest/v2/track/{id}/")

SYNC_ENDPOINTS = (
    TEAMS,
    SESSION_CATEGORIES,
    SESSION_TAGS,
    ATHLETES,
    TEAM_SESSIONS,
    TRACKS,
)
