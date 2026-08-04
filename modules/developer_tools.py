"""Strumenti tecnici del bridge, isolati dalle viste operative."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from modules.bridge_validation import compare_distance_sources
from modules.data_provider import get_data_provider
from modules.relative_distance_validation import compare_relative_distance_sources
from modules.day_overview_provider import coverage_percentage, overview_coverage
from modules.day_overview_validation import compare_overview_metric
from pas_connect.pas_bridge import available_sessions


def render_developer_tools(
    *, selected_provider: str, active_frame: Any, excel_source: Any, database_path: str | Path,
) -> None:
    with st.expander("Developer Tools", expanded=False):
        pilot_tab, validation_tab, coverage_tab = st.tabs(
            ["Distance Pilot", "Bridge Validation", "Copertura Panoramica"]
        )
        with pilot_tab:
            provider = get_data_provider(selected_provider)
            source = active_frame if selected_provider == "excel" else database_path
            try:
                frame = provider.load_pilot_distance_data(source)
                st.info(f"Sorgente selezionata: {provider.display_name}")
                if frame.empty:
                    st.info("Nessun valore Distance disponibile nella sorgente selezionata.")
                else:
                    st.metric("Distance totale", f"{float(frame['Distance (m)'].sum()):,.0f} m")
                    st.dataframe(frame, hide_index=True, use_container_width=True)
            except Exception as exc:
                st.error(f"Vista Distance non disponibile: {exc}")

        with validation_tab:
            metric = st.selectbox("Metrica", [
                "Distance", "Relative Distance", "Duration (min)", "Acc Events (n°)",
                "Dec Events (n°)", "Max Speed (km/h)", "Speed Events (n°)",
            ],
                                  key="bridge_validation_metric")
            tolerance = st.number_input(
                f"Tolleranza {metric}", min_value=0.0, value=0.1, step=0.1,
                key="bridge_validation_tolerance",
            )
            try:
                result = None
                if metric == "Distance":
                    excel = get_data_provider("excel").load_pilot_distance_data(excel_source)
                    gpexe = get_data_provider("gpexe").load_pilot_distance_data(database_path)
                    result = compare_distance_sources(excel, gpexe, tolerance_m=float(tolerance))
                elif metric == "Relative Distance":
                    excel_frame = get_data_provider("excel").load_performance_data(excel_source)
                    excel_dates = set(pd.to_datetime(
                        excel_frame["Date"], errors="coerce"
                    ).dropna().dt.strftime("%Y-%m-%d"))
                    gpexe_dates = {
                        str(row.get("start_timestamp") or "")[:10]
                        for row in available_sessions(database_path)
                    }
                    common_dates = sorted(excel_dates.intersection(gpexe_dates))
                    if not common_dates:
                        raise ValueError("Nessuna data comune disponibile per Relative Distance.")
                    preferred = next(
                        (value for value in ("2025-08-01", "2025-08-03") if value in common_dates),
                        common_dates[-1],
                    )
                    selected_date = st.selectbox(
                        "Data Relative Distance",
                        common_dates,
                        index=common_dates.index(preferred),
                        format_func=lambda value: pd.Timestamp(value).strftime("%d/%m/%Y"),
                        key="bridge_validation_relative_date",
                    )
                    excel = get_data_provider("excel").load_session_relative_distance_data(
                        excel_frame, selected_date
                    )
                    gpexe = get_data_provider("gpexe").load_session_relative_distance_data(
                        database_path, selected_date
                    )
                    result = compare_relative_distance_sources(
                        excel, gpexe, tolerance_m_min=float(tolerance)
                    )
                else:
                    excel_frame = get_data_provider("excel").load_performance_data(excel_source)
                    common_dates = sorted(
                        set(pd.to_datetime(excel_frame["Date"], errors="coerce").dropna().dt.strftime("%Y-%m-%d"))
                        & {str(row.get("start_timestamp") or "")[:10] for row in available_sessions(database_path)}
                    )
                    if not common_dates:
                        raise ValueError("Nessuna data comune per la validazione.")
                    preferred = next((d for d in ("2025-08-01", "2025-08-03") if d in common_dates), common_dates[-1])
                    selected_date = st.selectbox("Data Panoramica", common_dates,
                        index=common_dates.index(preferred), key="bridge_validation_overview_date")
                    excel = get_data_provider("excel").load_day_overview_data(excel_frame, selected_date)
                    gpexe = get_data_provider("gpexe").load_day_overview_data(database_path, selected_date)
                    comparisons, summary = compare_overview_metric(
                        excel, gpexe, metric, tolerance=float(tolerance)
                    )
                    st.dataframe(comparisons, hide_index=True, use_container_width=True)
                    cols = st.columns(5)
                    for col, label, key in zip(cols, ("Confrontati", "Coincidenti", "Differenti", "Solo Excel", "Solo GPExe"),
                        ("atleti_confrontati", "atleti_coincidenti", "atleti_differenti", "atleti_solo_excel", "atleti_solo_gpexe")):
                        col.metric(label, summary[key])
                    st.caption(f"Tolleranza: {summary['tolleranza']} {summary['unita']} · Unità canonica: {summary['unita']}")
                    result = None
                if result is not None:
                    summary = result.summary
                    cols = st.columns(4)
                    for column, label, key in zip(cols,
                        ("Sedute confrontate", "Atleti confrontati", "Atleti coincidenti", "Atleti differenti"),
                        ("sedute_confrontate", "atleti_confrontati", "atleti_coincidenti", "atleti_differenti")):
                        column.metric(label, summary[key])
                    if metric == "Relative Distance":
                        extra = st.columns(2)
                        extra[0].metric("Solo Excel", summary["atleti_solo_excel"])
                        extra[1].metric("Solo GPExe", summary["atleti_solo_gpexe"])
                    st.dataframe(result.comparisons, hide_index=True, use_container_width=True)
                    st.markdown("#### Sedute non confrontabili")
                    st.dataframe(result.non_comparable_sessions, hide_index=True, use_container_width=True)
            except Exception as exc:
                st.error(f"Bridge Validation non disponibile: {exc}")

        with coverage_tab:
            teams = st.session_state.get("pas_gpexe_teams", [])
            team_index = int(st.session_state.get("pas_gpexe_selected_team_index", 0) or 0)
            selected_team = teams[team_index] if teams and team_index < len(teams) else {}
            rows = overview_coverage(
                database_path,
                team_id=selected_team.get("id") if isinstance(selected_team, dict) else None,
            )
            st.metric("Copertura GPExe Panoramica", f"{coverage_percentage(rows):.1f}%")
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
