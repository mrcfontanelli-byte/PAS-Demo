"""Classificazione offline delle TeamSession GPExe per la Dashboard PAS."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import sqlite3
from typing import Any, Iterable


CANONICAL_DASHBOARD_CATEGORIES = {
    "FULL TRAINING": "Full Training",
    "INDIVIDUAL TRAINING": "Individual Training",
    "RETURN TO PLAY": "Return to Play",
    "ACTIVE RECOVERY": "Active Recovery",
    "DIFFERENT TRAINING": "Different Training",
    "DIFFERENT TRANING": "Different Training",
    "MATCH": "Match",
    "RECOVERY": "Recovery",
}


def canonical_gpexe_dashboard_category(value: object) -> str | None:
    """Riconosce categorie canoniche o un token iniziale ``[CATEGORIA]``."""
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    if normalized.startswith("["):
        closing = normalized.find("]")
        if closing <= 1:
            return None
        normalized = normalized[1:closing]
    key = " ".join(normalized.upper().split())
    return CANONICAL_DASHBOARD_CATEGORIES.get(key)


@dataclass(frozen=True)
class DashboardSessionClassification:
    technical_level: str
    canonical_dashboard_category: str | None
    dashboard_eligible: bool
    exclusion_reason: str | None


def _payload(raw_json: object) -> dict[str, Any]:
    try:
        raw = json.loads(str(raw_json or "{}"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    payload = raw.get("payload", raw)
    return payload if isinstance(payload, dict) else {}


def classify_gpexe_team_session(
    session: dict[str, Any], athlete_sessions: Iterable[dict[str, Any]],
    *, structurally_referenced_by_child: bool = False,
) -> DashboardSessionClassification:
    """Classifica deterministicamente una TeamSession usando soli dati locali."""
    requested_id = int(session["provider_session_id"])
    rows = list(athlete_sessions)
    structural = []
    for row in rows:
        payload = _payload(row.get("raw_json"))
        linked = payload.get("teamsession", row.get("provider_session_id"))
        drill = payload.get("drill", row.get("drill_id"))
        structural.append((linked, drill))

    is_child = bool(structural) and all(
        linked not in (None, "") and int(linked) != requested_id
        and drill not in (None, "")
        for linked, drill in structural
    )
    is_self = bool(structural) and all(
        linked not in (None, "") and int(linked) == requested_id
        and drill in (None, "")
        for linked, drill in structural
    )
    category = canonical_gpexe_dashboard_category(session.get("session_name"))

    if is_child:
        return DashboardSessionClassification(
            "DRILL_CHILD", None, False,
            "AthleteSession collegata a un'altra TeamSession con drill valorizzato",
        )
    if structurally_referenced_by_child and (is_self or not structural):
        return DashboardSessionClassification(
            "EXERCISE_CONTAINER", None, False,
            "TeamSession contenitore referenziata da AthleteSession figlie/drill",
        )
    if is_self:
        if category is None:
            return DashboardSessionClassification(
                "MAIN_SESSION", None, False,
                "Categoria GPExe non mappata nella tassonomia Dashboard canonica",
            )
        return DashboardSessionClassification("MAIN_SESSION", category, True, None)
    return DashboardSessionClassification(
        "AMBIGUOUS", None, False,
        "Evidenza strutturale insufficiente o incoerente",
    )


def classify_local_dashboard_sessions(
    connection: sqlite3.Connection, sessions: Iterable[dict[str, Any]],
    *, team_id: int, season: str,
) -> list[dict[str, Any]]:
    """Classifica un insieme già READY/performance-usable, con membership scoped."""
    connection.row_factory = sqlite3.Row
    source = [dict(item) for item in sessions]
    requested_ids = {int(item["provider_session_id"]) for item in source}
    details_by_requested: dict[int, list[dict[str, Any]]] = {
        session_id: [] for session_id in requested_ids
    }
    referenced_containers: set[int] = set()
    rows = connection.execute(
        """SELECT d.provider_athlete_session_id,d.provider_session_id,d.drill_id,d.raw_json
           FROM gpexe_athlete_session_details d
           JOIN gpexe_athlete_team_memberships m
             ON m.provider_player_id=d.provider_player_id
            AND m.team_id=? AND m.season=?""",
        (int(team_id), str(season)),
    ).fetchall()
    for db_row in rows:
        row = dict(db_row)
        requested = int(row["provider_session_id"])
        if requested in details_by_requested:
            details_by_requested[requested].append(row)
        payload = _payload(row.get("raw_json"))
        linked = payload.get("teamsession")
        drill = payload.get("drill", row.get("drill_id"))
        if linked not in (None, "") and drill not in (None, ""):
            referenced_containers.add(int(linked))

    result = []
    for session in source:
        session_id = int(session["provider_session_id"])
        classification = classify_gpexe_team_session(
            session, details_by_requested[session_id],
            structurally_referenced_by_child=session_id in referenced_containers,
        )
        result.append({**session, **asdict(classification)})
    return result
