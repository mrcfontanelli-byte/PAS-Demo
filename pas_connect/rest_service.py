"""Bundle builder REST GPExe seriale, diagnostico e privo di persistenza."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .rest_client import GPExeRESTClient, RESTProcessingResponse
from .rest_mapper import (
    PROVENANCE,
    map_rest_athlete_session,
    map_rest_athlete_session_list,
    map_rest_team_session,
)

REQUIRED_PROVIDER_KPIS = (
    "distance", "duration", "acceleration_events", "deceleration_events", "speed_events",
)
BUNDLE_STATUSES = {"READY", "INCOMPLETE", "FAILED"}


@dataclass(frozen=True)
class RESTBundleResult:
    status: str
    processing: bool
    bundle: Mapping[str, Any] | None
    diagnostics: tuple[Mapping[str, Any], ...]

    def __post_init__(self) -> None:
        if self.status not in BUNDLE_STATUSES:
            raise ValueError(f"Stato bundle REST non valido: {self.status}")


class GPExeRESTService:
    """Costruisce un bundle REST completo in memoria, senza side effect applicativi."""

    def __init__(self, client: GPExeRESTClient) -> None:
        self.client = client

    def build_team_session_bundle(
        self,
        team_session_id: int,
        *,
        all_params: bool = True,
        require_athlete: bool = True,
        require_track: bool = True,
    ) -> RESTBundleResult:
        requested_id = self.client._positive_id(team_session_id, "TeamSession")
        diagnostics: list[Mapping[str, Any]] = []

        try:
            raw_team = self.client.team_session(requested_id, all_params=all_params)
        except Exception as exc:
            return self._failed("team_session", exc, diagnostics)
        if isinstance(raw_team, RESTProcessingResponse):
            return self._processing("team_session", raw_team, diagnostics)
        try:
            team = map_rest_team_session(raw_team)
        except Exception as exc:
            return self._failed("team_session_mapping", exc, diagnostics)
        if team["provider_session_id"] != requested_id:
            diagnostics.append(self._diagnostic(
                "team_session_validation", "ERROR", "TeamSession ID non coerente.",
            ))
            return RESTBundleResult("FAILED", False, None, tuple(diagnostics))

        try:
            raw_list = self.client.athlete_sessions(requested_id)
        except Exception as exc:
            return self._failed("athlete_session_list", exc, diagnostics)
        if isinstance(raw_list, RESTProcessingResponse):
            partial = self._base_bundle(requested_id, team, (), ())
            return self._processing("athlete_session_list", raw_list, diagnostics, bundle=partial)
        try:
            session_ids = map_rest_athlete_session_list(raw_list)
        except Exception as exc:
            return self._failed("athlete_session_list_mapping", exc, diagnostics)

        mapped_sessions: list[Mapping[str, Any]] = []
        failed_ids = 0
        processing_ids = 0
        for athlete_session_id in session_ids:
            try:
                raw_detail = self.client.athlete_session(athlete_session_id)
                if isinstance(raw_detail, RESTProcessingResponse):
                    processing_ids += 1
                    diagnostics.append(self._processing_diagnostic(
                        "athlete_session_detail", raw_detail,
                        provider_athlete_session_id=athlete_session_id,
                    ))
                    continue
                mapped_sessions.append(map_rest_athlete_session(raw_detail))
            except Exception as exc:
                failed_ids += 1
                diagnostics.append(self._diagnostic(
                    "athlete_session_detail", "ERROR", self.client.redact(str(exc)),
                    provider_athlete_session_id=athlete_session_id,
                    error_type=type(exc).__name__,
                ))

        bundle = self._base_bundle(requested_id, team, tuple(session_ids), tuple(mapped_sessions))
        issues = self._validate_bundle(
            bundle,
            require_athlete=require_athlete,
            require_track=require_track,
        )
        diagnostics.extend(issues)
        if failed_ids or processing_ids:
            diagnostics.append(self._diagnostic(
                "athlete_session_summary", "INCOMPLETE",
                "Uno o piÃ¹ dettagli AthleteSession non sono disponibili.",
                failed_count=failed_ids, processing_count=processing_ids,
            ))
        status = "READY" if not diagnostics else "INCOMPLETE"
        return RESTBundleResult(status, processing_ids > 0, bundle, tuple(diagnostics))

    @staticmethod
    def _base_bundle(
        requested_id: int,
        team: Mapping[str, Any],
        session_ids: tuple[int, ...],
        sessions: tuple[Mapping[str, Any], ...],
    ) -> Mapping[str, Any]:
        return {
            "provider": "gpexe", "provider_contract": "rest_v2",
            "provider_session_id": requested_id,
            "team_session": team,
            "athlete_session_ids": session_ids,
            "athlete_sessions": sessions,
            "provenance": "gpexe_rest_bundle_dry_run",
        }

    def _validate_bundle(
        self,
        bundle: Mapping[str, Any],
        *,
        require_athlete: bool,
        require_track: bool,
    ) -> list[Mapping[str, Any]]:
        diagnostics: list[Mapping[str, Any]] = []
        requested_id = int(bundle["provider_session_id"])
        team = bundle["team_session"]
        expected_ids = tuple(bundle["athlete_session_ids"])
        sessions = tuple(bundle["athlete_sessions"])

        if len(expected_ids) != len(set(expected_ids)):
            diagnostics.append(self._diagnostic(
                "bundle_validation", "ERROR", "AthleteSession ID duplicati.",
            ))
        header_count = team.get("athlete_count")
        if isinstance(header_count, int) and header_count != len(expected_ids):
            diagnostics.append(self._diagnostic(
                "bundle_validation", "INCOMPLETE",
                "Conteggio AthleteSession diverso da header."
            ))
        raw_counts = (team.get("raw") or {}).get("counts")
        track_count = raw_counts.get("n_tracks") if isinstance(raw_counts, Mapping) else None
        if require_track and isinstance(track_count, int) and track_count != len(expected_ids):
            diagnostics.append(self._diagnostic(
                "bundle_validation", "INCOMPLETE", "Conteggio Track diverso dalla lista."
            ))
        if len(sessions) != len(expected_ids):
            diagnostics.append(self._diagnostic(
                "bundle_validation", "INCOMPLETE",
                "Numero dettagli AthleteSession diverso dalla lista."
            ))

        seen: set[int] = set()
        for session in sessions:
            session_id = int(session["provider_athlete_session_id"])
            if session_id in seen:
                diagnostics.append(self._diagnostic(
                    "bundle_validation", "ERROR", "Dettaglio AthleteSession duplicato.",
                    provider_athlete_session_id=session_id,
                ))
            seen.add(session_id)
            if session_id not in expected_ids:
                diagnostics.append(self._diagnostic(
                    "bundle_validation", "ERROR", "AthleteSession non presente nella lista.",
                    provider_athlete_session_id=session_id,
                ))
            if session.get("provider_session_id") != requested_id:
                diagnostics.append(self._diagnostic(
                    "bundle_validation", "ERROR", "AthleteSession associata a TeamSession errata.",
                    provider_athlete_session_id=session_id,
                ))
            if require_athlete and not (session.get("athlete") or {}).get("provider_player_id"):
                diagnostics.append(self._diagnostic(
                    "bundle_validation", "INCOMPLETE", "Athlete ID mancante.",
                    provider_athlete_session_id=session_id,
                ))
            if require_track and not (session.get("track") or {}).get("provider_track_id"):
                diagnostics.append(self._diagnostic(
                    "bundle_validation", "INCOMPLETE", "Track ID mancante.",
                    provider_athlete_session_id=session_id,
                ))
            diagnostics.extend(self._validate_kpis(session_id, session.get("kpis")))
        return diagnostics

    def _validate_kpis(self, session_id: int, metrics: object) -> list[Mapping[str, Any]]:
        if not isinstance(metrics, list):
            return [self._diagnostic(
                "kpi_validation", "INCOMPLETE", "KPI non strutturati come lista.",
                provider_athlete_session_id=session_id,
            )]
        diagnostics: list[Mapping[str, Any]] = []
        by_name: dict[str, Mapping[str, Any]] = {}
        for metric in metrics:
            if not isinstance(metric, Mapping) or not all(
                key in metric for key in ("provider_name", "value", "value_type", "active", "provenance", "raw")
            ):
                diagnostics.append(self._diagnostic(
                    "kpi_validation", "INCOMPLETE", "KPI strutturalmente non valido.",
                    provider_athlete_session_id=session_id,
                ))
                continue
            by_name[str(metric["provider_name"])] = metric
            if metric.get("provenance") != PROVENANCE:
                diagnostics.append(self._diagnostic(
                    "kpi_validation", "INCOMPLETE", "Provenance KPI non valida.",
                    provider_athlete_session_id=session_id,
                ))
            if metric.get("canonical_metric") is None and metric.get("active") is not False:
                diagnostics.append(self._diagnostic(
                    "kpi_validation", "INCOMPLETE", "Metrica provider sconosciuta attivata.",
                    provider_athlete_session_id=session_id,
                ))
        for name in REQUIRED_PROVIDER_KPIS:
            metric = by_name.get(name)
            if metric is None or metric.get("value") is None:
                diagnostics.append(self._diagnostic(
                    "kpi_validation", "INCOMPLETE", f"KPI richiesto mancante: {name}.",
                    provider_athlete_session_id=session_id,
                ))
        return diagnostics

    def _failed(
        self, stage: str, exc: Exception, diagnostics: list[Mapping[str, Any]],
    ) -> RESTBundleResult:
        diagnostics.append(self._diagnostic(
            stage, "ERROR", self.client.redact(str(exc)), error_type=type(exc).__name__,
        ))
        return RESTBundleResult("FAILED", False, None, tuple(diagnostics))

    def _processing(
        self,
        stage: str,
        response: RESTProcessingResponse,
        diagnostics: list[Mapping[str, Any]],
        *,
        bundle: Mapping[str, Any] | None = None,
    ) -> RESTBundleResult:
        diagnostics.append(self._processing_diagnostic(stage, response))
        return RESTBundleResult("INCOMPLETE", True, bundle, tuple(diagnostics))

    @staticmethod
    def _processing_diagnostic(
        stage: str, response: RESTProcessingResponse, **context: Any,
    ) -> Mapping[str, Any]:
        return {
            "stage": stage, "status": "PROCESSING", "message": response.state,
            "http_status": response.status,
            "retry_after_seconds": response.retry_after_seconds,
            **context,
        }

    @staticmethod
    def _diagnostic(stage: str, status: str, message: str, **context: Any) -> Mapping[str, Any]:
        return {"stage": stage, "status": status, "message": message, **context}
