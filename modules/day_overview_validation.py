"""Validazione giornaliera multi-metrica Excel/GPExe."""
from __future__ import annotations

import pandas as pd

from modules.day_overview_provider import OVERVIEW_METRICS
from modules.session_distance import normalize_athlete_name


def compare_overview_metric(
    excel: pd.DataFrame, gpexe: pd.DataFrame, metric_name: str, *, tolerance: float = 0.1,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if tolerance < 0:
        raise ValueError("La tolleranza non può essere negativa.")
    metric = next((item for item in OVERVIEW_METRICS if item.display == metric_name), None)
    if metric is None:
        raise ValueError(f"Metrica Panoramica non riconosciuta: {metric_name}")
    column = metric.column
    if column not in excel or column not in gpexe:
        raise ValueError(f"Metrica {metric_name} non disponibile in entrambe le sorgenti.")
    left = excel.loc[:, ["Athlete", column]].copy()
    right = gpexe.loc[:, ["Athlete", column]].copy()
    left["key"] = left["Athlete"].map(normalize_athlete_name)
    right["key"] = right["Athlete"].map(normalize_athlete_name)
    left[column] = pd.to_numeric(left[column], errors="coerce")
    right[column] = pd.to_numeric(right[column], errors="coerce")
    if metric.canonical == "Duration":
        left[column] *= 60.0
        if "Duration (s)" in gpexe:
            right[column] = pd.to_numeric(gpexe["Duration (s)"], errors="coerce")
    aggregate = metric.aggregation
    left = left.dropna(subset=[column]).groupby("key", as_index=False).agg(
        Atleta=("Athlete", "first"), Excel=(column, aggregate)
    )
    right = right.dropna(subset=[column]).groupby("key", as_index=False).agg(
        GPExe=(column, aggregate)
    )
    merged = left.merge(right, on="key", how="outer", indicator=True)
    compared = merged[merged["_merge"].eq("both")].copy()
    compared["Differenza assoluta"] = (compared["Excel"] - compared["GPExe"]).abs()
    compared["Stato"] = compared["Differenza assoluta"].le(tolerance).map(
        {True: "OK", False: "DIFFERENTE"}
    )
    comparison_label = "Duration (s)" if metric.canonical == "Duration" else metric_name
    compared = compared.rename(columns={
        "Excel": f"{comparison_label} Excel", "GPExe": f"{comparison_label} GPExe"
    })
    summary = {"atleti_confrontati": len(compared),
               "atleti_coincidenti": int(compared["Stato"].eq("OK").sum()),
               "atleti_differenti": int(compared["Stato"].eq("DIFFERENTE").sum()),
               "atleti_solo_excel": int(merged["_merge"].eq("left_only").sum()),
               "atleti_solo_gpexe": int(merged["_merge"].eq("right_only").sum()),
               "tolleranza": tolerance, "unita": metric.unit}
    return compared.drop(columns=["key", "_merge"]), summary
