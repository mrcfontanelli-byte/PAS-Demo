"""Confronto Excel/GPExe dedicato alla Relative Distance."""
from __future__ import annotations

import pandas as pd

from modules.bridge_validation import BridgeValidationResult, compare_distance_sources


def compare_relative_distance_sources(
    excel: pd.DataFrame,
    gpexe: pd.DataFrame,
    *,
    tolerance_m_min: float = 0.1,
) -> BridgeValidationResult:
    """Confronta Relative Distance senza modificare il confronto Distance."""
    if tolerance_m_min < 0:
        raise ValueError("La tolleranza Relative Distance non può essere negativa.")
    metric = "Relative Distance (m/min)"
    result = compare_distance_sources(
        excel.rename(columns={metric: "Distance (m)"}),
        gpexe.rename(columns={metric: "Distance (m)"}),
        tolerance_m=tolerance_m_min,
    )
    comparisons = result.comparisons.rename(columns={
        "Distance Excel": "Relative Distance Excel",
        "Distance GPExe": "Relative Distance GPExe",
    })
    left = set(excel.get("Athlete", pd.Series(dtype="string")).astype("string").str.strip().str.upper())
    right = set(gpexe.get("Athlete", pd.Series(dtype="string")).astype("string").str.strip().str.upper())
    summary = dict(result.summary)
    summary["atleti_solo_excel"] = len(left - right)
    summary["atleti_solo_gpexe"] = len(right - left)
    return BridgeValidationResult(comparisons, result.non_comparable_sessions, summary)
