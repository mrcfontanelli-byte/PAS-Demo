"""Gate di persistenza REST: pubblica soltanto bundle READY nello schema 12."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .database import PASConnectDatabase
from .rest_service import RESTBundleResult
from .rest_mapper import SPEED_ZONE_FAMILY

REST_KPI_SOURCE = "rest_v2"
APPROVED_CANONICAL_METRICS = {
    "Distance", "Duration", "Acc Events", "Dec Events", "Speed Events", "RPE", "Max Speed",
}


@dataclass(frozen=True)
class RESTPersistenceResult:
    published: bool
    status: str
    provider_session_id: int | None = None
    athlete_sessions_count: int = 0
    tracks_count: int = 0
    kpis_count: int = 0
    reason: str | None = None


@dataclass(frozen=True)
class RESTIdentityPersistenceResult:
    received: int
    inserted: int
    updated: int


class GPExeRESTIdentityPersistence:
    """Persistence identity-only, indipendente dalla readiness TeamSession."""

    def __init__(self, database: PASConnectDatabase) -> None:
        self.database = database

    def persist(
        self,
        identity_index: Mapping[int, Mapping[str, Any]],
    ) -> RESTIdentityPersistenceResult:
        inserted, updated = self.database.upsert_athlete_identities(
            identity_index,
            source="rest_v2",
        )
        return RESTIdentityPersistenceResult(len(identity_index), inserted, updated)


class GPExeRESTPersistenceGate:
    def __init__(self, database: PASConnectDatabase) -> None:
        self.database = database

    def publish(
        self,
        result: RESTBundleResult,
        *,
        season: str,
        identity_index: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> RESTPersistenceResult:
        if result.status != "READY" or result.processing or result.bundle is None:
            return RESTPersistenceResult(
                False, result.status,
                reason="Solo i bundle REST READY e non processing possono essere pubblicati.",
            )
        if not str(season).strip():
            raise ValueError("Stagione obbligatoria per la persistenza REST.")
        normalized_season = str(season).strip()
        parent, athletes, sessions = self._adapt_bundle(
            result.bundle,
            season=normalized_season,
            identity_index=identity_index,
        )
        session_count, track_count, kpi_count = self.database.upsert_team_session_bundle(
            parent, athletes, sessions, replace_kpis=True,
            replace_kpi_sources={REST_KPI_SOURCE, "rest_v2_speed_zone"},
            season=normalized_season,
        )
        return RESTPersistenceResult(
            True, "READY", int(parent["provider_session_id"]),
            session_count, track_count, kpi_count,
        )

    def _adapt_bundle(
        self,
        bundle: Mapping[str, Any],
        *,
        season: str | None = None,
        identity_index: Mapping[int, Mapping[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        if bundle.get("provider_contract") != "rest_v2":
            raise ValueError("Il gate accetta esclusivamente bundle REST v2.")
        team = bundle.get("team_session")
        if not isinstance(team, Mapping):
            raise ValueError("Bundle REST privo di TeamSession canonica.")
        category = team.get("category") if isinstance(team.get("category"), Mapping) else {}
        session_name = str(category.get("name") or team.get("nature") or "").strip()
        provider_session_id = int(team["provider_session_id"])
        bundle_provenance = str(bundle.get("provenance") or "rest_v2_aggregate")
        team_raw = dict(team.get("raw") or {})
        team_raw["pas_bundle_provenance"] = bundle_provenance
        parent = {
            "provider": "gpexe", "provider_contract": "rest_v2",
            "provider_session_id": provider_session_id, "team_id": int(team["team_id"]),
            "category_id": category.get("id"),
            "session_name": session_name or f"GPExe REST Session {provider_session_id}",
            "notes": None, "start_timestamp": team.get("start_timestamp"),
            "end_timestamp": team.get("end_timestamp"), "total_time": team.get("total_time"),
            "is_stats_valid": team.get("is_stats_valid"),
            "drill_enabled": (team.get("drill") or {}).get("enabled"),
            "state": "READY", "submitted_by": None, "created_at": None, "updated_at": None,
            "provenance": (
                "gpexe_rest_team_session_elementary"
                if bundle_provenance == "rest_v2_elementary"
                else "gpexe_rest_team_session_detail"
            ),
            "raw": team_raw,
        }
        athletes_by_id: dict[int, dict[str, Any]] = {}
        identities = identity_index or {}
        sessions: list[dict[str, Any]] = []
        for row in bundle.get("athlete_sessions") or ():
            athlete_id = int(row["athlete"]["provider_player_id"])
            track_id = str(row["track"]["provider_track_id"])
            identity = identities.get(athlete_id) or {}
            athletes_by_id.setdefault(athlete_id, {
                "provider_player_id": athlete_id,
                "first_name": identity.get("first_name"),
                "last_name": identity.get("last_name"),
                "short_name": identity.get("short_name"),
                "player_name": identity.get("player_name") or f"GPExe Athlete {athlete_id}",
                "team_id": int(team["team_id"]), "has_tracks": True,
                "provider_contract": "rest_v2",
                "identity_source": "rest_v2",
                "provenance": identity.get("provenance") or "gpexe_rest_athlete_reference",
                "raw": identity.get("raw") or {
                    "provider_player_id": athlete_id,
                    "provider_contract": "rest_v2",
                    "provenance": "gpexe_rest_athlete_reference",
                },
            })
            provider_kpis = []
            for metric in row.get("kpis") or []:
                if not metric.get("active") or metric.get("canonical_metric") not in APPROVED_CANONICAL_METRICS:
                    continue
                provider_kpis.append({
                    "source": REST_KPI_SOURCE,
                    "name": metric["provider_name"], "value": metric.get("value"),
                    "group": metric.get("canonical_metric"), "uom": metric.get("unit"),
                    "unit": metric.get("unit"), "provider_contract": "rest_v2",
                    "provenance": metric.get("provenance"), "raw": metric.get("raw"),
                })
            for zone in (row.get("zones") or {}).get("speed_zones") or []:
                if not zone.get("active") or zone.get("metric_family") != SPEED_ZONE_FAMILY:
                    continue
                provider_kpis.append({
                    "source": "rest_v2_speed_zone",
                    "name": zone["canonical_metric"], "value": zone.get("value"),
                    "group": SPEED_ZONE_FAMILY, "uom": zone.get("value_unit"),
                    "unit": zone.get("value_unit"), "provider_contract": "rest_v2",
                    "provenance": zone.get("provenance"),
                    "raw": {
                        "metric_family": "speed_zone_distance",
                        "provider": "gpexe", "provider_contract": "rest_v2",
                        "provider_metric_name": zone.get("provider_name"),
                        "provider_zone_number": zone.get("provider_zone_number"),
                        "context_snapshot": {
                            "team_id": int(team["team_id"]), "season": season,
                            "team_session_id": provider_session_id,
                            "athlete_session_id": int(row["provider_athlete_session_id"]),
                        },
                        "threshold_snapshot": {
                            "original_lower_bound_mps": zone.get("original_lower_bound_mps"),
                            "original_upper_bound_mps": zone.get("original_upper_bound_mps"),
                            "canonical_lower_bound_kmh": zone.get("canonical_lower_bound_kmh"),
                            "canonical_upper_bound_kmh": zone.get("canonical_upper_bound_kmh"),
                            "provider_threshold_unit": zone.get("provider_threshold_unit"),
                            "canonical_threshold_unit": zone.get("canonical_threshold_unit"),
                            "value_unit": zone.get("value_unit"),
                        },
                        "raw_provider_zone": zone.get("raw"),
                        "provenance": zone.get("provenance"),
                    },
                })
            sessions.append({
                "provider_athlete_session_id": int(row["provider_athlete_session_id"]),
                "provider_session_id": provider_session_id,
                "provider_player_id": athlete_id,
                "drill_id": (row.get("raw") or {}).get("drill"),
                "track_id": track_id,
                "state": row.get("state"), "starter": row.get("starter"),
                "is_stats_valid": row.get("is_stats_valid"),
                "total_time": row.get("total_time"), "template_id": None,
                "track": {"id": track_id, "athlete": {"id": athlete_id},
                          "provider_contract": "rest_v2",
                          "provenance": "gpexe_rest_track_reference"},
                "provider_kpis": provider_kpis,
                "provider_contract": "rest_v2", "provenance": row.get("provenance"),
                "raw": {
                    "provider_contract": "rest_v2",
                    "provenance": row.get("provenance"),
                    "payload": row.get("raw"),
                },
            })
        return parent, list(athletes_by_id.values()), sessions
