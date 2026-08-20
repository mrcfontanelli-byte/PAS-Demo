"""Bundle builder REST GPExe seriale, diagnostico e privo di persistenza."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

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
BUNDLE_PROVENANCE_AGGREGATE = "rest_v2_aggregate"
BUNDLE_PROVENANCE_ELEMENTARY = "rest_v2_elementary"


def _canonical_bundle(
    requested_id: int,
    team: Mapping[str, Any],
    session_ids: Sequence[int],
    sessions: Sequence[Mapping[str, Any]],
    *,
    provenance: str,
) -> Mapping[str, Any]:
    return {
        "provider": "gpexe", "provider_contract": "rest_v2",
        "provider_session_id": int(requested_id),
        "team_session": dict(team),
        "athlete_session_ids": tuple(int(value) for value in session_ids),
        "athlete_sessions": tuple(sessions),
        "provenance": provenance,
    }


def build_rest_elementary_bundle(
    team_session_metadata: Mapping[str, Any],
    athlete_session_ids: Sequence[int],
    athlete_session_detail_payloads: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    """Costruisce il modello canonico REST usando esclusivamente payload elementari."""
    requested_id = int(team_session_metadata["provider_session_id"])
    mapped = tuple(map_rest_athlete_session(payload) for payload in athlete_session_detail_payloads)
    return _canonical_bundle(
        requested_id, team_session_metadata, athlete_session_ids, mapped,
        provenance=BUNDLE_PROVENANCE_ELEMENTARY,
    )


def _aggregate_athlete_session_ids(team: Mapping[str, Any]) -> tuple[int, ...] | None:
    """Estrae gli ID dall'aggregate solo quando la relativa struttura e disponibile."""
    raw = team.get("raw")
    if not isinstance(raw, Mapping):
        return None
    table_data = raw.get("table_data")
    if not isinstance(table_data, Mapping):
        return None
    rows = table_data.get("athlete_sessions")
    if not isinstance(rows, list):
        return None
    result: list[int] = []
    for row in rows:
        if not isinstance(row, Mapping):
            return None
        try:
            result.append(int(row["id"]))
        except (KeyError, TypeError, ValueError):
            return None
    return tuple(result)


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
        team_session_metadata: Mapping[str, Any] | None = None,
    ) -> RESTBundleResult:
        requested_id = self.client._positive_id(team_session_id, "TeamSession")
        diagnostics: list[Mapping[str, Any]] = []

        try:
            raw_team = self.client.team_session(requested_id, all_params=all_params)
        except Exception as exc:
            return self._failed("team_session", exc, diagnostics)
        aggregate_processing = isinstance(raw_team, RESTProcessingResponse)
        if aggregate_processing:
            diagnostics.append(self._processing_diagnostic("team_session", raw_team))
            team = dict(team_session_metadata or {})
            if team and int(team.get("provider_session_id") or 0) != requested_id:
                diagnostics.append(self._diagnostic(
                    "team_session_metadata", "ERROR", "TeamSession metadata non coerente.",
                ))
                return RESTBundleResult("FAILED", False, None, tuple(diagnostics))
        else:
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
            partial = self._base_bundle(requested_id, team, (), ()) if team else None
            return self._processing("athlete_session_list", raw_list, diagnostics, bundle=partial)
        try:
            session_ids = map_rest_athlete_session_list(raw_list)
        except Exception as exc:
            return self._failed("athlete_session_list_mapping", exc, diagnostics)

        if not aggregate_processing:
            aggregate_ids = _aggregate_athlete_session_ids(team)
            if aggregate_ids is not None and (
                len(aggregate_ids) != len(set(aggregate_ids))
                or set(aggregate_ids) != set(session_ids)
            ):
                diagnostics.append(self._diagnostic(
                    "athlete_session_membership", "ERROR",
                    "Set AthleteSession scoped diverso dal set aggregate.",
                    scoped_count=len(session_ids), aggregate_count=len(aggregate_ids),
                    intersection_count=len(set(session_ids).intersection(aggregate_ids)),
                    scoped_only_count=len(set(session_ids).difference(aggregate_ids)),
                    aggregate_only_count=len(set(aggregate_ids).difference(session_ids)),
                ))
                return RESTBundleResult("INCOMPLETE", False, None, tuple(diagnostics))

        mapped_sessions: list[Mapping[str, Any]] = []
        raw_sessions: list[Mapping[str, Any]] = []
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
                raw_sessions.append(raw_detail)
            except Exception as exc:
                failed_ids += 1
                diagnostics.append(self._diagnostic(
                    "athlete_session_detail", "ERROR", self.client.redact(str(exc)),
                    provider_athlete_session_id=athlete_session_id,
                    error_type=type(exc).__name__,
                ))

        if aggregate_processing:
            if not team:
                diagnostics.append(self._diagnostic(
                    "team_session_metadata", "INCOMPLETE",
                    "Metadata TeamSession locali non disponibili per il fallback elementare.",
                ))
                return RESTBundleResult("INCOMPLETE", True, None, tuple(diagnostics))
            try:
                bundle = build_rest_elementary_bundle(team, session_ids, raw_sessions)
            except Exception as exc:
                return self._failed("elementary_bundle_mapping", exc, diagnostics)
        else:
            bundle = _canonical_bundle(
                requested_id, team, session_ids, mapped_sessions,
                provenance=BUNDLE_PROVENANCE_AGGREGATE,
            )
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
        blocking = [item for item in diagnostics if item.get("stage") != "team_session"]
        status = "READY" if not blocking else "INCOMPLETE"
        processing = processing_ids > 0 or (aggregate_processing and status != "READY")
        return RESTBundleResult(status, processing, bundle, tuple(diagnostics))

    @staticmethod
    def _base_bundle(
        requested_id: int,
        team: Mapping[str, Any],
        session_ids: tuple[int, ...],
        sessions: tuple[Mapping[str, Any], ...],
    ) -> Mapping[str, Any]:
        return _canonical_bundle(
            requested_id, team, session_ids, sessions,
            provenance=BUNDLE_PROVENANCE_AGGREGATE,
        )

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
        payload = response.payload if isinstance(response.payload, Mapping) else {}
        return {
            "stage": stage, "status": "PROCESSING", "message": response.state,
            "http_status": response.status,
            "retry_after_seconds": response.retry_after_seconds,
            "task_id": response.task_id if response.task_id is not None else payload.get("task_id"),
            "original_task_id": (
                response.original_task_id
                if response.original_task_id is not None
                else payload.get("original_task_id")
            ),
            **context,
        }

    @staticmethod
    def _diagnostic(stage: str, status: str, message: str, **context: Any) -> Mapping[str, Any]:
        return {"stage": stage, "status": status, "message": message, **context}
