"""Percorso operativo giornaliero della sola metrica Distance."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from pas_connect.metric_catalog import has_catalogued_distance
from pas_connect.pas_bridge import load_session_distance_frame, session_exists_on_date


MISSING_DAY_MESSAGE = "La giornata selezionata non è presente nel database PAS Connect."
MISSING_DISTANCE_MESSAGE = "La sessione GPExe non contiene una metrica Distance utilizzabile."
UNSUPPORTED_DRILL_MESSAGE = (
    "Il filtro Drill non è ancora disponibile per la sorgente GPExe. "
    "Seleziona il totale sessione oppure usa Excel."
)
TOTAL_SESSION_DRILLS = frozenset({"Totale sessione", "Full Training"})


class SessionDistanceError(ValueError):
    pass


def normalize_athlete_name(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def aggregate_session_distance(frame: pd.DataFrame) -> pd.DataFrame:
    """Somma più AthleteSession usando l'ID atleta quando disponibile."""
    columns = [
        "Date", "Athlete", "Athlete ID", "Distance (m)", "TeamSession ID", "Team ID", "Source",
    ]
    if frame.empty:
        return pd.DataFrame(columns=columns)
    data = frame.copy()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce").dt.normalize()
    data["Athlete"] = data["Athlete"].map(normalize_athlete_name)
    data["Distance (m)"] = pd.to_numeric(data["Distance (m)"], errors="coerce")
    if "Athlete ID" not in data:
        data["Athlete ID"] = pd.NA
    data["athlete_key"] = data.apply(
        lambda row: f"id:{row['Athlete ID']}" if pd.notna(row["Athlete ID"]) and str(row["Athlete ID"]).strip()
        else f"name:{row['Athlete']}", axis=1,
    )
    for column in ("TeamSession ID", "Team ID", "Source"):
        if column not in data:
            data[column] = pd.NA
    grouped = data.dropna(subset=["Date", "Athlete", "Distance (m)"]).groupby(
        ["Date", "athlete_key"], as_index=False,
    ).agg({
        "Athlete": "first", "Athlete ID": "first", "Distance (m)": "sum",
        "TeamSession ID": lambda values: ",".join(sorted({str(value) for value in values.dropna()})),
        "Team ID": "first", "Source": "first",
    })
    return grouped.drop(columns="athlete_key").reindex(columns=columns)


def load_gpexe_operational_distance(
    database_path: str | Path,
    selected_date: object,
    *,
    drill: str = "Totale sessione",
    team_id: object | None = None,
    session_ids: Iterable[int] | None = None,
    athlete_ids: Iterable[object] | None = None,
    athletes: Iterable[str] | None = None,
) -> pd.DataFrame:
    if drill not in TOTAL_SESSION_DRILLS:
        raise SessionDistanceError(UNSUPPORTED_DRILL_MESSAGE)
    if not session_exists_on_date(
        database_path, selected_date, team_id=team_id, session_ids=session_ids,
    ):
        raise SessionDistanceError(MISSING_DAY_MESSAGE)
    if not has_catalogued_distance(database_path):
        raise SessionDistanceError(MISSING_DISTANCE_MESSAGE)
    frame = load_session_distance_frame(
        database_path, selected_date, team_id=team_id, session_ids=session_ids,
        athlete_ids=athlete_ids, athletes=athletes,
    )
    if frame.empty:
        raise SessionDistanceError(MISSING_DISTANCE_MESSAGE)
    return aggregate_session_distance(frame)


@dataclass(frozen=True)
class SessionDistanceComparison:
    comparisons: pd.DataFrame
    excel_only: pd.DataFrame
    gpexe_only: pd.DataFrame


def compare_session_distance(
    excel: pd.DataFrame,
    gpexe: pd.DataFrame,
    *,
    tolerance_m: float = 0.1,
) -> SessionDistanceComparison:
    """Confronta una giornata usando gli ID quando presenti in entrambe le fonti."""
    if tolerance_m < 0:
        raise ValueError("La tolleranza Distance non può essere negativa.")
    left = aggregate_session_distance(excel)
    right = aggregate_session_distance(gpexe)
    ids_available = (
        not left.empty and not right.empty
        and left["Athlete ID"].notna().all() and right["Athlete ID"].notna().all()
    )
    if ids_available:
        left["match_key"] = left["Athlete ID"].astype(str)
        right["match_key"] = right["Athlete ID"].astype(str)
    else:
        left["match_key"] = left["Athlete"].map(normalize_athlete_name)
        right["match_key"] = right["Athlete"].map(normalize_athlete_name)
    merged = left.merge(right, on="match_key", how="inner", suffixes=(" Excel", " GPExe"))
    comparisons = pd.DataFrame({
        "Atleta": merged.get("Athlete Excel", pd.Series(dtype="string")),
        "Athlete ID": merged.get("Athlete ID GPExe", pd.Series(dtype="object")),
        "Distance Excel": merged.get("Distance (m) Excel", pd.Series(dtype=float)),
        "Distance GPExe": merged.get("Distance (m) GPExe", pd.Series(dtype=float)),
    })
    comparisons["Differenza assoluta"] = (
        comparisons["Distance Excel"] - comparisons["Distance GPExe"]
    ).abs()
    comparisons["Stato"] = comparisons["Differenza assoluta"].le(tolerance_m).map(
        {True: "OK", False: "DIFFERENTE"}
    )
    left_only = left[~left["match_key"].isin(right["match_key"])].drop(columns="match_key")
    right_only = right[~right["match_key"].isin(left["match_key"])].drop(columns="match_key")
    return SessionDistanceComparison(comparisons, left_only, right_only)
