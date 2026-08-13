from __future__ import annotations

import json

import pytest

from pas_connect.metric_descriptors import descriptor_pas_value, resolve_scalar_metrics
from pas_connect.rest_mapper import map_rest_scalar_kpis


def _row(source, position, name, value, group, unit=None, raw=None):
    return {
        "source": source, "position": position, "name": name, "value": value,
        "kpi_group": group, "uom": unit, "unit": unit,
        "raw_json": json.dumps(raw or {"name": name, "value": value}),
    }


@pytest.mark.parametrize("raw", [7.5, 8.4, 8.333333, 9.125, 0.0])
def test_max_speed_live_style_conversion_and_provenance(raw):
    metric = next(row for row in map_rest_scalar_kpis({"max_values_speed": raw})
                  if row["provider_name"] == "max_values_speed")
    assert metric["value"] == pytest.approx(raw * 3.6)
    assert metric["unit"] == "km/h"
    assert metric["provider_unit"] == "m/s"
    assert metric["raw"]["provider_value"] == raw
    assert metric["raw"]["canonical_value"] == pytest.approx(raw * 3.6)
    assert metric["raw"]["conversion"] == "x3.6"


def test_max_speed_is_optional_and_zero_is_not_missing():
    assert map_rest_scalar_kpis({}) == []
    metric = map_rest_scalar_kpis({"max_values_speed": 0})[0]
    assert metric["active"] is True
    assert metric["value"] == 0


def test_rest_owns_metric_without_cross_source_sum():
    result = resolve_scalar_metrics([
        _row("kpi", 0, "total_distance", 999, "Distance", "m"),
        _row("rest_v2", 0, "distance", 100, "Distance", "m"),
        _row("identifierKpi", 0, "Distance", 500, "Distance", "m"),
    ])
    assert result["Distance"].value == 100
    assert result["Distance"].source == "rest_v2"


def test_graphql_fallback_is_deterministic_when_rest_is_absent():
    result = resolve_scalar_metrics([
        _row("kpi", 0, "total_distance", 999, "Distance", "m"),
        _row("identifierKpi", 0, "Distance", 500, "Distance", "m"),
    ])
    assert result["Distance"].value == 500
    assert result["Distance"].source == "identifierKpi"


@pytest.mark.parametrize("canonical,name", [
    ("Distance", "distance"), ("RPE", "rpe"), ("Max Speed", "max_values_speed"),
])
def test_present_rest_null_never_silently_falls_back(canonical, name):
    result = resolve_scalar_metrics([
        _row("kpi", 0, name, 42, canonical),
        _row("rest_v2", 0, name, None, canonical),
    ])
    assert result[canonical].value is None
    assert result[canonical].source == "rest_v2"


def test_descriptor_units_and_accumulations_are_canonical():
    rows = [
        _row("rest_v2", 0, "distance", 100, "Distance", "m"),
        _row("rest_v2", 1, "rpe", 7, "RPE", ""),
        _row("rest_v2", 2, "max_values_speed", 27, "Max Speed", "km/h"),
    ]
    result = resolve_scalar_metrics(rows)
    assert result["Distance"].accumulation == "sum"
    assert result["RPE"].accumulation == "mean"
    assert result["Max Speed"].accumulation == "max"
    assert descriptor_pas_value(result["Max Speed"]) == 27


def test_legacy_rest_duration_without_uom_is_still_seconds():
    descriptor = resolve_scalar_metrics([
        _row("rest_v2", 0, "duration", 3600, "Duration", None),
    ])["Duration"]
    assert descriptor.value_unit == "s"
    assert descriptor_pas_value(descriptor) == 60
