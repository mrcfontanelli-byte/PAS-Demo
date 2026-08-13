"""Descriptor e risoluzione source-aware dei KPI scalar GPExe."""
from __future__ import annotations

from dataclasses import dataclass
import json
import math
import re
from typing import Any, Iterable, Mapping


def _key(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


@dataclass(frozen=True)
class ScalarMetricSpec:
    canonical_key: str
    display_label: str
    pas_column: str
    value_unit: str
    accumulation: str
    provider_names: tuple[str, ...]


@dataclass(frozen=True)
class MetricDescriptor:
    canonical_key: str
    display_label: str
    family: str
    value: float | int | None
    value_unit: str
    accumulation: str
    provider: str
    source: str
    provider_metric_name: str
    threshold_lower: float | None = None
    threshold_upper: float | None = None
    threshold_unit: str | None = None
    provenance: Mapping[str, Any] | None = None


SCALAR_METRICS: tuple[ScalarMetricSpec, ...] = (
    ScalarMetricSpec("Distance", "Distance (m)", "distance (m)", "m", "sum",
                     ("distance", "total distance", "total_distance")),
    ScalarMetricSpec("Duration", "Duration (min)", "Duration (dec)", "min", "sum",
                     ("duration", "total time", "total_time")),
    ScalarMetricSpec("Acc Events", "Acc Events", "acc events", "n°", "sum",
                     ("acceleration_events", "acc events", "accelerations")),
    ScalarMetricSpec("Dec Events", "Dec Events", "dec events", "n°", "sum",
                     ("deceleration_events", "dec events", "decelerations")),
    ScalarMetricSpec("Speed Events", "Speed Events", "speed events", "n°", "sum",
                     ("speed_events", "speed events", "high speed events", "sprint events")),
    ScalarMetricSpec("RPE", "RPE", "RPE (CR10)", "", "mean", ("rpe",)),
    ScalarMetricSpec("Max Speed", "Max Speed (km/h)", "max speed (km/h)", "km/h", "max",
                     ("max_values_speed", "max speed", "maximum speed", "top speed")),
)

_BY_CANONICAL = {_key(spec.canonical_key): spec for spec in SCALAR_METRICS}
_BY_NAME = {
    _key(name): spec
    for spec in SCALAR_METRICS
    for name in (spec.canonical_key, spec.display_label, spec.pas_column, *spec.provider_names)
}
_SOURCE_RANK = {"restv2": 0, "identifierkpi": 1, "kpi": 2}
_REST_LEGACY_UNITS = {"Distance": "m", "Duration": "s", "Max Speed": "km/h"}


def scalar_metric_spec(*, canonical: object = None, provider_name: object = None) -> ScalarMetricSpec | None:
    """Risolve una metrica usando prima il gruppo canonico, poi il nome provider."""
    return _BY_CANONICAL.get(_key(canonical)) or _BY_NAME.get(_key(provider_name))


def _number(value: object) -> float | int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        number = float(str(value).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number.is_integer() else number


def _raw(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("raw_json", row.get("raw"))
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = {}
    return value if isinstance(value, Mapping) else {}


def resolve_scalar_metrics(rows: Iterable[Mapping[str, Any]]) -> dict[str, MetricDescriptor]:
    """Seleziona una sola source per canonical metric.

    La presenza di una riga ``rest_v2`` stabilisce ownership REST anche con valore
    NULL. GraphQL viene usato soltanto quando la riga REST canonica non esiste.
    ``identifierKpi`` precede ``kpi`` per conservare il comportamento legacy.
    """
    candidates: dict[str, list[tuple[int, int, Mapping[str, Any], ScalarMetricSpec]]] = {}
    for row in rows:
        source = str(row.get("source") or "")
        rank = _SOURCE_RANK.get(_key(source))
        if rank is None:
            continue
        spec = scalar_metric_spec(canonical=row.get("kpi_group"), provider_name=row.get("name"))
        if spec is None:
            continue
        position = int(row.get("position") or 0)
        candidates.setdefault(spec.canonical_key, []).append((rank, position, row, spec))

    resolved: dict[str, MetricDescriptor] = {}
    for canonical, values in candidates.items():
        _, _, row, spec = min(values, key=lambda item: (item[0], item[1], str(item[2].get("name") or "")))
        source = str(row.get("source") or "")
        raw = _raw(row)
        row_unit = row.get("uom") or row.get("unit")
        if not row_unit and _key(source) == "restv2":
            row_unit = _REST_LEGACY_UNITS.get(canonical)
        resolved[canonical] = MetricDescriptor(
            canonical_key=canonical,
            display_label=spec.display_label,
            family="scalar",
            value=_number(row.get("value")),
            value_unit=str(row_unit or spec.value_unit),
            accumulation=spec.accumulation,
            provider="gpexe",
            source=source,
            provider_metric_name=str(row.get("name") or ""),
            provenance={"source": source, "raw": raw},
        )
    return resolved


def descriptor_pas_value(descriptor: MetricDescriptor) -> float | int | None:
    """Adatta il valore canonico alla colonna PAS legacy senza blending."""
    value = descriptor.value
    if value is None:
        return None
    unit = _key(descriptor.value_unit)
    if descriptor.canonical_key == "Duration" and unit in {"s", "sec", "second", "seconds"}:
        return value / 60.0
    if descriptor.canonical_key == "Distance" and unit in {"km", "kilometer", "kilometers"}:
        return value * 1000.0
    if descriptor.canonical_key == "Max Speed" and unit in {"ms", "mps"}:
        return value * 3.6
    return value
