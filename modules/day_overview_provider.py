"""Provider comune della Panoramica del giorno, senza dipendenze dalla UI."""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

import pandas as pd

from pas_connect.metric_descriptors import (
    SCALAR_METRICS, descriptor_pas_value, resolve_scalar_metrics,
)
from pas_connect.speed_zone_metrics import descriptor_from_snapshot

from modules.session_distance import (
    MISSING_DAY_MESSAGE, TOTAL_SESSION_DRILLS, UNSUPPORTED_DRILL_MESSAGE,
    SessionDistanceError, normalize_athlete_name,
)


@dataclass(frozen=True)
class OverviewMetric:
    display: str
    column: str
    canonical: str
    unit: str
    aggregation: str
    provider_name: str | None = None
    provider_kpi: str | None = None
    external_provider: str | None = None


OVERVIEW_METRICS = (
    OverviewMetric("RPE", "RPE (CR10)", "RPE", "", "mean", "rpe", "rpe"),
    OverviewMetric("Anaerobic Threshold Zone (mm:ss)", "Anaerobic threshold zone (hh:mm:ss)",
                   "Anaerobic Threshold Zone", "s", "sum", external_provider="Firstbeat"),
    OverviewMetric("High Intensity Training (mm:ss)", "High intensity training (hh:mm:ss)",
                   "High Intensity Training", "s", "sum", external_provider="Firstbeat"),
    OverviewMetric("Duration (min)", "Duration (dec)", "Duration", "s", "sum",
                   "duration (mm:ss)", "__athlete_total_time__"),
    OverviewMetric("Distance (m)", "distance (m)", "Distance", "m", "sum",
                   "distance (m)", "total_distance"),
    OverviewMetric("Distance 19.8-25.2 km/h (m)", "distance/speed Z3 (m)", "Distance Z3", "m", "sum",
                   "distance/speed Z3 (m)", "athletesessionspeedzone_distance_3"),
    OverviewMetric("Distance >25.2 km/h (m)", "distance/speed Z4 (m)", "Distance Z4", "m", "sum",
                   "distance/speed Z4 (m)", "athletesessionspeedzone_distance_4"),
    OverviewMetric("Acc Events (n°)", "acc events", "Acc Events", "n", "sum",
                   "acc events", "acceleration_events"),
    OverviewMetric("Dec Events (n°)", "dec events", "Dec Events", "n", "sum",
                   "dec events", "deceleration_events"),
    OverviewMetric("Max Speed (km/h)", "max speed (km/h)", "Max Speed", "km/h", "max",
                   "max speed (km/h)", "max_values_speed"),
    OverviewMetric("Speed Events (n°)", "speed events", "Speed Events", "n", "sum",
                   "speed events", "speed_events"),
)

_OVERVIEW_BY_CANONICAL = {metric.canonical: metric for metric in OVERVIEW_METRICS}

_DYNAMIC_ZONE_DEFAULT_COLOR = "#F2CF5B"
_DYNAMIC_ZONE_HIGH_SPEED_COLOR = "#F2CF5B"
_DYNAMIC_ZONE_TOP_SPEED_COLOR = "#E45756"


def _dynamic_zone_color(descriptor: Any) -> str:
    """Condivide solo la palette legacy per i bounds canonici equivalenti."""
    bounds = (descriptor.lower_bound, descriptor.upper_bound)
    if bounds in {(19.8, 25.2), (20.0, 25.0)}:
        return _DYNAMIC_ZONE_HIGH_SPEED_COLOR
    if bounds in {(25.2, None), (25.0, None)}:
        return _DYNAMIC_ZONE_TOP_SPEED_COLOR
    return _DYNAMIC_ZONE_DEFAULT_COLOR


def _dynamic_zone_specs(rows: Iterable[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Costruisce specifiche consumer dalle snapshot REST storiche."""
    descriptors = {}
    for row in rows:
        if str(row.get("source") or "") != "rest_v2_speed_zone":
            continue
        try:
            descriptor = descriptor_from_snapshot(row)
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        descriptors[descriptor.metric_key] = descriptor
    return {
        descriptor.label: {
            "column": descriptor.label, "unit": descriptor.value_unit,
            "aggregation": descriptor.accumulation, "accumulation": descriptor.accumulation,
            "decimals": 0, "format": "number", "color": _dynamic_zone_color(descriptor),
            "canonical_key": descriptor.metric_key, "metric_family": descriptor.metric_family,
            "threshold_lower": descriptor.lower_bound, "threshold_upper": descriptor.upper_bound,
            "threshold_unit": descriptor.threshold_unit,
        }
        for descriptor in sorted(descriptors.values(), key=lambda item: item.sort_key)
    }

PROFILE_ALIASES = {
    "Distance Z3": frozenset({
        "distance z3", "distance/speed z3", "distance 19.8-25.2 km/h",
        "distance 19.8-25.2 km/h (m)",
    }),
    "Distance Z4": frozenset({
        "distance z4", "distance/speed z4", "distance >25.2 km/h",
        "distance >25.2 km/h (m)",
    }),
}


def _normalize_profile_name(value: object) -> str:
    return " ".join(
        str(value or "").strip().casefold().replace("â€“", "-").replace("–", "-").split()
    )


def _profile_family(value: object) -> str | None:
    normalized = _normalize_profile_name(value)
    return next((family for family, aliases in PROFILE_ALIASES.items() if normalized in aliases), None)


def _profile_shape(profile: dict[str, Any]) -> str:
    has_min = profile.get("threshold_min") is not None
    has_max = profile.get("threshold_max") is not None
    return "bounded" if has_min and has_max else "lower" if has_min else "other"


def _requested_profile_shape(canonical_metric: str) -> str | None:
    normalized = _normalize_profile_name(canonical_metric)
    if ">" in normalized:
        return "lower"
    if "-" in normalized and any(character.isdigit() for character in normalized):
        return "bounded"
    return None


def resolve_threshold_metric_profile(
    connection: sqlite3.Connection, canonical_metric: str, *, team_id: object,
    season: object, valid_on: object,
) -> dict[str, Any] | None:
    """Risolve un profilo verificato per Team, stagione, validità e alias controllati."""
    if team_id in (None, "") or season in (None, ""):
        return None
    target_family = _profile_family(canonical_metric)
    if target_family is None:
        return None
    target_date = pd.Timestamp(valid_on).strftime("%Y-%m-%d")
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """SELECT id,team_id,team_name,season,canonical_metric,provider_metric_name,
                  threshold_min,threshold_max,threshold_min_inclusive,
                  threshold_max_inclusive,threshold_unit,verified,valid_from,valid_to
           FROM pas_metric_profiles
           WHERE cast(team_id AS text)=? AND season=? AND verified=1
             AND (valid_from IS NULL OR valid_from='' OR substr(valid_from,1,10)<=?)
             AND (valid_to IS NULL OR valid_to='' OR substr(valid_to,1,10)>=?)
           ORDER BY id DESC""",
        (str(team_id), str(season), target_date, target_date),
    ).fetchall()
    candidates = [dict(row) for row in rows if _profile_family(row["canonical_metric"]) == target_family]
    requested_shape = _requested_profile_shape(canonical_metric)
    if requested_shape:
        shaped = [row for row in candidates if _profile_shape(row) == requested_shape]
        if shaped:
            candidates = shaped
    return candidates[0] if candidates else None


def _resolve_overview_context(
    connection: sqlite3.Connection, target: str, *, team_id: object | None,
    session_ids: Iterable[int] | None = None,
) -> tuple[str | None, str | None]:
    selected_sessions = sorted({int(value) for value in (session_ids or [])})
    clauses = ["substr(s.start_timestamp,1,10)=?"]
    params: list[object] = [target]
    if team_id not in (None, ""):
        clauses.append("cast(s.team_id as text)=?")
        params.append(str(team_id))
    if selected_sessions:
        clauses.append(f"s.provider_session_id in ({','.join('?' for _ in selected_sessions)})")
        params.extend(selected_sessions)
    rows = connection.execute(
        f"""SELECT DISTINCT cast(s.team_id AS text) team_id,t.season
            FROM gpexe_team_sessions s
            LEFT JOIN gpexe_teams t ON cast(t.provider_team_id AS text)=cast(s.team_id AS text)
            WHERE {' AND '.join(clauses)}""",
        params,
    ).fetchall()
    contexts = {
        (str(row[0]), str(row[1])) for row in rows
        if row[0] not in (None, "") and row[1] not in (None, "")
    }
    if len(contexts) == 1:
        return next(iter(contexts))
    team_ids = {str(row[0]) for row in rows if row[0] not in (None, "")}
    if len(team_ids) != 1:
        return None, None
    resolved_team = next(iter(team_ids))
    seasons = {
        str(row[0]) for row in connection.execute(
            """SELECT DISTINCT season FROM pas_metric_profiles
               WHERE cast(team_id AS text)=? AND verified=1
                 AND (valid_from IS NULL OR valid_from='' OR substr(valid_from,1,10)<=?)
                 AND (valid_to IS NULL OR valid_to='' OR substr(valid_to,1,10)>=?)""",
            (resolved_team, target, target),
        ) if row[0] not in (None, "")
    }
    return (resolved_team, next(iter(seasons))) if len(seasons) == 1 else (None, None)


def duration_seconds(value: object, unit: str | None = None) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        return duration_seconds(value.get("value"), value.get("uom") or value.get("unit"))
    text = str(value).strip()
    if ":" in text:
        try:
            parts = [float(part) for part in text.split(":")]
        except ValueError:
            return None
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return None
    try:
        number = float(text.replace(",", "."))
    except ValueError:
        return None
    normalized = str(unit or "s").strip().casefold()
    return number * 60 if normalized in {"min", "minute", "minutes"} else number


def overview_coverage(
    database_path: str | Path, *, team_id: object | None = None,
    season: object | None = None, valid_on: object | None = None,
    session_ids: Iterable[int] | None = None,
) -> list[dict[str, object]]:
    path = Path(database_path)
    catalog: set[str] = set()
    profiles: set[str] = set()
    if path.is_file():
        with sqlite3.connect(path) as connection:
            if valid_on is not None and (team_id in (None, "") or season in (None, "")):
                context_team, context_season = _resolve_overview_context(
                    connection, pd.Timestamp(valid_on).strftime("%Y-%m-%d"),
                    team_id=team_id, session_ids=session_ids,
                )
                team_id = context_team
                season = context_season
            catalog = {str(row[0]).casefold() for row in connection.execute(
                "SELECT canonical_metric FROM pas_metric_catalog WHERE provider='GPExe'"
            )}
            if team_id not in (None, "") and season not in (None, "") and valid_on is not None:
                profiles = {
                    metric.canonical for metric in OVERVIEW_METRICS
                    if metric.canonical in PROFILE_ALIASES and resolve_threshold_metric_profile(
                        connection, metric.display.removesuffix(" (m)"), team_id=team_id,
                        season=season, valid_on=valid_on,
                    ) is not None
                }
    rows = []
    for metric in OVERVIEW_METRICS:
        if metric.external_provider:
            status = "EXTERNAL_PROVIDER"
        elif metric.canonical in {"Distance Z3", "Distance Z4"}:
            status = "VERIFIED" if metric.canonical in profiles else "MISSING"
        elif metric.provider_name and (
            metric.canonical.casefold() in catalog
            or metric.provider_name.rsplit(" (", 1)[0].casefold() in catalog
        ):
            status = "VERIFIED"
        else:
            status = "MISSING"
        rows.append({"Metrica": metric.display, "Provider richiesto": metric.external_provider or "GPExe",
                     "Stato": status, "Unità canonica": metric.unit})
    return rows


def coverage_percentage(rows: list[dict[str, object]]) -> float:
    return 100.0 * sum(row["Stato"] == "VERIFIED" for row in rows) / len(rows) if rows else 0.0


def load_gpexe_day_overview(
    database_path: str | Path, selected_date: object, *, drill: str = "Totale sessione",
    team_id: object | None = None, session_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[object] | None = None, athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    if drill not in TOTAL_SESSION_DRILLS:
        raise SessionDistanceError(UNSUPPORTED_DRILL_MESSAGE)
    path = Path(database_path)
    target = pd.Timestamp(selected_date).strftime("%Y-%m-%d")
    clauses = ["substr(s.start_timestamp,1,10)=?"]
    params: list[object] = [target]
    if team_id not in (None, ""):
        clauses.append("cast(s.team_id as text)=?"); params.append(str(team_id))
    selected_sessions = sorted({int(value) for value in (session_ids or [])})
    if selected_sessions:
        clauses.append(f"s.provider_session_id in ({','.join('?' for _ in selected_sessions)})")
        params.extend(selected_sessions)
    sql = f"""SELECT d.provider_athlete_session_id athlete_session_id,
      d.provider_session_id team_session_id,d.provider_player_id athlete_id,s.team_id,
      s.start_timestamp,COALESCE(
        NULLIF(TRIM(COALESCE(a.first_name,'')||' '||COALESCE(a.last_name,'')),''),
        NULLIF(TRIM(a.player_name),''),
        'GPExe Athlete '||d.provider_player_id
      ) athlete,
      d.raw_json detail_raw_json,k.source,k.position,k.name,k.value,k.kpi_group,
      k.uom,k.unit,k.raw_json kpi_raw_json
      FROM gpexe_athlete_session_details d JOIN gpexe_team_sessions s
      ON s.provider_session_id=d.provider_session_id
      LEFT JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
      LEFT JOIN gpexe_athlete_session_kpis k
      ON k.provider_athlete_session_id=d.provider_athlete_session_id
      WHERE {' AND '.join(clauses)} ORDER BY d.provider_athlete_session_id,k.source,k.position"""
    with sqlite3.connect(path) as connection:
        resolved_team_id, resolved_season = _resolve_overview_context(
            connection, target, team_id=team_id, session_ids=selected_sessions,
        )
        raw = pd.read_sql_query(sql, connection, params=params)
        profile_kpis = {}
        for metric in OVERVIEW_METRICS:
            if metric.canonical not in PROFILE_ALIASES:
                continue
            profile = resolve_threshold_metric_profile(
                connection, metric.display.removesuffix(" (m)"), team_id=resolved_team_id,
                season=resolved_season, valid_on=target,
            )
            if profile is not None:
                profile_kpis[metric.canonical] = str(profile["provider_metric_name"])
    if raw.empty:
        raise SessionDistanceError(MISSING_DAY_MESSAGE)
    zone_specs = _dynamic_zone_specs([
        {"source": row.source, "raw_json": row.kpi_raw_json}
        for row in raw.itertuples() if pd.notna(row.source)
    ])
    records = []
    for athlete_session_id, rows in raw.groupby("athlete_session_id", sort=False):
        first = rows.iloc[0]
        record = {"Date": pd.Timestamp(first["start_timestamp"]), "Athlete": normalize_athlete_name(first["athlete"]),
                  "Athlete ID": first["athlete_id"], "AthleteSession ID": athlete_session_id,
                  "TeamSession ID": first["team_session_id"], "Team ID": first["team_id"], "Source": "GPExe"}
        kpi_rows = [
            {"source": item.source, "position": item.position, "name": item.name,
             "value": item.value, "kpi_group": item.kpi_group, "uom": item.uom,
             "unit": item.unit, "raw_json": item.kpi_raw_json}
            for item in rows.itertuples() if pd.notna(item.name)
        ]
        scalar = resolve_scalar_metrics(kpi_rows)
        for spec in SCALAR_METRICS:
            metric = _OVERVIEW_BY_CANONICAL.get(spec.canonical_key)
            if metric is None:
                continue
            descriptor = scalar.get(spec.canonical_key)
            record[metric.column] = descriptor_pas_value(descriptor) if descriptor else pd.NA
        if pd.isna(record.get("Duration (dec)")):
            try:
                detail_raw = json.loads(str(first["detail_raw_json"] or "{}"))
            except json.JSONDecodeError:
                detail_raw = {}
            seconds = duration_seconds(detail_raw.get("totalTime") or detail_raw.get("total_time"))
            record["Duration (dec)"] = seconds / 60.0 if seconds is not None else pd.NA
        record["Duration (s)"] = (
            float(record["Duration (dec)"]) * 60.0
            if pd.notna(record.get("Duration (dec)")) else pd.NA
        )
        for label, spec in zone_specs.items():
            matches = [item for item in kpi_rows if item["source"] == "rest_v2_speed_zone"
                       and item["name"] == spec["canonical_key"]]
            record[label] = pd.to_numeric(matches[0]["value"], errors="coerce") if matches else pd.NA
        # Compatibilita GraphQL legacy: i profili Z3/Z4 restano disponibili
        # soltanto quando il contesto non possiede zone REST dinamiche.
        if not zone_specs:
            for canonical, provider_name in profile_kpis.items():
                metric = _OVERVIEW_BY_CANONICAL[canonical]
                matches = [item for item in kpi_rows if item["name"] == provider_name]
                record[metric.column] = (
                    pd.to_numeric(matches[0]["value"], errors="coerce") if matches else pd.NA
                )
        records.append(record)
    frame = pd.DataFrame(records)
    ids = {str(value) for value in (athlete_ids or [])}
    if ids:
        frame = frame[frame["Athlete ID"].astype("string").isin(ids)]
    elif athletes:
        names = {normalize_athlete_name(value) for value in athletes}
        frame = frame[frame["Athlete"].isin(names)]
    aggregations = {
        metric.column: (lambda values: values.sum(min_count=1))
        if metric.aggregation == "sum" else metric.aggregation
        for metric in OVERVIEW_METRICS
        if metric.column in frame.columns
    }
    aggregations.update({label: (lambda values: values.sum(min_count=1)) for label in zone_specs})
    aggregations["Duration (s)"] = lambda values: values.sum(min_count=1)
    aggregations.update({"Athlete": "first", "Athlete ID": "first", "Team ID": "first", "Source": "first",
                         "TeamSession ID": lambda values: ",".join(sorted({str(v) for v in values.dropna()}))})
    frame["athlete_key"] = frame.apply(lambda row: f"id:{row['Athlete ID']}" if pd.notna(row["Athlete ID"])
                                       else f"name:{row['Athlete']}", axis=1)
    result = frame.groupby(["Date", "athlete_key"], as_index=False).agg(aggregations).drop(columns="athlete_key")
    result.attrs["dynamic_metric_specs"] = zone_specs
    return result
