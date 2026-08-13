"""Descriptor read-only delle Speed Zone Distance storicizzate da GPExe REST."""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .rest_mapper import (
    SPEED_PROVIDER_THRESHOLD_UNIT, SPEED_THRESHOLD_UNIT, SPEED_ZONE_FAMILY, SPEED_ZONE_VALUE_UNIT,
    speed_zone_label, speed_zone_metric_key,
)


@dataclass(frozen=True)
class SpeedZoneDistanceDescriptor:
    metric_family: str
    metric_key: str
    label: str
    lower_bound: float | None
    upper_bound: float | None
    threshold_unit: str
    value_unit: str
    team_id: int | None = None
    season: str | None = None
    team_session_id: int | None = None
    athlete_session_id: int | None = None
    accumulation: str = "sum"

    @property
    def sort_key(self) -> tuple[float, float]:
        return (
            float("-inf") if self.lower_bound is None else self.lower_bound,
            float("inf") if self.upper_bound is None else self.upper_bound,
        )


def descriptor_from_snapshot(snapshot: Mapping[str, Any]) -> SpeedZoneDistanceDescriptor:
    raw_value = snapshot.get("raw_json", snapshot.get("raw"))
    raw = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
    if not isinstance(raw, Mapping):
        raise ValueError("Snapshot Speed Zone Distance privo di provenance.")
    payload = raw.get("raw") if isinstance(raw.get("raw"), Mapping) else raw
    metadata = payload.get("threshold_snapshot")
    if not isinstance(metadata, Mapping):
        raise ValueError("Snapshot Speed Zone Distance privo di bounds storici.")
    lower = metadata.get("canonical_lower_bound_kmh")
    upper = metadata.get("canonical_upper_bound_kmh")
    threshold_unit = str(metadata.get("canonical_threshold_unit") or "")
    provider_unit = str(metadata.get("provider_threshold_unit") or "")
    value_unit = str(metadata.get("value_unit") or "")
    if (provider_unit != SPEED_PROVIDER_THRESHOLD_UNIT or
            threshold_unit != SPEED_THRESHOLD_UNIT or value_unit != SPEED_ZONE_VALUE_UNIT):
        raise ValueError("Unità Speed Zone Distance non supportate.")
    lower = float(lower) if lower is not None else None
    upper = float(upper) if upper is not None else None
    if lower is None and upper is None:
        raise ValueError("Snapshot Speed Zone Distance privo di bounds.")
    context = payload.get("context_snapshot")
    context = context if isinstance(context, Mapping) else {}
    return SpeedZoneDistanceDescriptor(
        SPEED_ZONE_FAMILY, speed_zone_metric_key(lower, upper),
        speed_zone_label(lower, upper), lower, upper, threshold_unit, value_unit,
        int(context["team_id"]) if context.get("team_id") is not None else None,
        str(context["season"]) if context.get("season") is not None else None,
        int(context["team_session_id"]) if context.get("team_session_id") is not None else None,
        int(context["athlete_session_id"]) if context.get("athlete_session_id") is not None else None,
    )


def aggregate_speed_zone_values(values: list[object]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return sum(numbers) if numbers else None
