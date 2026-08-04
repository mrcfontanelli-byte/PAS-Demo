"""Confronto interno Excel/GPExe per la metrica pilota Distance."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class BridgeValidationResult:
    comparisons: pd.DataFrame
    non_comparable_sessions: pd.DataFrame
    summary: dict[str, int]


def _prepare(frame: pd.DataFrame, source: str) -> pd.DataFrame:
    required = {"Date", "Athlete", "Distance (m)"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"Sorgente {source} priva di: {', '.join(missing)}")
    prepared = frame.copy()
    prepared["Date"] = pd.to_datetime(
        prepared["Date"], errors="coerce", format="mixed",
    ).dt.normalize()
    prepared["Athlete"] = prepared["Athlete"].astype("string").str.strip()
    prepared["athlete_key"] = prepared["Athlete"].str.upper()
    prepared["Distance (m)"] = pd.to_numeric(prepared["Distance (m)"], errors="coerce")
    if "TeamSession ID" not in prepared:
        prepared["TeamSession ID"] = pd.NA
    prepared["session_key"] = prepared["TeamSession ID"].map(
        lambda value: None if pd.isna(value) or str(value).strip() == "" else str(value).strip()
    )
    return prepared.dropna(subset=["Date", "Athlete", "Distance (m)"])


def compare_distance_sources(
    excel: pd.DataFrame,
    gpexe: pd.DataFrame,
    *,
    tolerance_m: float = 0.1,
) -> BridgeValidationResult:
    """Confronta solo sessioni e atleti presenti in entrambe le sorgenti."""
    if tolerance_m < 0:
        raise ValueError("La tolleranza Distance non può essere negativa.")
    excel_data = _prepare(excel, "Excel")
    gpexe_data = _prepare(gpexe, "GPExe")
    comparison_parts: list[pd.DataFrame] = []
    non_comparable: list[dict[str, object]] = []
    compared_sessions = 0

    all_dates = sorted(set(excel_data["Date"]).union(gpexe_data["Date"]))
    for session_date in all_dates:
        excel_day = excel_data[excel_data["Date"].eq(session_date)]
        gpexe_day = gpexe_data[gpexe_data["Date"].eq(session_date)]
        if excel_day.empty or gpexe_day.empty:
            source = "GPExe" if excel_day.empty else "Excel"
            available = gpexe_day if excel_day.empty else excel_day
            ids = sorted(set(available["session_key"].dropna())) or [None]
            non_comparable.extend({
                "Data": session_date,
                "TeamSession ID": session_id,
                "Presente solo in": source,
                "Motivo": "Seduta assente nell'altra sorgente",
            } for session_id in ids)
            continue

        excel_ids = set(excel_day["session_key"].dropna())
        gpexe_ids = set(gpexe_day["session_key"].dropna())
        if excel_ids and gpexe_ids:
            pairs = [
                (
                    session_id,
                    excel_day[excel_day["session_key"].eq(session_id)],
                    gpexe_day[gpexe_day["session_key"].eq(session_id)],
                )
                for session_id in sorted(excel_ids.intersection(gpexe_ids))
            ]
            for session_id in sorted(excel_ids - gpexe_ids):
                non_comparable.append({
                    "Data": session_date, "TeamSession ID": session_id,
                    "Presente solo in": "Excel", "Motivo": "TeamSession assente in GPExe",
                })
            for session_id in sorted(gpexe_ids - excel_ids):
                non_comparable.append({
                    "Data": session_date, "TeamSession ID": session_id,
                    "Presente solo in": "GPExe", "Motivo": "TeamSession assente in Excel",
                })
        else:
            pairs = [(None, excel_day, gpexe_day)]

        for session_id, excel_session, gpexe_session in pairs:
            compared_sessions += 1
            excel_athletes = excel_session.groupby("athlete_key", as_index=False).agg(
                Atleta=("Athlete", "first"),
                **{"Distance Excel": ("Distance (m)", "sum")},
            )
            gpexe_athletes = gpexe_session.groupby("athlete_key", as_index=False).agg(
                **{"Distance GPExe": ("Distance (m)", "sum")},
            )
            comparison = excel_athletes.merge(gpexe_athletes, on="athlete_key", how="inner")
            if comparison.empty:
                continue
            comparison.insert(0, "Data", session_date)
            comparison.insert(1, "TeamSession ID", session_id)
            comparison["Differenza assoluta"] = (
                comparison["Distance Excel"] - comparison["Distance GPExe"]
            ).abs()
            comparison["Stato"] = comparison["Differenza assoluta"].le(tolerance_m).map(
                {True: "OK", False: "DIFFERENTE"}
            )
            comparison_parts.append(comparison.drop(columns=["athlete_key"]))

    comparison_columns = [
        "Data", "TeamSession ID", "Atleta", "Distance Excel", "Distance GPExe",
        "Differenza assoluta", "Stato",
    ]
    comparisons = (
        pd.concat(comparison_parts, ignore_index=True)
        if comparison_parts else pd.DataFrame(columns=comparison_columns)
    )
    non_comparable_frame = pd.DataFrame(non_comparable, columns=[
        "Data", "TeamSession ID", "Presente solo in", "Motivo",
    ])
    summary = {
        "sedute_confrontate": compared_sessions,
        "atleti_confrontati": len(comparisons),
        "atleti_coincidenti": int(comparisons["Stato"].eq("OK").sum()),
        "atleti_differenti": int(comparisons["Stato"].eq("DIFFERENTE").sum()),
    }
    return BridgeValidationResult(comparisons, non_comparable_frame, summary)
