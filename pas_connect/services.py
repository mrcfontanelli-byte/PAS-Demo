"""Servizi applicativi tipizzati per le risorse GPExe Foundation."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Mapping

from .client import GPExeClient
from .endpoints import ATHLETES, SESSION_CATEGORIES, SESSION_TAGS, TEAM_SESSIONS, TEAMS, TRACKS


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
        return _items(self.client.request(TEAMS, query=query or None))

    def team_sessions(self, *, team_id: object | None = None, **query: object) -> list[dict[str, Any]]:
        params = dict(query)
        if team_id is not None:
            params.setdefault("team", team_id)
        return _items(self.client.request(TEAM_SESSIONS, query=params or None))

    def athletes(self, **query: object) -> list[dict[str, Any]]:
        return _items(self.client.request(ATHLETES, query=query or None))

    def categories(self, **query: object) -> list[dict[str, Any]]:
        return _items(self.client.request(SESSION_CATEGORIES, query=query or None))

    def tags(self, **query: object) -> list[dict[str, Any]]:
        return _items(self.client.request(SESSION_TAGS, query=query or None))

    def tracks(self, **query: object) -> list[dict[str, Any]]:
        return _items(self.client.request(TRACKS, query=query or None))
