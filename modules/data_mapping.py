"""Schema canonico e mapping GPExe -> PAS.

Il modulo non attiva GPExe come sorgente: definisce soltanto un livello puro,
testabile e indipendente dalla UI per normalizzare nomi, unità e campi obbligatori.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Mapping


class MappingValidationError(ValueError):
    """Payload non convertibile nello schema canonico PAS."""


@dataclass(frozen=True)
class CanonicalMetric:
    pas_column: str
    unit: str
    aliases: tuple[str, ...]
    required: bool = False


def _key(value: object) -> str:
    text = str(value or "").strip().lower().replace("²", "2")
    return re.sub(r"[^a-z0-9]+", "", text)


CANONICAL_METRICS: tuple[CanonicalMetric, ...] = (
    CanonicalMetric("distance (m)", "m", ("distance", "total distance", "distance m"), True),
    CanonicalMetric("relative distance (m/min)", "m/min", ("relative distance", "distance per minute", "m/min")),
    CanonicalMetric("acc events", "n°", ("acc events", "acceleration events", "accelerations")),
    CanonicalMetric("dec events", "n°", ("dec events", "deceleration events", "decelerations")),
    CanonicalMetric("distance/speed Z3 (m)", "m", ("distance 19.8-25.2", "19.8-25.2 km/h", "speed zone 3 distance")),
    CanonicalMetric("distance/speed Z4 (m)", "m", ("distance >25.2", ">25.2 km/h", "speed zone 4 distance")),
    CanonicalMetric("speed events", "n°", ("speed events", "high speed events", "sprint events")),
    CanonicalMetric("max speed (km/h)", "km/h", ("max speed", "maximum speed", "top speed")),
)

_ALIAS_INDEX = {
    _key(alias): metric
    for metric in CANONICAL_METRICS
    for alias in (metric.pas_column, *metric.aliases)
}


def resolve_metric(label: str) -> CanonicalMetric | None:
    """Restituisce la metrica PAS associata a una label GPExe."""
    return _ALIAS_INDEX.get(_key(label))


def _number(value: Any, label: str) -> float | int | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise MappingValidationError(f"Valore non numerico per {label}: {value!r}")
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError) as exc:
        raise MappingValidationError(f"Valore non numerico per {label}: {value!r}") from exc
    if not math.isfinite(number):
        raise MappingValidationError(f"Valore non finito per {label}: {value!r}")
    return int(number) if number.is_integer() else number


def _convert(value: float | int | None, source_unit: str | None, target_unit: str, label: str):
    if value is None:
        return None
    source = _key(source_unit)
    target = _key(target_unit)
    if not source or source == target:
        return value
    if source in {"km", "kilometer", "kilometers"} and target == "m":
        return value * 1000
    if source in {"ms", "mps"} and target == "kmh":
        return value * 3.6
    if source in {"min", "minute", "minutes"} and target == "s":
        return value * 60
    raise MappingValidationError(
        f"Unità GPExe non supportata per {label}: {source_unit!r} -> {target_unit!r}"
    )


def map_gpexe_metrics(
    metrics: Mapping[str, Any],
    *,
    units: Mapping[str, str] | None = None,
    require_core: bool = False,
) -> dict[str, Any]:
    """Normalizza metriche GPExe nelle colonne PAS senza alterare aggregazioni.

    Le label non riconosciute vengono ignorate; i valori mancanti restano ``None``.
    """
    if not isinstance(metrics, Mapping):
        raise MappingValidationError("Le metriche GPExe devono essere una mappa label-valore.")
    units = units or {}
    result: dict[str, Any] = {}
    for label, raw_value in metrics.items():
        definition = resolve_metric(str(label))
        if definition is None:
            continue
        value = _number(raw_value, str(label))
        result[definition.pas_column] = _convert(
            value, units.get(str(label)), definition.unit, str(label)
        )
    if require_core:
        missing = [m.pas_column for m in CANONICAL_METRICS if m.required and result.get(m.pas_column) is None]
        if missing:
            raise MappingValidationError("Metriche GPExe obbligatorie mancanti: " + ", ".join(missing))
    return result
