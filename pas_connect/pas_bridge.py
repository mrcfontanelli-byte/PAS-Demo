"""Conversione del database PAS Connect GPExe nello schema prestativo PAS."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd

from modules.data_mapping import CANONICAL_METRICS, map_gpexe_metrics
from .dashboard_sessions import classify_local_dashboard_sessions
from .metric_descriptors import SCALAR_METRICS, descriptor_pas_value, resolve_scalar_metrics

_SCALAR_SPEC_BY_CANONICAL = {spec.canonical_key: spec for spec in SCALAR_METRICS}


def _duration_minutes(value: object) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 60.0 if number > 300 else number
    text = str(value).strip()
    try:
        if ":" in text:
            parts = [float(part) for part in text.split(":")]
            if len(parts) == 3:
                return parts[0] * 60 + parts[1] + parts[2] / 60
            if len(parts) == 2:
                return parts[0] + parts[1] / 60
        return float(text) / 60.0
    except (TypeError, ValueError):
        return None


def available_sessions(
    database_path: str | Path, *, team_id: int | None = None,
    season: str | None = None, ready_only: bool = False,
    dashboard_only: bool = False,
) -> list[dict[str, object]]:
    path = Path(database_path)
    if not path.is_file():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        clauses: list[str] = []
        values: list[object] = []
        if team_id is not None:
            clauses.append("s.team_id=?")
            values.append(int(team_id))
        table_names = {
            str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        has_results = {
            "gpexe_session_sync_results", "gpexe_sync_runs"
        }.issubset(table_names)
        has_local_performance = {
            "gpexe_athlete_session_details",
            "gpexe_athlete_session_kpis",
            "gpexe_athlete_team_memberships",
        }.issubset(table_names)
        local_eligible = """EXISTS (
            SELECT 1
            FROM gpexe_athlete_session_details a
            JOIN gpexe_athlete_session_kpis k
              ON k.provider_athlete_session_id=a.provider_athlete_session_id
             AND k.source IN ('rest_v2','identifierKpi','kpi')
            WHERE a.provider_session_id=s.provider_session_id
        )"""
        ready_eligible = """EXISTS (
            SELECT 1 FROM gpexe_session_sync_results r
            WHERE r.provider_session_id=s.provider_session_id
              AND r.readiness='READY' AND r.status IN ('SUCCESS','SKIPPED')
        )"""
        if season:
            eligibility: list[str] = []
            if has_local_performance:
                eligibility.append("""EXISTS (
                    SELECT 1
                    FROM gpexe_athlete_session_details a
                    JOIN gpexe_athlete_session_kpis k
                      ON k.provider_athlete_session_id=a.provider_athlete_session_id
                     AND k.source IN ('rest_v2','identifierKpi','kpi')
                    JOIN gpexe_athlete_team_memberships m
                      ON m.provider_player_id=a.provider_player_id
                     AND m.team_id=s.team_id AND m.season=?
                    WHERE a.provider_session_id=s.provider_session_id
                )""")
                values.append(str(season))
            if has_results:
                eligibility.append("""EXISTS (
                    SELECT 1 FROM gpexe_session_sync_results r
                    JOIN gpexe_sync_runs u ON u.id=r.sync_run_id
                    WHERE r.provider_session_id=s.provider_session_id AND u.season=?
                      AND (?=0 OR (r.readiness='READY'
                                   AND r.status IN ('SUCCESS','SKIPPED')))
                )""")
                values.extend((str(season), int(bool(ready_only))))
            if not eligibility:
                return []
            clauses.append("(" + " OR ".join(eligibility) + ")")
        elif ready_only:
            eligibility = []
            if has_local_performance:
                eligibility.append(local_eligible)
            if has_results:
                eligibility.append(ready_eligible)
            if not eligibility:
                return []
            clauses.append("(" + " OR ".join(eligibility) + ")")
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        rows = connection.execute(
            """SELECT s.provider_session_id, s.session_name, s.start_timestamp,
               s.team_id, s.state FROM gpexe_team_sessions s""" + where
            + " ORDER BY s.start_timestamp DESC, s.provider_session_id DESC",
            values,
        ).fetchall()
        sessions = [dict(row) for row in rows]
        if ready_only and team_id is not None and season:
            sessions = classify_local_dashboard_sessions(
                connection, sessions, team_id=int(team_id), season=str(season)
            )
            if dashboard_only:
                sessions = [item for item in sessions if item["dashboard_eligible"]]
    return sessions


def available_contexts(database_path: str | Path) -> list[dict[str, object]]:
    """Elenca Team/stagioni localmente utilizzabili, senza consultare Excel."""
    path = Path(database_path)
    if not path.is_file():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        table_names = {
            str(row[0]) for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        selects: list[str] = []
        if {
            "gpexe_team_sessions",
            "gpexe_athlete_session_details",
            "gpexe_athlete_session_kpis",
            "gpexe_athlete_team_memberships",
        }.issubset(table_names):
            selects.append("""SELECT s.team_id AS team_id, m.season AS season,
                       1 AS source_priority
                FROM gpexe_team_sessions s
                JOIN gpexe_athlete_session_details a
                  ON a.provider_session_id=s.provider_session_id
                JOIN gpexe_athlete_session_kpis k
                  ON k.provider_athlete_session_id=a.provider_athlete_session_id
                 AND k.source IN ('rest_v2','identifierKpi','kpi')
                JOIN gpexe_athlete_team_memberships m
                  ON m.provider_player_id=a.provider_player_id
                 AND m.team_id=s.team_id
                WHERE s.team_id IS NOT NULL AND TRIM(m.season)<>''""")
        if {"gpexe_session_sync_results", "gpexe_sync_runs"}.issubset(table_names):
            selects.append("""SELECT r.team_id AS team_id, u.season AS season,
                       0 AS source_priority
                FROM gpexe_session_sync_results r
                JOIN gpexe_sync_runs u ON u.id=r.sync_run_id
                WHERE r.readiness='READY' AND r.status IN ('SUCCESS','SKIPPED')
                  AND r.team_id IS NOT NULL AND TRIM(u.season)<>''""")
        if "gpexe_teams" in table_names:
            selects.append("""SELECT provider_team_id AS team_id, season,
                       2 AS source_priority
                FROM gpexe_teams
                WHERE season IS NOT NULL AND TRIM(season)<>''""")
        if not selects:
            return []
        rows = connection.execute(
            "WITH contexts AS (" + " UNION ALL ".join(selects)
            + "), ranked AS (SELECT team_id,season,MIN(source_priority) source_priority "
              "FROM contexts GROUP BY team_id,season) "
              "SELECT r.team_id,r.season,t.team_name FROM ranked r "
              "LEFT JOIN gpexe_teams t ON t.provider_team_id=r.team_id "
              "ORDER BY r.source_priority,r.team_id,r.season"
        ).fetchall()
        result: list[dict[str, object]] = []
        for row in rows:
            item = dict(row)
            if item.get("team_name") in (None, ""):
                item.pop("team_name", None)
            result.append(item)
        return result


def format_gpexe_context_label(
    team_id: object,
    season: object,
    team_name: object = None,
) -> str:
    """Label provider-aware; Team ID e stagione restano la chiave interna."""
    name = str(team_name or "").strip() or f"Team {int(team_id)}"
    return f"{name} · {str(season)}"


def available_athletes(
    database_path: str | Path, *, team_id: int, season: str,
    selected_session_ids: Iterable[int] | None = None,
) -> list[dict[str, object]]:
    """Elenca l'unione degli atleti delle sole TeamSession selezionate."""
    path = Path(database_path)
    selected = tuple(sorted({int(value) for value in (selected_session_ids or [])}))
    if not path.is_file() or not selected:
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='gpexe_athlete_team_memberships'"
        ).fetchone() is None:
            return []
        placeholders = ",".join("?" for _ in selected)
        rows = connection.execute(
            f"""SELECT a.provider_player_id, a.external_player_id, a.first_name,
                a.last_name, a.player_name, a.short_name, m.team_id, m.season,
                m.jersey_number, m.is_active
            FROM gpexe_athlete_session_details d
            JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
            JOIN gpexe_athlete_team_memberships m
              ON m.provider_player_id=d.provider_player_id AND m.team_id=s.team_id
            JOIN gpexe_athletes a ON a.provider_player_id=m.provider_player_id
            WHERE m.team_id=? AND m.season=?
              AND d.provider_session_id IN ({placeholders})
            GROUP BY a.provider_player_id, a.external_player_id, a.first_name,
                a.last_name, a.player_name, a.short_name, m.team_id, m.season,
                m.jersey_number, m.is_active
            ORDER BY a.player_name, a.provider_player_id""",
            (int(team_id), str(season), *selected),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            full_name = f"{item.get('first_name') or ''} {item.get('last_name') or ''}".strip()
            item["athlete_label"] = (
                full_name
                or str(item.get("player_name") or "").strip()
                or f"GPExe Athlete {item['provider_player_id']}"
            ).upper()
            result.append(item)
        return result


def has_compatible_performance_rows(
    database_path: str | Path,
    *,
    session_ids: Iterable[int] | None = None,
) -> bool:
    """Indica se il database locale e gia utilizzabile dalla pipeline analitica PAS.

    Le tabelle introdotte da PAS Connect possono essere correttamente popolate anche
    quando la conversione verso lo schema prestativo storico non e ancora possibile.
    Quel caso e uno stato supportato, non un errore di caricamento dell'app.
    """
    try:
        return not load_pas_performance_frame(
            database_path,
            session_ids=session_ids,
        ).empty
    except (FileNotFoundError, ValueError, sqlite3.Error, KeyError, TypeError, json.JSONDecodeError):
        return False


def load_pilot_distance_frame(database_path: str | Path) -> pd.DataFrame:
    """Legge il KPI Distance v4.4 nello schema comune della vista pilota."""
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"Database PAS Connect non trovato: {path}")
    sql = """
        SELECT s.start_timestamp AS Date,
               COALESCE(
                   NULLIF(TRIM(COALESCE(a.first_name, '') || ' ' || COALESCE(a.last_name, '')), ''),
                   NULLIF(TRIM(a.player_name), ''),
                   'GPExe Athlete ' || d.provider_player_id
               ) AS Athlete,
               d.provider_player_id AS athlete_id,
               k.value AS distance_value, k.uom AS distance_uom,
               d.provider_session_id AS team_session_id,
               s.team_id AS team_id,
               d.provider_athlete_session_id AS athlete_session_id,
               k.source AS kpi_source
        FROM gpexe_athlete_session_kpis k
        JOIN gpexe_athlete_session_details d
          ON d.provider_athlete_session_id=k.provider_athlete_session_id
        JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
        LEFT JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
        WHERE LOWER(k.name) IN ('distance', 'total distance', 'total_distance')
        ORDER BY d.provider_athlete_session_id,
                 CASE k.source WHEN 'identifierKpi' THEN 0 ELSE 1 END,
                 k.position
    """
    with sqlite3.connect(path) as connection:
        frame = pd.read_sql_query(sql, connection)
    columns = [
        "Date", "Athlete", "Distance (m)", "TeamSession ID",
        "AthleteSession ID", "Athlete ID", "Team ID", "Source",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame = frame.drop_duplicates(subset=["athlete_session_id"], keep="first")
    distance = pd.to_numeric(frame["distance_value"], errors="coerce")
    distance = distance.where(frame["distance_uom"].str.lower().ne("km"), distance * 1000.0)
    result = pd.DataFrame({
        "Date": pd.to_datetime(frame["Date"], errors="coerce"),
        "Athlete": frame["Athlete"].astype("string").str.strip(),
        "Distance (m)": distance,
        "TeamSession ID": frame["team_session_id"],
        "AthleteSession ID": frame["athlete_session_id"],
        "Athlete ID": frame["athlete_id"],
        "Team ID": frame["team_id"],
        "Source": "GPExe",
    })
    return result.dropna(subset=["Date", "Athlete", "Distance (m)"]).reset_index(drop=True)


def session_exists_on_date(
    database_path: str | Path,
    selected_date: object,
    *,
    team_id: object | None = None,
    session_ids: Iterable[int] | None = None,
) -> bool:
    path = Path(database_path)
    target = pd.Timestamp(selected_date).strftime("%Y-%m-%d")
    clauses = ["substr(start_timestamp, 1, 10)=?"]
    params: list[object] = [target]
    if team_id not in (None, ""):
        clauses.append("CAST(team_id AS TEXT)=?")
        params.append(str(team_id))
    selected = tuple(sorted({int(value) for value in (session_ids or [])}))
    if selected:
        clauses.append(f"provider_session_id IN ({','.join('?' for _ in selected)})")
        params.extend(selected)
    with sqlite3.connect(path) as connection:
        return connection.execute(
            f"SELECT 1 FROM gpexe_team_sessions WHERE {' AND '.join(clauses)} LIMIT 1",
            params,
        ).fetchone() is not None


def load_session_distance_frame(
    database_path: str | Path,
    selected_date: object,
    *,
    team_id: object | None = None,
    session_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[object] | None = None,
    athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Distance GPExe giornaliera, filtrata senza consultare Excel."""
    frame = load_pilot_distance_frame(database_path)
    target = pd.Timestamp(selected_date).normalize()
    frame = frame[pd.to_datetime(frame["Date"], errors="coerce").dt.normalize().eq(target)]
    if team_id not in (None, ""):
        frame = frame[frame["Team ID"].astype("string").eq(str(team_id))]
    selected_sessions = {str(value) for value in (session_ids or [])}
    if selected_sessions:
        frame = frame[frame["TeamSession ID"].astype("string").isin(selected_sessions)]
    selected_athlete_ids = {str(value) for value in (athlete_ids or [])}
    if selected_athlete_ids:
        frame = frame[frame["Athlete ID"].astype("string").isin(selected_athlete_ids)]
    elif athletes:
        normalized = {" ".join(str(value).upper().split()) for value in athletes}
        keys = frame["Athlete"].map(lambda value: " ".join(str(value).upper().split()))
        frame = frame[keys.isin(normalized)]
    return frame.reset_index(drop=True)


def load_session_relative_distance_frame(
    database_path: str | Path, selected_date: object, *, team_id: object | None = None,
    session_ids: Iterable[int] | None = None, athlete_ids: Iterable[object] | None = None,
    athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Relative Distance GPExe dal catalogo e da PAS Connect, senza fallback Excel."""
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"Database PAS Connect non trovato: {path}")
    with sqlite3.connect(path) as connection:
        catalog = connection.execute(
            """SELECT provider_metric_name FROM pas_metric_catalog
               WHERE provider='GPExe' AND active=1 AND requires_profile=0
                 AND lower(canonical_metric) IN ('relative distance', 'avg speed')
               ORDER BY CASE lower(canonical_metric) WHEN 'relative distance' THEN 0 ELSE 1 END, id
               LIMIT 1"""
        ).fetchone()
        if catalog is None:
            return pd.DataFrame(columns=["Date", "Athlete", "Relative Distance (m/min)",
                                         "TeamSession ID", "AthleteSession ID", "Athlete ID",
                                         "Team ID", "Source"])
        provider_name = str(catalog[0] or "").strip().casefold()
        aliases = {provider_name, provider_name.replace(" (m/min)", ""), "average_v", "avg speed"}
        placeholders = ",".join("?" for _ in aliases)
        sql = f"""SELECT s.start_timestamp Date,
          COALESCE(
              NULLIF(TRIM(COALESCE(a.first_name, '') || ' ' || COALESCE(a.last_name, '')), ''),
              NULLIF(TRIM(a.player_name), ''),
              'GPExe Athlete ' || d.provider_player_id
          ) Athlete,
          d.provider_player_id athlete_id, k.value metric_value, k.uom metric_uom,
          d.provider_session_id team_session_id, s.team_id team_id,
          d.provider_athlete_session_id athlete_session_id
          FROM gpexe_athlete_session_kpis k
          JOIN gpexe_athlete_session_details d ON d.provider_athlete_session_id=k.provider_athlete_session_id
          JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
          LEFT JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
          WHERE lower(k.name) IN ({placeholders})
          ORDER BY d.provider_athlete_session_id,
                   CASE k.source WHEN 'identifierKpi' THEN 0 ELSE 1 END, k.position"""
        frame = pd.read_sql_query(sql, connection, params=tuple(aliases))
    columns = ["Date", "Athlete", "Relative Distance (m/min)", "TeamSession ID",
               "AthleteSession ID", "Athlete ID", "Team ID", "Source"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    frame = frame.drop_duplicates("athlete_session_id", keep="first")
    result = pd.DataFrame({"Date": pd.to_datetime(frame["Date"], errors="coerce"),
        "Athlete": frame["Athlete"].astype("string").str.strip(),
        "Relative Distance (m/min)": pd.to_numeric(frame["metric_value"], errors="coerce"),
        "TeamSession ID": frame["team_session_id"], "AthleteSession ID": frame["athlete_session_id"],
        "Athlete ID": frame["athlete_id"], "Team ID": frame["team_id"], "Source": "GPExe"})
    target = pd.Timestamp(selected_date).normalize()
    result = result[pd.to_datetime(result["Date"], errors="coerce").dt.normalize().eq(target)]
    if team_id not in (None, ""):
        result = result[result["Team ID"].astype("string").eq(str(team_id))]
    selected_sessions = {str(v) for v in (session_ids or [])}
    if selected_sessions:
        result = result[result["TeamSession ID"].astype("string").isin(selected_sessions)]
    selected_ids = {str(v) for v in (athlete_ids or [])}
    if selected_ids:
        result = result[result["Athlete ID"].astype("string").isin(selected_ids)]
    elif athletes:
        selected_names = {" ".join(str(v).upper().split()) for v in athletes}
        result = result[result["Athlete"].map(lambda v: " ".join(str(v).upper().split())).isin(selected_names)]
    return result.dropna(subset=["Date", "Athlete", "Relative Distance (m/min)"]).reset_index(drop=True)


def load_pas_performance_frame(
    database_path: str | Path,
    *,
    session_ids: Iterable[int] | None = None,
) -> pd.DataFrame:
    """Legge le sessioni sincronizzate e restituisce le colonne consumate dal PAS Core."""
    path = Path(database_path)
    if not path.is_file():
        raise FileNotFoundError(f"Database PAS Connect non trovato: {path}")
    selected = tuple(sorted({int(value) for value in (session_ids or [])}))
    where = ""
    params: tuple[object, ...] = ()
    if selected:
        placeholders = ",".join("?" for _ in selected)
        where = f"WHERE r.provider_session_id IN ({placeholders})"
        params = selected
    sql = f"""
        SELECT r.provider_session_id, r.provider_athlete_session_id,
               r.athlete_first_name, r.athlete_last_name, r.athlete_role,
               p.player_name,
               r.state AS athlete_state, r.metrics_json,
               s.session_name, s.start_timestamp, s.end_timestamp, s.total_time,
               s.category_id, s.state AS session_state, s.team_id,
               d.category_name,
               a.provider_player_id, a.starter, a.duration,
               a.metrics_json AS detail_metrics_json, 'GPExe' AS source
        FROM gpexe_session_athlete_rows r
        JOIN gpexe_team_sessions s ON s.provider_session_id=r.provider_session_id
        LEFT JOIN gpexe_team_session_details d ON d.provider_session_id=r.provider_session_id
        LEFT JOIN gpexe_athlete_session_details a
          ON a.provider_athlete_session_id=r.provider_athlete_session_id
        LEFT JOIN gpexe_athletes p
          ON p.provider_player_id=a.provider_player_id
        {where}
        ORDER BY s.start_timestamp, r.athlete_last_name, r.athlete_first_name
    """
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = list(connection.execute(sql, params).fetchall())
        rest_where = where.replace("r.provider_session_id", "a.provider_session_id")
        rest_rows = connection.execute(
            f"""SELECT a.provider_session_id, a.provider_athlete_session_id,
                p.first_name AS athlete_first_name, p.last_name AS athlete_last_name,
                p.player_name,
                '' AS athlete_role, a.state AS athlete_state, '{{}}' AS metrics_json,
                s.session_name, s.start_timestamp, s.end_timestamp, s.total_time,
                s.category_id, s.state AS session_state, s.team_id,
                d.category_name, a.provider_player_id, a.starter, a.duration,
                a.metrics_json AS detail_metrics_json, 'GPExe' AS source
            FROM gpexe_athlete_session_details a
            JOIN gpexe_team_sessions s ON s.provider_session_id=a.provider_session_id
            LEFT JOIN gpexe_team_session_details d
              ON d.provider_session_id=a.provider_session_id
            LEFT JOIN gpexe_athletes p
              ON p.provider_player_id=a.provider_player_id
            WHERE NOT EXISTS (
                SELECT 1 FROM gpexe_session_athlete_rows r
                WHERE r.provider_session_id=a.provider_session_id
                  AND r.provider_athlete_session_id=a.provider_athlete_session_id
            )
            {('AND ' + rest_where.removeprefix('WHERE ')) if rest_where else ''}
            AND EXISTS (
                SELECT 1 FROM gpexe_athlete_session_kpis k
                WHERE k.provider_athlete_session_id=a.provider_athlete_session_id
                  AND k.source IN ('rest_v2', 'identifierKpi', 'kpi')
            )
            ORDER BY s.start_timestamp, a.provider_athlete_session_id""",
            params,
        ).fetchall()
        rows.extend(rest_rows)
        athlete_session_ids = tuple({int(row["provider_athlete_session_id"]) for row in rows})
        kpis_by_athlete_session: dict[int, list[dict[str, object]]] = {
            athlete_session_id: [] for athlete_session_id in athlete_session_ids
        }
        if athlete_session_ids:
            placeholders = ",".join("?" for _ in athlete_session_ids)
            kpi_rows = connection.execute(
                f"""SELECT provider_athlete_session_id, source, position, name, value,
                    kpi_group, uom, unit, raw_json
                FROM gpexe_athlete_session_kpis
                WHERE provider_athlete_session_id IN ({placeholders})
                  AND source IN ('rest_v2', 'identifierKpi', 'kpi')
                ORDER BY provider_athlete_session_id, source, position""",
                athlete_session_ids,
            ).fetchall()
            for kpi in kpi_rows:
                kpis_by_athlete_session[int(kpi["provider_athlete_session_id"])].append(dict(kpi))
    records: list[dict[str, object]] = []
    warnings: list[str] = []
    for row in rows:
        raw_metrics = json.loads(row["metrics_json"] or "{}")
        detail_metrics = json.loads(row["detail_metrics_json"] or "{}")
        combined = {**raw_metrics, **detail_metrics}
        mapped = map_gpexe_metrics(combined, require_core=False)
        descriptors = resolve_scalar_metrics(
            kpis_by_athlete_session.get(int(row["provider_athlete_session_id"]), ())
        )
        for canonical, descriptor in descriptors.items():
            mapped[_SCALAR_SPEC_BY_CANONICAL[canonical].pas_column] = descriptor_pas_value(descriptor)
        if mapped.get("distance (m)") is None:
            warnings.append(f"Athlete Session {row['provider_athlete_session_id']}: Distance assente")
            continue
        start = pd.to_datetime(row["start_timestamp"], errors="coerce")
        full_name = (
            f"{row['athlete_first_name'] or ''} {row['athlete_last_name'] or ''}"
        ).strip()
        athlete = (
            full_name
            or str(row["player_name"] or "").strip()
            or f"GPExe Athlete {row['provider_player_id']}"
        ).upper()
        record: dict[str, object] = {
            "Date": start.normalize() if pd.notna(start) else pd.NaT,
            "Athlete": athlete,
            "Drill": str(row["category_name"] or row["session_name"] or "GPExe Session").strip().title(),
            "Season Phase": "In Season",
            "Cycle": "",
            "Length Cycle": pd.NA,
            "Match Day +/-": "",
            "MD+": "",
            "MD-": "",
            "Role": str(row["athlete_role"] or "").strip(),
            "Time of Day": start.strftime("%H:%M") if pd.notna(start) else "",
            "Type Session": str(row["session_state"] or "").strip(),
            "Starters / No Starters": "S" if bool(row["starter"]) else "NS",
            "Duration (dec)": _duration_minutes(row["duration"] or row["total_time"]),
            "Anaerobic threshold zone (hh:mm:ss)": pd.NA,
            "High intensity training (hh:mm:ss)": pd.NA,
            "RPE (CR10)": pd.NA,
            "Athlete ID": row["provider_player_id"],
            "Team ID": row["team_id"],
            "Source": row["source"],
            "GPExe TeamSession ID": int(row["provider_session_id"]),
            "GPExe AthleteSession ID": int(row["provider_athlete_session_id"]),
            "GPExe KPI Provenance": {
                canonical: dict(descriptor.provenance or {})
                for canonical, descriptor in descriptors.items()
            },
        }
        record.update(mapped)
        records.append(record)
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("Le sessioni GPExe sincronizzate non contengono righe prestative utilizzabili.")
    for metric in CANONICAL_METRICS:
        if metric.pas_column not in frame:
            frame[metric.pas_column] = pd.NA
    frame = frame.sort_values(["Date", "Athlete"]).reset_index(drop=True)
    frame.attrs.update({
        "source_name": path.name,
        "sheet_name": "GPExe API",
        "gpexe_session_ids": selected,
        "gpexe_warnings": tuple(warnings),
        "gpexe_rows_read": len(rows),
        "gpexe_rows_rejected": len(warnings),
    })
    return frame
