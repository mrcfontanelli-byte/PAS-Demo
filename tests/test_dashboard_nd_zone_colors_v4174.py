from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).parents[1]


def _availability_helper():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "metric_has_context_values"
    )
    namespace = {"pd": pd}
    exec(compile(ast.Module(body=[function], type_ignores=[]), "app.py", "exec"), namespace)
    return namespace["metric_has_context_values"]


def test_metric_availability_treats_zero_and_partial_values_as_available():
    available = _availability_helper()
    spec = {"column": "metric"}
    assert available(pd.DataFrame({"metric": [None, 0, float("nan")]}), spec)
    assert available(pd.DataFrame({"metric": [None, "4.5", float("nan")]}), spec)


def test_metric_availability_rejects_all_null_non_numeric_and_missing_columns():
    available = _availability_helper()
    spec = {"column": "metric"}
    assert not available(pd.DataFrame({"metric": [None, float("nan")]}), spec)
    assert not available(pd.DataFrame({"metric": [None, "N/D"]}), spec)
    assert not available(pd.DataFrame({"other": [1]}), spec)


def test_player_null_does_not_hide_a_globally_available_metric():
    available = _availability_helper()
    context = pd.DataFrame({"Athlete": ["A", "B"], "metric": [None, 3]})
    assert available(context, {"column": "metric"})
    assert pd.isna(context.loc[context["Athlete"].eq("A"), "metric"].mean())


def test_gpexe_availability_uses_global_context_and_excel_keeps_full_catalog():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    split_start = source.index("dashboard_available_metric_specs = dict(")
    split_end = source.index("# ---------------------------------------------------------\n# 3. PANORAMICA", split_start)
    split = source[split_start:split_end]
    assert "if dashboard_uses_gpexe_distance:" in split
    assert "metric_has_context_values(dashboard_gpexe_overview_current, spec)" in split
    assert "dashboard_available_metric_specs = dict(dashboard_contextual_metric_specs)" in split
    assert "overview_player" not in split


def test_all_gpexe_selectors_reuse_available_catalog_and_expander_is_closed():
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("list(dashboard_available_metric_specs.keys())") == 5
    assert 'detail_metric_options = list(dashboard_available_metric_specs.keys())' in source
    assert 'f"Metriche non disponibili ({len(dashboard_unavailable_metric_specs)})"' in source
    assert "expanded=False" in source[source.index("if dashboard_unavailable_metric_specs:"):]
    assert 'st.markdown(f"- {unavailable_metric_name} — N/D")' in source
