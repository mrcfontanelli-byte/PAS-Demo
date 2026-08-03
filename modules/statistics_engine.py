from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import percentileofscore


def descriptive_statistics(values: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            "mean": np.nan, "median": np.nan, "sd": np.nan, "se": np.nan,
            "cv": np.nan, "min": np.nan, "max": np.nan, "p25": np.nan,
            "p75": np.nan, "ci_low": np.nan, "ci_high": np.nan, "count": 0,
        }

    mean = float(clean.mean())
    sd = float(clean.std(ddof=1)) if len(clean) > 1 else 0.0
    se = sd / sqrt(len(clean)) if len(clean) > 0 else np.nan
    cv = (sd / mean * 100.0) if mean != 0 else np.nan
    if len(clean) > 1:
        critical = float(stats.t.ppf(0.975, df=len(clean) - 1))
        ci_low, ci_high = mean - critical * se, mean + critical * se
    else:
        ci_low = ci_high = mean

    return {
        "mean": mean,
        "median": float(clean.median()),
        "sd": sd,
        "se": se,
        "cv": cv,
        "min": float(clean.min()),
        "max": float(clean.max()),
        "p25": float(clean.quantile(0.25)),
        "p75": float(clean.quantile(0.75)),
        "ci_low": float(ci_low),
        "ci_high": float(ci_high),
        "count": int(clean.count()),
    }


def value_against_reference(value: float, reference: pd.Series) -> dict[str, float]:
    clean = pd.to_numeric(reference, errors="coerce").dropna()
    summary = descriptive_statistics(clean)

    if pd.isna(value) or clean.empty:
        return {"difference_pct": np.nan, "z_score": np.nan, "percentile": np.nan}

    mean = summary["mean"]
    sd = summary["sd"]
    difference_pct = ((value - mean) / mean * 100.0) if mean != 0 else np.nan
    z_score = ((value - mean) / sd) if sd and not pd.isna(sd) else 0.0
    percentile = float(percentileofscore(clean, value, kind="weak"))
    return {"difference_pct": difference_pct, "z_score": z_score, "percentile": percentile}


def _clean(values: pd.Series) -> np.ndarray:
    return pd.to_numeric(values, errors="coerce").dropna().to_numpy(dtype=float)


def shapiro_result(values: pd.Series) -> dict[str, float | str]:
    clean = _clean(values)
    if clean.size < 3:
        return {"statistic": np.nan, "p_value": np.nan, "status": "N insufficiente"}
    sample = clean[:5000]
    statistic, p_value = stats.shapiro(sample)
    status = "Compatibile con normalità" if p_value >= 0.05 else "Non normale"
    return {"statistic": float(statistic), "p_value": float(p_value), "status": status}


def _cohens_d(a: np.ndarray, b: np.ndarray) -> float:
    if a.size < 2 or b.size < 2:
        return np.nan
    pooled_df = a.size + b.size - 2
    if pooled_df <= 0:
        return np.nan
    pooled_sd = sqrt(((a.size - 1) * np.var(a, ddof=1) + (b.size - 1) * np.var(b, ddof=1)) / pooled_df)
    return float((np.mean(a) - np.mean(b)) / pooled_sd) if pooled_sd else 0.0


def _hedges_g(d: float, n_a: int, n_b: int) -> float:
    if pd.isna(d):
        return np.nan
    df = n_a + n_b - 2
    correction = 1 - (3 / (4 * df - 1)) if df > 1 else 1.0
    return float(d * correction)


def effect_magnitude(value: float) -> str:
    if pd.isna(value):
        return "N/D"
    absolute = abs(float(value))
    if absolute < 0.2:
        return "Trascurabile"
    if absolute < 0.5:
        return "Piccolo"
    if absolute < 0.8:
        return "Moderato"
    return "Grande"


def compare_independent_groups(a_values: pd.Series, b_values: pd.Series) -> dict[str, float | str]:
    a = _clean(a_values)
    b = _clean(b_values)
    if a.size < 2 or b.size < 2:
        return {
            "test": "Dati insufficienti", "statistic": np.nan, "p_value": np.nan,
            "effect_size": np.nan, "effect_name": "N/D", "effect_magnitude": "N/D",
            "normal_a": np.nan, "normal_b": np.nan,
        }

    normal_a = shapiro_result(pd.Series(a))["p_value"]
    normal_b = shapiro_result(pd.Series(b))["p_value"]
    both_normal = bool(pd.notna(normal_a) and pd.notna(normal_b) and normal_a >= 0.05 and normal_b >= 0.05)

    if both_normal:
        levene_p = float(stats.levene(a, b, center="median").pvalue)
        equal_var = levene_p >= 0.05
        statistic, p_value = stats.ttest_ind(a, b, equal_var=equal_var, nan_policy="omit")
        d = _cohens_d(a, b)
        effect = _hedges_g(d, a.size, b.size)
        test_name = "Independent samples t-test" if equal_var else "Welch t-test"
        effect_name = "Hedges g"
    else:
        statistic, p_value = stats.mannwhitneyu(a, b, alternative="two-sided")
        effect = 1 - (2 * float(statistic)) / (a.size * b.size)
        test_name = "Mann–Whitney U"
        effect_name = "Rank-biserial r"

    return {
        "test": test_name,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "effect_size": float(effect),
        "effect_name": effect_name,
        "effect_magnitude": effect_magnitude(float(effect)),
        "normal_a": float(normal_a) if pd.notna(normal_a) else np.nan,
        "normal_b": float(normal_b) if pd.notna(normal_b) else np.nan,
    }


def correlation_analysis(x_values: pd.Series, y_values: pd.Series) -> dict[str, float | str]:
    frame = pd.DataFrame({"x": pd.to_numeric(x_values, errors="coerce"), "y": pd.to_numeric(y_values, errors="coerce")}).dropna()
    if len(frame) < 3:
        return {"test": "Dati insufficienti", "coefficient": np.nan, "p_value": np.nan, "magnitude": "N/D"}
    x, y = frame["x"], frame["y"]
    nx, ny = shapiro_result(x)["p_value"], shapiro_result(y)["p_value"]
    if pd.notna(nx) and pd.notna(ny) and nx >= 0.05 and ny >= 0.05:
        coefficient, p_value = stats.pearsonr(x, y)
        test_name = "Pearson r"
    else:
        coefficient, p_value = stats.spearmanr(x, y)
        test_name = "Spearman ρ"
    absolute = abs(float(coefficient))
    magnitude = "Trascurabile" if absolute < 0.1 else "Piccola" if absolute < 0.3 else "Moderata" if absolute < 0.5 else "Grande"
    return {"test": test_name, "coefficient": float(coefficient), "p_value": float(p_value), "magnitude": magnitude}


def compare_multiple_groups(values: pd.Series, groups: pd.Series) -> dict[str, float | str | int]:
    """Confronto automatico fra almeno tre gruppi indipendenti.

    Usa ANOVA a una via quando tutti i gruppi sono compatibili con normalità e
    presentano varianze omogenee; in caso contrario usa Kruskal–Wallis.
    """
    frame = pd.DataFrame({
        "value": pd.to_numeric(values, errors="coerce"),
        "group": groups.astype("string"),
    }).dropna()
    samples = [part["value"].to_numpy(dtype=float) for _, part in frame.groupby("group", sort=False)]
    samples = [sample for sample in samples if sample.size >= 2]
    if len(samples) < 3:
        return {
            "test": "Dati insufficienti", "statistic": np.nan, "p_value": np.nan,
            "effect_size": np.nan, "effect_name": "N/D", "effect_magnitude": "N/D",
            "groups": len(samples),
        }

    normal_ps = [shapiro_result(pd.Series(sample))["p_value"] for sample in samples]
    all_normal = all(pd.notna(p) and p >= 0.05 for p in normal_ps)
    levene_p = float(stats.levene(*samples, center="median").pvalue)

    if all_normal and levene_p >= 0.05:
        statistic, p_value = stats.f_oneway(*samples)
        grand_mean = frame["value"].mean()
        ss_between = sum(len(sample) * (sample.mean() - grand_mean) ** 2 for sample in samples)
        ss_total = float(((frame["value"] - grand_mean) ** 2).sum())
        effect = float(ss_between / ss_total) if ss_total else 0.0
        test_name = "One-way ANOVA"
        effect_name = "Eta squared"
    else:
        statistic, p_value = stats.kruskal(*samples)
        n = len(frame)
        k = len(samples)
        effect = float(max(0.0, (float(statistic) - k + 1) / (n - k))) if n > k else np.nan
        test_name = "Kruskal–Wallis"
        effect_name = "Epsilon squared"

    return {
        "test": test_name,
        "statistic": float(statistic),
        "p_value": float(p_value),
        "effect_size": effect,
        "effect_name": effect_name,
        "effect_magnitude": effect_magnitude(effect),
        "groups": len(samples),
        "levene_p": levene_p,
    }


def infer_analysis_plan(metric_count: int, factor_count: int, factor_levels: list[int]) -> dict[str, str]:
    """Restituisce una descrizione leggibile del percorso scelto dal motore."""
    if metric_count <= 0:
        return {"kind": "invalid", "title": "Nessuna analisi", "method": "Seleziona almeno una metrica."}
    if factor_count == 0:
        if metric_count == 1:
            return {"kind": "descriptive", "title": "Profilo descrittivo", "method": "Statistiche descrittive e distribuzione."}
        return {"kind": "relationship", "title": "Relazioni tra metriche", "method": "Descrittive e correlazioni automatiche."}
    first_levels = factor_levels[0] if factor_levels else 0
    if factor_count == 1:
        if first_levels == 2:
            return {"kind": "two_groups", "title": "Confronto tra due gruppi", "method": "t-test/Welch oppure Mann–Whitney, scelto automaticamente."}
        if first_levels > 2:
            return {"kind": "multiple_groups", "title": "Confronto tra più gruppi", "method": "ANOVA oppure Kruskal–Wallis, scelto automaticamente."}
        return {"kind": "descriptive", "title": "Profilo descrittivo", "method": "Il fattore contiene meno di due livelli validi."}
    return {
        "kind": "factorial",
        "title": "Analisi multifattoriale esplorativa",
        "method": "Trend, distribuzioni e confronti automatici del primo fattore, stratificati per il secondo.",
    }
