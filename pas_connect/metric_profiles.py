"""Profili metrici configurabili, indipendenti dal motore analitico PAS."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping


@dataclass(frozen=True)
class MetricProfileComparison:
    status: str
    explanation: str


def normalize_metric_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    """Valida e normalizza un profilo prima della persistenza."""
    normalized = dict(profile)
    for field in ("team_name", "season", "canonical_metric", "provider_metric_name", "threshold_unit", "source"):
        value = str(normalized.get(field) or "").strip()
        if not value:
            raise ValueError(f"Campo obbligatorio mancante: {field}.")
        normalized[field] = value
    if normalized.get("team_id") in (None, ""):
        raise ValueError("Campo obbligatorio mancante: team_id.")
    normalized["team_id"] = str(normalized["team_id"]).strip()
    for field in ("threshold_min", "threshold_max"):
        value = normalized.get(field)
        normalized[field] = None if value in (None, "") else float(value)
    minimum, maximum = normalized["threshold_min"], normalized["threshold_max"]
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("La soglia minima non può superare la soglia massima.")
    for field in ("threshold_min_inclusive", "threshold_max_inclusive", "verified"):
        normalized[field] = bool(normalized.get(field, False))
    for field in ("valid_from", "valid_to"):
        value = normalized.get(field)
        normalized[field] = value.isoformat() if isinstance(value, date) else (str(value).strip() or None if value is not None else None)
    if normalized["valid_from"] and normalized["valid_to"] and normalized["valid_from"] > normalized["valid_to"]:
        raise ValueError("La data iniziale non può essere successiva alla data finale.")
    normalized["notes"] = str(normalized.get("notes") or "").strip() or None
    return normalized


def format_metric_threshold(profile: Mapping[str, Any]) -> str:
    """Rappresenta intervalli aperti, chiusi o semiaperti in forma leggibile."""
    minimum = profile.get("threshold_min")
    maximum = profile.get("threshold_max")
    unit = str(profile.get("threshold_unit") or "").strip()
    min_inclusive = bool(profile.get("threshold_min_inclusive"))
    max_inclusive = bool(profile.get("threshold_max_inclusive"))
    if minimum is None and maximum is None:
        interval = "qualsiasi valore"
    elif maximum is None:
        interval = f"{'>=' if min_inclusive else '>'}{minimum:g}"
    elif minimum is None:
        interval = f"{'<=' if max_inclusive else '<'}{maximum:g}"
    else:
        interval = f"{'[' if min_inclusive else '('}{minimum:g}–{maximum:g}{']' if max_inclusive else ')'}"
    return f"{interval} {unit}".strip()


def compare_metric_profiles(
    left: Mapping[str, Any] | None,
    right: Mapping[str, Any] | None,
    *,
    applicable_date: date | str | None = None,
) -> MetricProfileComparison:
    """Certifica la confrontabilità semantica di due metriche a soglia."""
    if left is None or right is None:
        return MetricProfileComparison("CONFIGURAZIONE MANCANTE", "Manca almeno uno dei due profili metrici.")
    if not bool(left.get("verified")) or not bool(right.get("verified")):
        return MetricProfileComparison("CONFIGURAZIONE NON VERIFICATA", "Almeno un profilo non è stato verificato.")
    if applicable_date is not None:
        target = applicable_date.isoformat() if isinstance(applicable_date, date) else str(applicable_date)
        for label, profile in (("primo", left), ("secondo", right)):
            if (profile.get("valid_from") and target < str(profile["valid_from"])) or (
                profile.get("valid_to") and target > str(profile["valid_to"])
            ):
                return MetricProfileComparison("NON CONFRONTABILE", f"Il {label} profilo non è valido alla data {target}.")
    fields = (
        ("threshold_unit", "unità"), ("threshold_min", "soglia minima"),
        ("threshold_max", "soglia massima"),
        ("threshold_min_inclusive", "inclusività minima"),
        ("threshold_max_inclusive", "inclusività massima"),
        ("valid_from", "inizio validità"), ("valid_to", "fine validità"),
    )
    differences = [label for field, label in fields if left.get(field) != right.get(field)]
    if differences:
        return MetricProfileComparison(
            "NON CONFRONTABILE",
            "I profili differiscono per: " + ", ".join(differences) + ". Nessuna differenza numerica calcolata.",
        )
    return MetricProfileComparison("CONFRONTABILE", "Unità, soglie, inclusività e periodo di validità coincidono.")
