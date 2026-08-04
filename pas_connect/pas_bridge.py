"""Conversione del database PAS Connect GPExe nello schema prestativo PAS."""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Iterable

import pandas as pd

from modules.data_mapping import map_gpexe_metrics


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


def available_sessions(database_path: str | Path) -> list[dict[str, object]]:
    path = Path(database_path)
    if not path.is_file():
        return []
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT provider_session_id, session_name, start_timestamp, team_id, state
               FROM gpexe_team_sessions
               ORDER BY start_timestamp DESC, provider_session_id DESC"""
        ).fetchall()
    return [dict(row) for row in rows]


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
               r.state AS athlete_state, r.metrics_json,
               s.session_name, s.start_timestamp, s.end_timestamp, s.total_time,
               s.category_id, s.state AS session_state,
               d.category_name,
               a.starter, a.duration, a.metrics_json AS detail_metrics_json
        FROM gpexe_session_athlete_rows r
        JOIN gpexe_team_sessions s ON s.provider_session_id=r.provider_session_id
        LEFT JOIN gpexe_team_session_details d ON d.provider_session_id=r.provider_session_id
        LEFT JOIN gpexe_athlete_session_details a
          ON a.provider_athlete_session_id=r.provider_athlete_session_id
        {where}
        ORDER BY s.start_timestamp, r.athlete_last_name, r.athlete_first_name
    """
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(sql, params).fetchall()
    records: list[dict[str, object]] = []
    warnings: list[str] = []
    for row in rows:
        raw_metrics = json.loads(row["metrics_json"] or "{}")
        detail_metrics = json.loads(row["detail_metrics_json"] or "{}")
        combined = {**raw_metrics, **detail_metrics}
        mapped = map_gpexe_metrics(combined, require_core=False)
        if mapped.get("distance (m)") is None:
            warnings.append(f"Athlete Session {row['provider_athlete_session_id']}: Distance assente")
            continue
        start = pd.to_datetime(row["start_timestamp"], errors="coerce")
        athlete = f"{row['athlete_first_name'] or ''} {row['athlete_last_name'] or ''}".strip().upper()
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
            "GPExe TeamSession ID": int(row["provider_session_id"]),
            "GPExe AthleteSession ID": int(row["provider_athlete_session_id"]),
        }
        record.update(mapped)
        records.append(record)
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError("Le sessioni GPExe sincronizzate non contengono righe prestative utilizzabili.")
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
