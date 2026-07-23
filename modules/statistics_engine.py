from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import percentileofscore


def descriptive_statistics(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "mean": np.nan, "median": np.nan, "sd": np.nan, "cv": np.nan,
            "min": np.nan, "max": np.nan, "p25": np.nan, "p75": np.nan,
            "count": 0,
        }

    mean = float(clean.mean())
    sd = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    cv = (sd / mean * 100.0) if mean != 0 else np.nan

    return {
        "mean": mean,
        "median": float(clean.median()),
        "sd": sd,
        "cv": cv,
        "min": float(clean.min()),
        "max": float(clean.max()),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
        "count": int(clean.count()),
    }


def value_against_reference(value: float, reference: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(reference, errors="coerce").dropna()
    stats = descriptive_statistics(clean)

    if pd.isna(value) or clean.empty:
        return {"difference_pct": np.nan, "z_score": np.nan, "percentile": np.nan}

    mean = stats["mean"]
    sd = stats["sd"]
    difference_pct = ((value - mean) / mean * 100.0) if mean != 0 else np.nan
    z_score = ((value - mean) / sd) if sd not in (0, np.nan) and not pd.isna(sd) else 0.0
    percentile = float(percentileofscore(clean, value, kind="weak"))

    return {
        "difference_pct": difference_pct,
        "z_score": z_score,
        "percentile": percentile,
    }
