"""PAS Load Index (PLI) basato sul modello prestativo individuale di gara."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd

from modules.config import METRICS


PLI_COMPONENTS: dict[str, tuple[str, ...]] = {
    "Volume": ("Distance (m)", "Duration (min)"),
    "Alta velocità": ("Distance 19.8-25.2 km/h (m)",),
    "Sprint": ("Distance >25.2 km/h (m)", "Speed Events (n°)"),
    "Componente neuromuscolare": ("Acc Events (n°)", "Dec Events (n°)"),
    "Velocità massima": ("Max Speed (km/h)", "% Max Speed individuale"),
    "Carico interno": ("RPE",),
}

RPE_MATCH_REFERENCE = 8.0
DURATION_MATCH_REFERENCE = 90.0


@dataclass(frozen=True)
class PLIResult:
    player_scores: pd.DataFrame
    component_long: pd.DataFrame
    metric_long: pd.DataFrame
    references: pd.DataFrame


def _remove_outliers(values: pd.Series) -> pd.Series:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if len(clean) < 3:
        return clean
    mean = float(clean.mean())
    sd = float(clean.std(ddof=0))
    if sd <= 0:
        return clean
    return clean[clean.between(mean - 2 * sd, mean + 2 * sd)]


def _aggregate_player_day(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    work = frame.copy()
    work["Date"] = pd.to_datetime(work["Date"], errors="coerce").dt.normalize()
    aggregations: dict[str, str] = {}
    for metric, meta in METRICS.items():
        column = meta["column"]
        if column in work.columns:
            work[column] = pd.to_numeric(work[column], errors="coerce")
            aggregations[column] = meta.get("aggregation", "sum")
    if not aggregations:
        return pd.DataFrame()
    return work.groupby(["Athlete", "Date"], as_index=False).agg(aggregations)


def build_individual_match_references(data: pd.DataFrame) -> pd.DataFrame:
    """Costruisce il modello gara individuale per tutte le metriche PLI.

    Le metriche additive sono normalizzate per minuto e proiettate a 90 minuti.
    Duration è fissata a 90 minuti e RPE a 8. Max Speed usa la media gara.
    La % Max Speed usa la media gara rispetto al massimo storico individuale.
    """
    if data.empty or "Drill" not in data.columns:
        return pd.DataFrame()
    match = data[data["Drill"].astype(str).str.strip().eq("Match")].copy()
    match_day = _aggregate_player_day(match)
    if match_day.empty:
        return pd.DataFrame()

    duration_col = METRICS["Duration (min)"]["column"]
    max_speed_col = METRICS["Max Speed (km/h)"]["column"]

    historical = data[["Athlete", max_speed_col]].copy() if max_speed_col in data.columns else pd.DataFrame()
    if not historical.empty:
        historical[max_speed_col] = pd.to_numeric(historical[max_speed_col], errors="coerce")
        historical = historical.groupby("Athlete", as_index=False)[max_speed_col].max().rename(columns={max_speed_col: "historical_max_speed"})

    reference_rows: list[dict[str, object]] = []
    additive_metrics = {
        "Distance (m)",
        "Distance 19.8-25.2 km/h (m)",
        "Distance >25.2 km/h (m)",
        "Acc Events (n°)",
        "Dec Events (n°)",
        "Speed Events (n°)",
    }

    for athlete, athlete_data in match_day.groupby("Athlete"):
        row: dict[str, object] = {"Athlete": athlete}
        durations = pd.to_numeric(athlete_data.get(duration_col), errors="coerce")
        for metric in additive_metrics:
            col = METRICS[metric]["column"]
            vals = pd.to_numeric(athlete_data.get(col), errors="coerce")
            valid = vals.notna() & durations.notna() & durations.gt(0)
            rates = _remove_outliers(vals.loc[valid] / durations.loc[valid])
            row[f"ref::{metric}"] = float(rates.mean()) * 90 if not rates.empty else np.nan

        max_vals = _remove_outliers(pd.to_numeric(athlete_data.get(max_speed_col), errors="coerce"))
        row["ref::Max Speed (km/h)"] = float(max_vals.mean()) if not max_vals.empty else np.nan
        row["ref::Duration (min)"] = DURATION_MATCH_REFERENCE
        row["ref::RPE"] = RPE_MATCH_REFERENCE

        historical_max = np.nan
        if not historical.empty:
            hist_row = historical[historical["Athlete"].astype(str).eq(str(athlete))]
            if not hist_row.empty:
                historical_max = float(hist_row.iloc[0]["historical_max_speed"])
        if historical_max and np.isfinite(historical_max) and historical_max > 0 and not max_vals.empty:
            match_pct = _remove_outliers(max_vals / historical_max * 100.0)
            row["ref::% Max Speed individuale"] = float(match_pct.mean()) if not match_pct.empty else np.nan
        else:
            row["ref::% Max Speed individuale"] = np.nan
        row["historical_max_speed"] = historical_max
        reference_rows.append(row)

    return pd.DataFrame(reference_rows)


def _current_metric_values(data: pd.DataFrame) -> pd.DataFrame:
    day = _aggregate_player_day(data)
    if day.empty:
        return pd.DataFrame()
    # La vista PLI rappresenta una singola seduta/periodo già filtrato: somma i giorni
    # per le metriche cumulative e mantiene max/media per le metriche non additive.
    agg: dict[str, tuple[str, str]] = {}
    for metric, meta in METRICS.items():
        col = meta["column"]
        if col not in day.columns:
            continue
        method = meta.get("accumulation", meta.get("aggregation", "sum"))
        agg[col] = (col, method)
    return day.groupby("Athlete", as_index=False).agg(**agg)


def calculate_pli(data: pd.DataFrame, reference_source: pd.DataFrame | None = None) -> PLIResult:
    """Calcola PLI e dettaglio componenti per i dati già filtrati dalla richiesta."""
    empty = PLIResult(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
    if data.empty:
        return empty
    references = build_individual_match_references(reference_source if reference_source is not None else data)
    current = _current_metric_values(data)
    if current.empty or references.empty:
        return empty
    merged = current.merge(references, on="Athlete", how="left")

    metric_rows: list[dict[str, object]] = []
    for _, row in merged.iterrows():
        athlete = str(row["Athlete"])
        historical_max = pd.to_numeric(pd.Series([row.get("historical_max_speed")]), errors="coerce").iloc[0]
        for metric in [m for components in PLI_COMPONENTS.values() for m in components]:
            if metric == "% Max Speed individuale":
                max_col = METRICS["Max Speed (km/h)"]["column"]
                current_value = pd.to_numeric(pd.Series([row.get(max_col)]), errors="coerce").iloc[0]
                value = current_value / historical_max * 100.0 if pd.notna(current_value) and pd.notna(historical_max) and historical_max > 0 else np.nan
            else:
                col = METRICS[metric]["column"]
                value = pd.to_numeric(pd.Series([row.get(col)]), errors="coerce").iloc[0]
            reference = pd.to_numeric(pd.Series([row.get(f"ref::{metric}")]), errors="coerce").iloc[0]
            pct = value / reference * 100.0 if pd.notna(value) and pd.notna(reference) and reference > 0 else np.nan
            metric_rows.append({
                "Athlete": athlete,
                "Metric": metric,
                "Value": value,
                "Reference": reference,
                "Percent": pct,
            })

    metric_long = pd.DataFrame(metric_rows)
    component_rows: list[dict[str, object]] = []
    for athlete, athlete_metrics in metric_long.groupby("Athlete"):
        for component, metrics in PLI_COMPONENTS.items():
            values = athlete_metrics[athlete_metrics["Metric"].isin(metrics)]["Percent"].dropna()
            component_rows.append({
                "Athlete": athlete,
                "Component": component,
                "Percent": float(values.mean()) if not values.empty else np.nan,
                "Metrics available": int(values.size),
                "Metrics expected": len(metrics),
            })
    component_long = pd.DataFrame(component_rows)
    player_scores = (
        component_long.groupby("Athlete", as_index=False)
        .agg(PLI=("Percent", "mean"), components_available=("Percent", "count"))
        .dropna(subset=["PLI"])
    )
    return PLIResult(player_scores, component_long, metric_long, references)
