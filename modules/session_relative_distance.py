"""Percorso operativo della metrica Relative Distance (m/min)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

from modules.session_distance import (
    MISSING_DAY_MESSAGE, TOTAL_SESSION_DRILLS, UNSUPPORTED_DRILL_MESSAGE,
    SessionDistanceError, normalize_athlete_name,
)
from pas_connect.pas_bridge import load_session_relative_distance_frame, session_exists_on_date

MISSING_RELATIVE_DISTANCE_MESSAGE = (
    "La sessione GPExe non contiene una metrica Relative Distance utilizzabile."
)


def _aggregate(frame: pd.DataFrame) -> pd.DataFrame:
    columns = ["Date", "Athlete", "Athlete ID", "Relative Distance (m/min)",
               "TeamSession ID", "Team ID", "Source"]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    data = frame.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce").dt.normalize()
    data["Athlete"] = data["Athlete"].map(normalize_athlete_name)
    data["Relative Distance (m/min)"] = pd.to_numeric(
        data["Relative Distance (m/min)"], errors="coerce"
    )
    if "Athlete ID" not in data:
        data["Athlete ID"] = pd.NA
    data["athlete_key"] = data.apply(
        lambda row: f"id:{row['Athlete ID']}" if pd.notna(row["Athlete ID"])
        and str(row["Athlete ID"]).strip() else f"name:{row['Athlete']}", axis=1,
    )
    for column in ("TeamSession ID", "Team ID", "Source"):
        if column not in data:
            data[column] = pd.NA
    grouped = data.dropna(subset=["Date", "Athlete", "Relative Distance (m/min)"]).groupby(
        ["Date", "athlete_key"], as_index=False
    ).agg({"Athlete": "first", "Athlete ID": "first",
           "Relative Distance (m/min)": "mean",
           "TeamSession ID": lambda values: ",".join(sorted({str(v) for v in values.dropna()})),
           "Team ID": "first", "Source": "first"})
    return grouped.drop(columns="athlete_key").reindex(columns=columns)


def load_excel_operational_relative_distance(
    frame: pd.DataFrame, selected_date: object, *, athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    required = {"Date", "Athlete", "avg speed (m/min)"}
    missing = required.difference(frame.columns)
    if missing:
        raise SessionDistanceError("La sorgente Excel non contiene Relative Distance.")
    data = frame.loc[:, list(required)].rename(
        columns={"avg speed (m/min)": "Relative Distance (m/min)"}
    )
    data["Athlete ID"] = pd.NA
    data["TeamSession ID"] = pd.NA
    data["Team ID"] = pd.NA
    data["Source"] = "Excel"
    data = data[pd.to_datetime(data["Date"], errors="coerce").dt.normalize().eq(
        pd.Timestamp(selected_date).normalize()
    )]
    if athletes:
        selected = {normalize_athlete_name(v) for v in athletes}
        data = data[data["Athlete"].map(normalize_athlete_name).isin(selected)]
    return _aggregate(data)


def load_gpexe_operational_relative_distance(
    database_path: str | Path, selected_date: object, *, drill: str = "Totale sessione",
    team_id: object | None = None, session_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[object] | None = None, athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    if drill not in TOTAL_SESSION_DRILLS:
        raise SessionDistanceError(UNSUPPORTED_DRILL_MESSAGE)
    if not session_exists_on_date(database_path, selected_date, team_id=team_id, session_ids=session_ids):
        raise SessionDistanceError(MISSING_DAY_MESSAGE)
    frame = load_session_relative_distance_frame(
        database_path, selected_date, team_id=team_id, session_ids=session_ids,
        athlete_ids=athlete_ids, athletes=athletes,
    )
    if frame.empty:
        raise SessionDistanceError(MISSING_RELATIVE_DISTANCE_MESSAGE)
    return _aggregate(frame)
