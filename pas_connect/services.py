"""Servizi applicativi tipizzati per le risorse GPExe Foundation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

from .client import GPExeClient
from .endpoints import ATHLETES, SESSION_CATEGORIES, SESSION_TAGS, TEAM_SESSIONS, TEAMS, TRACKS
from .exceptions import APIRequestError

UNVERIFIED_QUERY_MESSAGE = "Query GraphQL Team/TeamSession da acquisire e verificare."


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(x) for x in payload if isinstance(x, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("results", "data", "items", "objects"):
            value = payload.get(key)
            if isinstance(value, list):
                return [dict(x) for x in value if isinstance(x, Mapping)]
    return []


@dataclass
class GPExeServices:
    client: GPExeClient

    def teams(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError(UNVERIFIED_QUERY_MESSAGE)

    def team_sessions(self, *, team_id: object | None = None, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError(UNVERIFIED_QUERY_MESSAGE)

    def athletes(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Athletes da acquisire e verificare.")

    def categories(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Categories da acquisire e verificare.")

    def tags(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Tags da acquisire e verificare.")

    def tracks(self, **query: object) -> list[dict[str, Any]]:
        raise APIRequestError("Query GraphQL Tracks da acquisire e verificare.")
