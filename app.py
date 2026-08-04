from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import base64
import sys

# Garantisce che i moduli locali siano risolti anche su Streamlit Cloud.
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import calendar
import json
from datetime import timedelta
from io import BytesIO
import re
import unicodedata
import warnings

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from scipy import stats as scipy_stats
from patsy import build_design_matrices

from modules.config import APP_NAME, APP_SUBTITLE, METRICS, DEFAULT_DRILLS
from modules.security import DEMO_PASSWORD
from modules.version import APP_BUILD_VERSION, APP_EDITION
from modules.pas_assistant import render_pas_assistant
from modules.data_loader import (
    aggregate_player_day,
    database_summary,
)
from modules.data_provider import get_available_data_providers, get_data_provider, resolve_data_provider
from modules.statistics_engine import (
    descriptive_statistics,
    value_against_reference,
    shapiro_result,
    compare_independent_groups,
    correlation_analysis,
    compare_multiple_groups,
    infer_analysis_plan,
)
from modules.context_engine import context_for_date, historical_similar_days
from modules.reporting import (
    build_pdf_report,
    build_session_report_pdf,
    build_forecast_report_pdf,
    build_daily_planner_report_pdf,
)
from modules.charts import (
    trend_chart,
    player_comparison_chart,
    historical_boxplot,
    compact_reference_boxplot,
    compact_player_day_bars,
)
from pas_connect import GPExeClient, GPExeGraphQLClient, GPExeConfig, GPExeServices, GPExeAPIDataProvider, PASConnectDatabase, SnapshotStore, sync_reference_data, sync_team_sessions, sync_team_session_details, sync_athlete_session_details, run_full_sync, invalidate_team_filter_state, invalidate_athlete_filter_state, invalidate_athlete_session_state, invalidate_athlete_context_state, resolve_team_club_id, store_athlete_fetch_result, athletes_from_team_session_results, team_session_error_diagnostic, normalize_team_session_error_diagnostics, TEAM_SESSION_DIAGNOSTIC_COLUMNS
from pas_connect.pas_bridge import available_sessions, has_compatible_performance_rows
from pas_connect.mapper import map_team_session, map_graphql_athlete, map_graphql_athlete_session
from pas_connect.endpoints import TEAMS


st.set_page_config(
    page_title=f"{APP_NAME} · {APP_EDITION} v{APP_BUILD_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    /* Compatta lo spazio superiore senza sovrapporre la toolbar nativa Streamlit.
       Il margine di sicurezza evita il taglio dell'header PAS su Streamlit Cloud. */
    [data-testid="stMainBlockContainer"],
    .main .block-container {
        padding-top: 3.5rem !important;
    }

    /* Hide Streamlit native running/status animation. */
    div[data-testid="stStatusWidget"],
    div[data-testid="stToolbar"] div[data-testid="stStatusWidget"] {
        display: none !important;
        visibility: hidden !important;
    }

    /* PAS custom loader. */
    .pas-loader-card {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.85rem;
        width: 100%;
        padding: 1rem 1.2rem;
        margin: 0.35rem 0 0.75rem 0;
        border: 1px solid rgba(244, 196, 48, 0.35);
        border-radius: 0.75rem;
        background: rgba(7, 20, 38, 0.96);
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18);
    }

    .pas-loader-ball {
        display: inline-block;
        font-size: 1.8rem;
        line-height: 1;
        transform-origin: center;
        animation: pasFootballSpin 0.8s linear infinite;
    }

    .pas-loader-copy {
        display: flex;
        flex-direction: column;
        gap: 0.12rem;
    }

    .pas-loader-title {
        color: #FFFFFF;
        font-size: 0.98rem;
        font-weight: 850;
        line-height: 1.15;
    }

    .pas-loader-subtitle {
        color: #B9C6D8;
        font-size: 0.72rem;
        letter-spacing: 0.035em;
    }

    /* PAS football loading spinner */
    div[data-testid="stSpinner"] svg {
        display: none !important;
    }

    div[data-testid="stSpinner"] > div::before {
        content: "⚽";
        display: inline-block;
        font-size: 1.55rem;
        margin-right: 0.55rem;
        transform-origin: center;
        animation: pasFootballSpin 0.85s linear infinite;
        vertical-align: middle;
    }

    @keyframes pasFootballSpin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }

    .pas-brand-header {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.15rem 0 0.8rem 0;
        margin-bottom: 0.25rem;
        border-bottom: 1px solid rgba(244, 196, 48, 0.22);
    }

    .pas-brand-header img {
        width: 66px;
        height: 66px;
        object-fit: contain;
    }

    .pas-brand-kicker {
        color: #F4C430;
        font-size: 0.76rem;
        font-weight: 850;
        letter-spacing: 0.12em;
        text-transform: uppercase;
    }

    .pas-brand-title {
        color: #FFFFFF;
        font-size: 1.18rem;
        font-weight: 850;
        line-height: 1.15;
    }

    .pas-brand-subtitle {
        color: #B9C6D8;
        font-size: 0.78rem;
        margin-top: 0.15rem;
    }

    .pas-section-title {
        font-size: 1.12rem;
        font-weight: 800;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        margin: 1.2rem 0 0.55rem 0;
        color: #F4C430;
    }

    .pas-dashboard-hero {
        display: flex;
        align-items: flex-end;
        justify-content: space-between;
        gap: 1rem;
        margin: 0.15rem 0 0.35rem 0;
        padding: 0.75rem 0.95rem;
        border: 1px solid rgba(142, 209, 252, 0.18);
        border-radius: 0.85rem;
        background: linear-gradient(135deg, rgba(12, 31, 54, 0.92), rgba(7, 20, 38, 0.72));
    }

    .pas-dashboard-hero-title {
        color: #FFFFFF;
        font-size: 1.18rem;
        font-weight: 850;
        line-height: 1.2;
    }

    .pas-dashboard-hero-meta {
        color: #9FB2C8;
        font-size: 0.76rem;
        margin-top: 0.18rem;
    }

    .pas-dashboard-card-marker {
        display: none;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.pas-dashboard-card-marker) {
        border: 1px solid rgba(142, 209, 252, 0.20) !important;
        border-radius: 0.95rem !important;
        background: linear-gradient(180deg, rgba(12, 31, 54, 0.94), rgba(8, 23, 41, 0.86)) !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.16);
        overflow: hidden;
    }

    div[data-testid="stVerticalBlockBorderWrapper"]:has(.pas-dashboard-card-marker) > div {
        padding: 0.85rem 0.95rem 0.75rem 0.95rem !important;
    }

    .pas-card-title {
        font-size: 1.02rem;
        font-weight: 820;
        line-height: 1.18;
        margin-bottom: 0.18rem;
        color: #DDE8F5;
        letter-spacing: 0.01em;
    }

    .pas-card-value {
        font-size: 2.45rem;
        font-weight: 900;
        line-height: 1;
        margin: 0.08rem 0 0.30rem 0;
        color: #FFFFFF;
        letter-spacing: -0.025em;
    }

    .pas-card-secondary {
        margin-top: -0.15rem;
        margin-bottom: 0.25rem;
        color: #8ED1FC;
        font-size: 0.92rem;
        font-weight: 800;
        letter-spacing: 0.01em;
    }

    .pas-card-delta {
        display: inline-flex;
        align-items: center;
        font-size: 0.78rem;
        font-weight: 800;
        padding: 0.22rem 0.48rem;
        border-radius: 999px;
        margin-bottom: 0.32rem;
        letter-spacing: 0.01em;
    }

    .pas-status-normal {
        color: #76D7A2;
        background: rgba(46, 204, 113, 0.13);
        border: 1px solid rgba(46, 204, 113, 0.32);
    }

    .pas-status-moderate {
        color: #FFD166;
        background: rgba(255, 193, 7, 0.12);
        border: 1px solid rgba(255, 193, 7, 0.32);
    }

    .pas-status-high {
        color: #FF8A8A;
        background: rgba(255, 82, 82, 0.12);
        border: 1px solid rgba(255, 82, 82, 0.32);
    }

    .pas-card-stats {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 0.30rem;
        margin-top: 0.42rem;
    }

    .pas-card-stat {
        padding: 0.34rem 0.38rem;
        border-radius: 0.48rem;
        background: rgba(255, 255, 255, 0.035);
        border: 1px solid rgba(185, 198, 216, 0.09);
        min-width: 0;
    }

    .pas-card-stat-label {
        display: block;
        color: #8393A7;
        font-size: 0.62rem;
        font-weight: 750;
        text-transform: uppercase;
        letter-spacing: 0.055em;
        line-height: 1;
    }

    .pas-card-stat-value {
        display: block;
        color: #E8EEF6;
        font-size: 0.79rem;
        font-weight: 820;
        margin-top: 0.15rem;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .pas-card-reference {
        font-size: 0.68rem;
        line-height: 1.2;
        color: #8F9CAD;
        margin: -0.08rem 0 0.20rem 0.04rem;
        white-space: nowrap;
    }

    .pas-card-accumulation {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 0.55rem;
        margin-top: 0.55rem;
        padding: 0.44rem 0.55rem;
        border-radius: 0.55rem;
        background: rgba(244, 196, 48, 0.07);
        border: 1px solid rgba(244, 196, 48, 0.20);
    }

    .pas-card-accumulation-label {
        font-size: 0.70rem;
        font-weight: 750;
        color: #B9C6D8;
        margin-bottom: 0;
        line-height: 1.2;
    }

    .pas-card-accumulation-value {
        font-size: 1.12rem;
        font-weight: 900;
        color: #F4C430;
        line-height: 1.1;
        white-space: nowrap;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 0.8rem;
    }

    div[data-testid="stMetricLabel"] p {
        font-size: 1.18rem !important;
        font-weight: 800 !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 2.3rem !important;
        font-weight: 800 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def require_demo_login() -> None:
    if st.session_state.get("pas_demo_authenticated"):
        return

    st.markdown(
        f"""
        <div style="
            max-width: 620px;
            margin: 7vh auto 1.5rem auto;
            padding: 2.2rem 2.4rem;
            border: 1px solid rgba(244,196,48,0.30);
            border-radius: 1rem;
            background: rgba(7,20,38,0.78);
            text-align: center;
        ">
            <div style="
                color:#F4C430;
                font-size:3rem;
                font-weight:900;
                letter-spacing:0.08em;
            ">PAS</div>
            <div style="
                color:#FFFFFF;
                font-size:1.35rem;
                font-weight:750;
                margin-top:0.15rem;
            ">Performance Analysis System</div>
            <div style="
                color:#B9C6D8;
                font-size:0.95rem;
                margin-top:0.45rem;
            ">{APP_EDITION} v{APP_BUILD_VERSION} · Accesso riservato</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    login_col_left, login_col, login_col_right = st.columns(
        [1.2, 1, 1.2]
    )

    with login_col:
        entered_password = st.text_input(
            "Password",
            type="password",
            key="pas_demo_password_input",
        )

        if st.button(
            "Accedi",
            type="primary",
            use_container_width=True,
        ):
            if entered_password == DEMO_PASSWORD:
                st.session_state[
                    "pas_demo_authenticated"
                ] = True
                st.rerun()
            else:
                st.error("Password non corretta.")

    st.stop()


require_demo_login()


def fmt(value: float, decimals: int = 0) -> str:
    if pd.isna(value):
        return "N/D"
    return f"{value:.{decimals}f}".replace(".", ",")


def metric_decimals(metric_name: str) -> int:
    return int(METRICS.get(metric_name, {}).get("decimals", 0))


def metric_format(metric_name: str) -> str:
    return str(METRICS.get(metric_name, {}).get("format", "number"))



def brand_logo_data_uri(base_dir: Path) -> str:
    logo_path = (
        base_dir
        / "assets"
        / "brand"
        / "hellas_verona_logo.png"
    )
    if not logo_path.exists():
        return ""

    encoded = base64.b64encode(
        logo_path.read_bytes()
    ).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_pas_brand_header(base_dir: Path) -> None:
    logo_uri = brand_logo_data_uri(base_dir)
    logo_html = (
        f'<img src="{logo_uri}" alt="Hellas Verona FC">'
        if logo_uri
        else ""
    )
    st.markdown(
        f"""
        <div class="pas-brand-header">
            {logo_html}
            <div>
                <div class="pas-brand-kicker">
                    Hellas Verona FC
                </div>
                <div class="pas-brand-title">
                    Performance Analysis System
                </div>
                <div class="pas-brand-subtitle">
                    Elite Football Performance
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )




@contextmanager
def pas_loader(message: str):
    """
    Loader proprietario PAS con pallone animato.
    Sostituisce st.spinner nelle operazioni controllate dall'app.
    """
    placeholder = st.empty()
    safe_message = (
        str(message)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )

    placeholder.markdown(
        f"""
        <div class="pas-loader-card">
            <div class="pas-loader-ball">⚽</div>
            <div class="pas-loader-copy">
                <div class="pas-loader-title">
                    {safe_message}
                </div>
                <div class="pas-loader-subtitle">
                    Performance Analysis System
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        yield
    finally:
        placeholder.empty()




PLANNER_ACTIVITY_TYPES = [
    "Field Session",
    "Gym Session",
    "Pre-Activation",
    "Video Analysis",
    "Official Match",
    "Friendly Match",
    "Recovery",
    "Medical / RTP",
    "Day Off",
    "Other",
]

PLANNER_PLAYER_STATUSES = [
    "Full Training",
    "Different Training",
    "Return to Play",
    "Individual Training",
    "Gym Only",
    "Medical",
    "Not Available",
    "National Team",
    "Rest",
]

PLANNER_STATUS_COLORS = {
    "Full Training": "#54A24B",
    "Different Training": "#F58518",
    "Return to Play": "#D45087",
    "Individual Training": "#F2CF5B",
    "Gym Only": "#4C78A8",
    "Medical": "#E45756",
    "Not Available": "#8A98A8",
    "National Team": "#B279A2",
    "Rest": "#72B7B2",
}

PLANNER_ACTIVITY_COLORS = {
    "Field Session": "#54A24B",
    "Gym Session": "#4C78A8",
    "Pre-Activation": "#F2CF5B",
    "Video Analysis": "#B279A2",
    "Official Match": "#E45756",
    "Friendly Match": "#F58518",
    "Recovery": "#72B7B2",
    "Medical / RTP": "#D45087",
    "Day Off": "#8A98A8",
    "Other": "#9D755D",
}


def planner_storage_path(base_dir: Path) -> Path:
    path = base_dir / "data" / "daily_planner.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_planner_store(base_dir: Path) -> dict:
    path = planner_storage_path(base_dir)
    if not path.exists():
        return {"days": {}}

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return {"days": {}}
        payload.setdefault("days", {})
        return payload
    except Exception:
        return {"days": {}}


def save_planner_store(base_dir: Path, store: dict) -> None:
    planner_storage_path(base_dir).write_text(
        json.dumps(
            store,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def planner_day_key(value) -> str:
    return pd.Timestamp(value).strftime("%Y-%m-%d")


def planner_activity_summary(day_payload: dict) -> list[str]:
    activities = day_payload.get("activities", [])
    return [
        str(activity.get("type", "Other"))
        for activity in activities
        if activity.get("type")
    ]


def render_planner_calendar(
    store: dict,
    selected_month: pd.Timestamp,
) -> str | None:
    """
    Calendario mensile a griglia 7x6 con celle uniformi.
    Ogni giorno mostra fino a tre attività/partite.
    """
    year = int(selected_month.year)
    month = int(selected_month.month)
    month_matrix = calendar.monthcalendar(year, month)
    day_names = ["Lun", "Mar", "Mer", "Gio", "Ven", "Sab", "Dom"]

    header_cols = st.columns(7, gap="small")
    for index, day_name in enumerate(day_names):
        header_cols[index].markdown(
            (
                "<div style='text-align:center;font-weight:850;"
                "padding:0.35rem 0;color:#B9C6D8;"
                "border-bottom:1px solid rgba(185,198,216,.22);'>"
                f"{day_name}</div>"
            ),
            unsafe_allow_html=True,
        )

    clicked_key = None
    days_store = store.get("days", {})
    today_key = pd.Timestamp.today().strftime("%Y-%m-%d")

    for week in month_matrix:
        week_cols = st.columns(7, gap="small")
        for weekday_index, day_number in enumerate(week):
            with week_cols[weekday_index]:
                if day_number == 0:
                    st.markdown(
                        (
                            "<div style='height:126px;border-radius:10px;"
                            "border:1px solid rgba(185,198,216,.08);"
                            "background:rgba(255,255,255,.01);'></div>"
                        ),
                        unsafe_allow_html=True,
                    )
                    continue

                date_key = f"{year:04d}-{month:02d}-{day_number:02d}"
                payload = days_store.get(date_key, {})
                activities = payload.get("activities", [])
                is_selected = (
                    st.session_state.get("planner_selected_date")
                    == date_key
                )
                is_today = date_key == today_key

                with st.container(border=True):
                    label = str(day_number)
                    if is_today:
                        label += " · oggi"
                    if is_selected:
                        label = f"● {label}"

                    if st.button(
                        label,
                        key=f"planner_calendar_{date_key}",
                        use_container_width=True,
                    ):
                        clicked_key = date_key

                    visible = activities[:3]
                    for activity in visible:
                        activity_type = str(
                            activity.get("type", "Other")
                        )
                        title = str(activity.get("title", "")).strip()
                        compact_label = title or activity_type
                        color = PLANNER_ACTIVITY_COLORS.get(
                            activity_type,
                            "#8A98A8",
                        )
                        st.markdown(
                            (
                                "<div style='font-size:0.66rem;"
                                "line-height:1.15;margin:2px 0;"
                                "padding:3px 6px;border-radius:7px;"
                                f"background:{color};color:white;"
                                "overflow:hidden;white-space:nowrap;"
                                "text-overflow:ellipsis;'>"
                                f"{compact_label}</div>"
                            ),
                            unsafe_allow_html=True,
                        )

                    remaining = len(activities) - len(visible)
                    if remaining > 0:
                        st.caption(f"+{remaining} attività")
                    elif not activities:
                        st.markdown(
                            "<div style='height:58px;'></div>",
                            unsafe_allow_html=True,
                        )

    return clicked_key




def render_dashboard_planner_calendar(
    store: dict,
    selected_month: pd.Timestamp | None = None,
) -> None:
    """
    Calendario Planner compatto e non modificabile per la Dashboard.
    Mostra il mese corrente e una sintesi delle attività.
    """
    selected_month = (
        pd.Timestamp.today()
        if selected_month is None
        else pd.Timestamp(selected_month)
    )

    year = int(selected_month.year)
    month = int(selected_month.month)
    month_matrix = calendar.monthcalendar(year, month)
    day_names = ["L", "M", "M", "G", "V", "S", "D"]
    today_key = pd.Timestamp.today().strftime("%Y-%m-%d")
    days_store = store.get("days", {})

    header_html = "".join(
        (
            "<div style='text-align:center;font-size:0.62rem;"
            "font-weight:850;color:#8FA0B4;padding:2px 0;'>"
            f"{day_name}</div>"
        )
        for day_name in day_names
    )

    cells_html = []

    for week in month_matrix:
        for day_number in week:
            if day_number == 0:
                cells_html.append(
                    (
                        "<div style='min-height:29px;border-radius:5px;"
                        "background:rgba(255,255,255,.015);'></div>"
                    )
                )
                continue

            date_key = f"{year:04d}-{month:02d}-{day_number:02d}"
            payload = days_store.get(date_key, {})
            activities = sort_planner_activities(
                payload.get("activities", [])
            )

            is_today = date_key == today_key
            border = (
                "1px solid #F4C430"
                if is_today
                else "1px solid rgba(185,198,216,.12)"
            )
            background = (
                "rgba(244,196,48,.08)"
                if is_today
                else "rgba(255,255,255,.025)"
            )

            activity_lines = []
            for activity in activities[:1]:
                activity_type = str(
                    activity.get("type", "Other")
                )
                title = str(
                    activity.get("title", "")
                ).strip()
                activity_label = title or activity_type
                if len(activity_label) > 10:
                    activity_label = activity_label[:9] + "…"

                color = PLANNER_ACTIVITY_COLORS.get(
                    activity_type,
                    "#8A98A8",
                )

                activity_lines.append(
                    (
                        "<div style='display:flex;align-items:center;"
                        "gap:2px;font-size:0.46rem;line-height:1.0;"
                        "margin-top:2px;white-space:nowrap;"
                        "overflow:hidden;text-overflow:ellipsis;'>"
                        f"<span style='width:4px;height:4px;"
                        f"border-radius:50%;background:{color};"
                        "display:inline-block;flex:0 0 auto;'></span>"
                        f"<span style='overflow:hidden;"
                        f"text-overflow:ellipsis;'>{activity_label}</span>"
                        "</div>"
                    )
                )

            if len(activities) > 1:
                activity_lines.append(
                    (
                        "<div style='font-size:0.50rem;color:#8FA0B4;"
                        "margin-top:1px;'>"
                        f"+{len(activities) - 1}</div>"
                    )
                )

            cells_html.append(
                (
                    f"<div style='min-height:29px;padding:2px 3px;"
                    f"border:{border};border-radius:6px;"
                    f"background:{background};overflow:hidden;'>"
                    f"<div style='font-size:0.54rem;font-weight:850;"
                    f"color:#FFFFFF;'>{day_number}</div>"
                    + "".join(activity_lines)
                    + "</div>"
                )
            )

    st.markdown(
        (
            "<div style='border:1px solid rgba(185,198,216,.16);"
            "border-radius:9px;background:rgba(7,20,38,.72);"
            "padding:9px 10px 10px 10px;'>"
            "<div style='display:flex;align-items:center;"
            "justify-content:space-between;margin-bottom:6px;'>"
            "<div style='font-size:0.68rem;font-weight:850;"
            "color:#FFFFFF;'>Planner</div>"
            "</div>"
            "<div style='display:grid;grid-template-columns:"
            "repeat(7,minmax(0,1fr));gap:2px;'>"
            + header_html
            + "".join(cells_html)
            + "</div></div>"
        ),
        unsafe_allow_html=True,
    )



def planner_time_sort_key(activity: dict) -> tuple:
    """
    Ordina le attività in base all'orario di inizio.
    Gli orari mancanti o non validi vengono posizionati in fondo,
    mantenendo un ordinamento stabile.
    """
    raw_time = str(
        activity.get("start_time", "")
    ).strip()

    if not raw_time:
        return (1, 24, 60, raw_time)

    normalised = raw_time.replace(".", ":")
    parts = normalised.split(":")

    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0

        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError

        return (0, hour, minute, raw_time)
    except Exception:
        return (1, 24, 60, raw_time)


def sort_planner_activities(
    activities: list[dict],
) -> list[dict]:
    """Restituisce una nuova lista ordinata per orario."""
    return sorted(
        list(activities),
        key=planner_time_sort_key,
    )




PLANNER_EXERCISE_ACTIVITY_TYPES = {
    "Field Session",
    "Gym Session",
    "Pre-Activation",
}

PLANNER_EXERCISE_CATEGORIES = [
    "Warm-up",
    "Technical",
    "Tactical",
    "Strength",
    "Power",
    "Plyometrics",
    "Speed",
    "Acceleration",
    "Deceleration",
    "Change of Direction",
    "Mobility",
    "Core",
    "Upper Body",
    "Lower Body",
    "Recovery",
    "Other",
]


def planner_activity_item_label(
    activity_type: str,
) -> str:
    """Nome dell'elemento interno in base al tipo di attività."""
    if activity_type == "Field Session":
        return "Esercitazione"
    return "Esercizio"



def planner_default_activity(
    day_participants: list[str],
) -> dict:
    return {
        "type": "Field Session",
        "title": "",
        "start_time": "",
        "notes": "",
        "participants": list(day_participants),
        "drills": [],
    }



def fmt_duration(value: float) -> str:
    if pd.isna(value):
        return "N/D"
    total_seconds = max(0, int(round(float(value))))
    minutes, seconds = divmod(total_seconds, 60)
    return f"{minutes:02d}:{seconds:02d}"


def fmt_metric(value: float, metric_name: str) -> str:
    if metric_format(metric_name) == "duration":
        return fmt_duration(value)
    return fmt(value, metric_decimals(metric_name))



_report_selector_groups_rendered: set[str] = set()


def render_reportable_chart(
    figure,
    title: str,
    key: str,
    use_container_width: bool = True,
    config: dict | None = None,
    selection_group: str | None = None,
    report_enabled: bool = True,
    report_figure=None,
    show_selector: bool = True,
) -> None:
    st.plotly_chart(
        figure,
        use_container_width=use_container_width,
        config=config,
        key=key,
    )

    if not report_enabled:
        return

    if "report_catalog" not in st.session_state:
        st.session_state.report_catalog = {}

    report_group = selection_group or key

    figure_for_report = (
        report_figure
        if report_figure is not None
        else figure
    )

    st.session_state.report_catalog[key] = {
        "title": title,
        "figure_json": figure_for_report.to_json(),
        "selection_group": report_group,
    }

    if show_selector:
        render_compact_report_selector(report_group)


def render_compact_report_selector(report_group: str) -> None:
    """Comando report discreto e orizzontale, una sola volta per gruppo."""
    if report_group in _report_selector_groups_rendered:
        return
    _report_selector_groups_rendered.add(report_group)
    st.checkbox(
        "Aggiungi box plot al report",
        key=f"report_select_group_{report_group}",
        help="Aggiunge al report tutti i box plot del parametro.",
    )



def reference_status(z_score: float) -> tuple[str, str]:
    if pd.isna(z_score):
        return "Storico non disponibile", "pas-status-moderate"

    absolute_z = abs(float(z_score))
    if absolute_z <= 0.5:
        return "In linea con lo storico", "pas-status-normal"
    if absolute_z <= 1.0:
        return "Scostamento moderato", "pas-status-moderate"
    return "Scostamento rilevante", "pas-status-high"


def render_metric_card_header(
    title: str,
    value: float,
    metric_name: str,
    delta_pct: float,
    z_score: float,
    period_stats: dict,
    accumulation_value: float,
    accumulation_text: str,
    secondary_text: str | None = None,
    reference_count: int = 0,
    reference_detail: str = "",
) -> None:
    """
    Mantiene il layout originale delle card.
    Solo la card RPE non mostra il riquadro dell'accumulo.
    """
    status_text, status_class = reference_status(z_score)

    if pd.isna(delta_pct):
        delta_text = status_text
    else:
        delta_text = f"{delta_pct:+.1f}% · {status_text}"

    display_value = fmt_metric(value, metric_name)
    display_mean = fmt_metric(
        period_stats["mean"],
        metric_name,
    )
    display_median = fmt_metric(
        period_stats["median"],
        metric_name,
    )
    display_sd = fmt_metric(
        period_stats["sd"],
        metric_name,
    )
    secondary_html = (
        f'<div class="pas-card-secondary">{secondary_text}</div>'
        if secondary_text
        else ""
    )
    reference_html = (
        f'<div class="pas-card-reference" title="{reference_detail}">'
        f'vs media omologa · n={int(reference_count)}</div>'
        if reference_count > 0
        else '<div class="pas-card-reference">media omologa non disponibile</div>'
    )

    stats_html = f"""
<div class="pas-card-stats">
    <div class="pas-card-stat"><span class="pas-card-stat-label">Media</span><span class="pas-card-stat-value">{display_mean}</span></div>
    <div class="pas-card-stat"><span class="pas-card-stat-label">Mediana</span><span class="pas-card-stat-value">{display_median}</span></div>
    <div class="pas-card-stat"><span class="pas-card-stat-label">SD</span><span class="pas-card-stat-value">{display_sd}</span></div>
    <div class="pas-card-stat"><span class="pas-card-stat-label">CV</span><span class="pas-card-stat-value">{fmt(period_stats['cv'], 1)}%</span></div>
</div>
"""

    if metric_name == "RPE":
        html = f"""
<div class="pas-dashboard-card-marker"></div>
<div class="pas-card-title">{title}</div>
<div class="pas-card-value">{display_value}</div>
{secondary_html}
<div class="pas-card-delta {status_class}">{delta_text}</div>
{reference_html}
{stats_html}
"""
    else:
        display_accumulation = fmt_metric(
            accumulation_value,
            metric_name,
        )

        html = f"""
<div class="pas-dashboard-card-marker"></div>
<div class="pas-card-title">{title}</div>
<div class="pas-card-value">{display_value}</div>
{secondary_html}
<div class="pas-card-delta {status_class}">{delta_text}</div>
{reference_html}
{stats_html}
<div class="pas-card-accumulation">
    <div class="pas-card-accumulation-label">
        {accumulation_text}
    </div>
    <div class="pas-card-accumulation-value">
        {display_accumulation}
    </div>
</div>
"""

    st.markdown(
        html.strip(),
        unsafe_allow_html=True,
    )


def calculate_accumulation(
    player_day: pd.DataFrame,
    metric_name: str,
    overview_mode: str,
    overview_player: str | None,
) -> float:
    """
    Accumulo Dashboard:
    - Team Overview: calcola il Team Average di ogni giornata
      e poi somma le medie giornaliere;
    - Player Overview: somma i valori giornalieri del giocatore;
    - Max Speed: massimo del periodo. Nel Team Overview è il
      massimo dei Team Average giornalieri.
    """
    if player_day.empty:
        return np.nan

    metric_column = METRICS[metric_name]["column"]
    is_max_speed = metric_name == "Max Speed (km/h)"

    if metric_column not in player_day.columns:
        return np.nan

    if overview_mode == "Player Overview":
        values = pd.to_numeric(
            player_day.loc[
                player_day["Athlete"].eq(overview_player),
                metric_column,
            ],
            errors="coerce",
        ).dropna()

        if values.empty:
            return np.nan

        if is_max_speed:
            return float(values.max())

        return float(values.sum())

    daily_team_average = (
        player_day.assign(
            _metric_value=pd.to_numeric(
                player_day[metric_column],
                errors="coerce",
            )
        )
        .dropna(subset=["_metric_value"])
        .groupby("Date", as_index=False)["_metric_value"]
        .mean()
    )

    if daily_team_average.empty:
        return np.nan

    if is_max_speed:
        return float(
            daily_team_average["_metric_value"].max()
        )

    return float(
        daily_team_average["_metric_value"].sum()
    )


def accumulation_label(
    metric_name: str,
    overview_mode: str,
) -> str:
    if metric_name == "Max Speed (km/h)":
        return (
            "Picco Team Average nel periodo"
            if overview_mode == "Team Overview"
            else "Picco giocatore nel periodo"
        )

    return (
        "Somma Team Average del periodo"
        if overview_mode == "Team Overview"
        else "Totale giocatore nel periodo"
    )




def _normalize_player_photo_name(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFKD",
        str(value),
    )
    normalized = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        " ",
        normalized,
    ).strip().upper()
    return " ".join(sorted(normalized.split()))


def find_player_photo(
    base_dir: Path,
    athlete: str,
) -> Path | None:
    """
    Trova automaticamente la foto usando il nome Athlete.
    Gestisce ordine nome/cognome, accenti e trattini.
    """
    photos_dir = base_dir / "assets" / "players"
    if not photos_dir.exists():
        return None

    aliases = {
        "AKPA AKPRO JEAN DANIEL": "Akpa-Akpro",
        "AL MUSRATI MOATASEM": "Al-Musrati",
        "VALENTINI NICHOLAS": "Valentini Nicolas",
    }

    clean_athlete = re.sub(
        r"[^A-Za-z0-9À-ÿ]+",
        " ",
        str(athlete),
    ).strip().upper()
    requested_alias = aliases.get(clean_athlete)

    if requested_alias:
        for image_path in photos_dir.iterdir():
            if (
                image_path.is_file()
                and image_path.stem.lower()
                == requested_alias.lower()
            ):
                return image_path

    athlete_key = _normalize_player_photo_name(athlete)

    for image_path in photos_dir.iterdir():
        if not image_path.is_file():
            continue
        if image_path.suffix.lower() not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
        }:
            continue
        if (
            _normalize_player_photo_name(image_path.stem)
            == athlete_key
        ):
            return image_path

    return None



def build_performance_model(
    match_player_day: pd.DataFrame,
    metric_specs: dict[str, dict],
    min_matches: int = 5,
) -> pd.DataFrame:
    """
    Modello individuale basato sulle partite.

    Per le metriche di volume/evento il riferimento è calcolato
    al minuto. In fase di confronto il rate individuale viene
    moltiplicato per la durata effettiva della partita analizzata.

    Restano in valore assoluto:
    - Max Speed
    - Relative Distance
    - MPE Rec Avg Time

    Duration resta una variabile di contesto e non genera un target.
    Gli outlier sono esclusi oltre ±2 deviazioni standard.
    """
    duration_column = METRICS["Duration (min)"]["column"]
    absolute_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    rows: list[dict[str, object]] = []

    for athlete, athlete_data in match_player_day.groupby("Athlete"):
        row: dict[str, object] = {"Athlete": athlete}
        valid_counts: list[int] = []

        duration_values = pd.to_numeric(
            athlete_data.get(duration_column),
            errors="coerce",
        )

        for metric_name, meta in metric_specs.items():
            column = meta["column"]

            if column not in athlete_data.columns:
                row[column] = np.nan
                row[f"{column}__per_min"] = np.nan
                row[f"{column}__n"] = 0
                continue

            metric_values = pd.to_numeric(
                athlete_data[column],
                errors="coerce",
            )

            if metric_name == "Duration (min)":
                values = metric_values.dropna()
                storage_column = column
            elif metric_name in absolute_metrics:
                values = metric_values.dropna()
                storage_column = column
            else:
                valid_mask = (
                    metric_values.notna()
                    & duration_values.notna()
                    & duration_values.gt(0)
                )
                values = (
                    metric_values.loc[valid_mask]
                    / duration_values.loc[valid_mask]
                )
                storage_column = f"{column}__per_min"

            if len(values) >= 3:
                sd = float(values.std(ddof=0))
                mean = float(values.mean())
                if sd > 0:
                    values = values[
                        values.between(
                            mean - 2 * sd,
                            mean + 2 * sd,
                        )
                    ]

            row[storage_column] = (
                float(values.mean())
                if not values.empty
                else np.nan
            )
            row[f"{column}__n"] = int(len(values))
            valid_counts.append(int(len(values)))

        row["Model Status"] = (
            "Consolidato"
            if valid_counts and min(valid_counts) >= min_matches
            else "Provvisorio"
        )
        rows.append(row)

    return pd.DataFrame(rows)


def build_projected_targets(
    match_values: pd.DataFrame,
    performance_model: pd.DataFrame,
    metric_specs: dict[str, dict],
) -> pd.DataFrame:
    """
    Costruisce il target specifico per ciascun giocatore nella
    partita analizzata.

    Target = modello al minuto × durata effettiva della partita.
    Max Speed, Relative Distance e MPE Rec Avg Time restano assoluti.
    Duration non riceve una linea target.
    """
    if match_values.empty or performance_model.empty:
        return pd.DataFrame()

    duration_column = METRICS["Duration (min)"]["column"]
    absolute_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    merged = match_values[["Athlete", duration_column]].merge(
        performance_model,
        on="Athlete",
        how="left",
        suffixes=("", "__model"),
    )

    targets = pd.DataFrame({
        "Athlete": merged["Athlete"],
    })

    durations = pd.to_numeric(
        merged[duration_column],
        errors="coerce",
    )

    for metric_name, meta in metric_specs.items():
        column = meta["column"]

        if metric_name == "Duration (min)":
            targets[column] = np.nan
        elif metric_name in absolute_metrics:
            targets[column] = pd.to_numeric(
                merged.get(column),
                errors="coerce",
            )
        else:
            rates = pd.to_numeric(
                merged.get(f"{column}__per_min"),
                errors="coerce",
            )
            targets[column] = rates * durations

    return targets


def model_display_value(
    model_row: pd.Series,
    metric_name: str,
    metric_meta: dict,
) -> tuple[str, str, str | None]:
    """
    Card Performance Model:
    - metriche normalizzate proiettate sui 90 minuti;
    - valore al minuto mostrato con un decimale;
    - Max Speed, Relative Distance e MPE Rec Avg Time assolute.
    """
    column = metric_meta["column"]
    absolute_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    if metric_name in absolute_metrics:
        return (
            fmt_metric(model_row.get(column), metric_name),
            metric_meta.get("unit", ""),
            None,
        )

    per_minute_value = model_row.get(f"{column}__per_min")

    if pd.isna(per_minute_value):
        return (
            "N/D",
            metric_meta.get("unit", ""),
            None,
        )

    projected_value = float(per_minute_value) * 90
    decimals = int(metric_meta.get("decimals", 0))

    projected_display = (
        f"{projected_value:.{decimals}f}"
        .replace(".", ",")
    )
    per_minute_display = (
        f"{float(per_minute_value):.1f}"
        .replace(".", ",")
    )

    return (
        projected_display,
        metric_meta.get("unit", ""),
        per_minute_display,
    )





def performance_model_selected_match_value(
    player_matches: pd.DataFrame,
    metric_name: str,
    metric_meta: dict,
    selected_match_date: pd.Timestamp | None,
) -> float:
    """Valore della partita selezionata nella scala del modello."""
    if selected_match_date is None or player_matches.empty:
        return np.nan

    column = metric_meta["column"]
    duration_column = METRICS["Duration (min)"]["column"]
    absolute_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    selected_rows = player_matches[
        player_matches["Date"].dt.normalize().eq(
            pd.Timestamp(selected_match_date).normalize()
        )
    ].copy()

    if selected_rows.empty or column not in selected_rows.columns:
        return np.nan

    metric_values = pd.to_numeric(
        selected_rows[column],
        errors="coerce",
    )

    if metric_name in absolute_metrics:
        valid_values = metric_values.dropna()
        return (
            float(valid_values.mean())
            if not valid_values.empty
            else np.nan
        )

    durations = pd.to_numeric(
        selected_rows.get(duration_column),
        errors="coerce",
    )
    valid = (
        metric_values.notna()
        & durations.notna()
        & durations.gt(0)
    )

    if not valid.any():
        return np.nan

    projected_values = (
        metric_values.loc[valid]
        / durations.loc[valid]
        * 90
    )
    return float(projected_values.mean())



def performance_model_distribution_chart(
    player_matches: pd.DataFrame,
    metric_name: str,
    metric_meta: dict,
    selected_match_date: pd.Timestamp | None,
    model_row: pd.Series,
):
    """Box plot con punti partita e match selezionato evidenziato."""
    column = metric_meta["column"]
    duration_column = METRICS["Duration (min)"]["column"]
    absolute_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    extra_columns = [
        c for c in ["Match Day +/-"]
        if c in player_matches.columns
    ]
    plot_data = player_matches[
        ["Date", column, duration_column, *extra_columns]
    ].copy()

    if "Match Day +/-" not in plot_data.columns:
        plot_data["Match Day +/-"] = "MATCH"
    plot_data["Match Reference"] = (
        plot_data["Match Day +/-"]
        .fillna("MATCH")
        .astype(str)
        + " · "
        + plot_data["Date"].dt.strftime("%d/%m/%Y")
    )
    plot_data[column] = pd.to_numeric(
        plot_data[column],
        errors="coerce",
    )
    plot_data[duration_column] = pd.to_numeric(
        plot_data[duration_column],
        errors="coerce",
    )

    if metric_name in absolute_metrics:
        plot_data["Display Value"] = plot_data[column]
        model_value = model_row.get(column)
        display_unit = metric_meta.get("unit", "")
    else:
        valid_duration = plot_data[duration_column].gt(0)
        plot_data.loc[
            valid_duration,
            "Display Value",
        ] = (
            plot_data.loc[valid_duration, column]
            / plot_data.loc[valid_duration, duration_column]
        )
        model_rate = model_row.get(f"{column}__per_min")
        model_value = (
            float(model_rate)
            if pd.notna(model_rate)
            else np.nan
        )
        base_unit = metric_meta.get("unit", "")
        display_unit = (
            f"{base_unit}/min"
            if base_unit
            else "/min"
        )

    plot_data = plot_data.dropna(
        subset=["Display Value", "Date"]
    ).sort_values("Date")

    selected_mask = pd.Series(False, index=plot_data.index)
    if selected_match_date is not None:
        selected_mask = plot_data["Date"].dt.normalize().eq(
            pd.Timestamp(selected_match_date).normalize()
        )

    base_points = plot_data.loc[~selected_mask]
    selected_points = plot_data.loc[selected_mask]
    unit = display_unit

    figure = go.Figure()

    figure.add_trace(
        go.Box(
            y=plot_data["Display Value"],
            name=metric_name,
            boxpoints=False,
            marker_color=metric_meta.get("color"),
            line_color=metric_meta.get("color"),
            fillcolor="rgba(255,255,255,0.04)",
            hoverinfo="skip",
        )
    )

    figure.add_trace(
        go.Scatter(
            x=[metric_name] * len(base_points),
            y=base_points["Display Value"],
            mode="markers",
            name="Altre partite",
            marker=dict(
                size=9,
                color=metric_meta.get("color"),
                opacity=0.68,
                line=dict(width=0.7, color="#FFFFFF"),
            ),
            customdata=base_points["Match Reference"],
            hovertemplate=(
                "<b>%{customdata}</b><br>"
                "Valore: %{y:.1f} "
                + unit
                + "<extra></extra>"
            ),
        )
    )

    if not selected_points.empty:
        selected_display_value = float(
            selected_points["Display Value"].mean()
        )
        selected_label = (
            f"{selected_display_value:.1f}"
            + (f" {unit}" if unit else "")
        )

        figure.add_trace(
            go.Scatter(
                x=[metric_name] * len(selected_points),
                y=selected_points["Display Value"],
                mode="markers+text",
                text=[selected_label] * len(selected_points),
                textposition="top center",
                textfont=dict(
                    size=12,
                    color="#000000",
                    family="Arial Black",
                ),
                name="Partita selezionata",
                marker=dict(
                    size=15,
                    color="#F4C430",
                    symbol="diamond",
                    line=dict(width=2, color="#071426"),
                ),
                customdata=selected_points["Match Reference"],
                hovertemplate=(
                    "<b>%{customdata}</b><br>"
                    "Valore: %{y:.1f} "
                    + unit
                    + "<extra></extra>"
                ),
            )
        )

    if pd.notna(model_value):
        avg_label = (
            f"AVG {float(model_value):.1f}"
            + (f" {unit}" if unit else "")
        )
        figure.add_hline(
            y=float(model_value),
            line_color="#D62839",
            line_width=2,
            line_dash="dash",
            annotation_text=avg_label,
            annotation_position="top right",
        )

    figure.update_layout(
        height=390,
        margin=dict(l=30, r=30, t=35, b=30),
        yaxis_title=unit,
        xaxis_title="",
        showlegend=True,
    )
    return figure



def match_value_target_chart(
    values: pd.DataFrame,
    targets: pd.DataFrame,
    metric_name: str,
    metric_meta: dict,
):
    column = metric_meta["column"]
    plot = values[["Athlete", column]].copy()
    plot[column] = pd.to_numeric(
        plot[column],
        errors="coerce",
    )
    plot = plot.dropna(subset=[column]).sort_values(column)

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=plot[column],
            y=plot["Athlete"],
            orientation="h",
            name="Partita",
            marker_color=metric_meta.get("color"),
            text=[
                fmt_metric(value, metric_name)
                for value in plot[column]
            ],
            textposition="outside",
        )
    )

    if not targets.empty and column in targets.columns:
        target_lookup = targets.set_index("Athlete")[column]
        target_values = [
            target_lookup.get(athlete, np.nan)
            for athlete in plot["Athlete"]
        ]
        fig.add_trace(
            go.Scatter(
                x=target_values,
                y=plot["Athlete"],
                mode="markers",
                name="Modello individuale",
                marker=dict(
                    symbol="line-ns-open",
                    size=24,
                    line=dict(width=3),
                    color="#D62839",
                ),
                customdata=[
                    fmt_metric(value, metric_name)
                    if pd.notna(value)
                    else "N/D"
                    for value in target_values
                ],
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    "Target: %{customdata}<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=max(340, 36 * len(plot)),
        margin=dict(l=20, r=50, t=30, b=30),
        xaxis_title=metric_meta.get("unit", ""),
        yaxis_title="",
        showlegend=True,
    )
    return fig






FORECAST_METRICS = {
    "Distance (m)": {
        "source": "D Rel",
        "color": "#91D14F",
        "unit": "m",
        "decimals": 0,
    },
    "Acc Events (n°)": {
        "source": "Acc/min",
        "color": "#8FB9DE",
        "unit": "n°",
        "decimals": 0,
    },
    "Dec Events (n°)": {
        "source": "Dec/min",
        "color": "#7FDBE2",
        "unit": "n°",
        "decimals": 0,
    },
    "Distance 19.8-25.2 km/h (m)": {
        "source": "z3/ min",
        "color": "#FFD966",
        "unit": "m",
        "decimals": 0,
    },
    "Distance >25.2 km/h (m)": {
        "source": "z4/min",
        "color": "#FF6B00",
        "unit": "m",
        "decimals": 0,
    },
    "Speed Events (n°)": {
        "source": "Sprint/min",
        "color": "#F4A582",
        "unit": "n°",
        "decimals": 0,
    },
}

DRILL_ANALYSIS_METRICS = {
    "Relative Distance (m/min)": {
        "column": "avg speed (m/min)",
        "unit": "m/min",
        "color": "#54A24B",
    },
    "Acc Events (n°/min)": {
        "column": "acc events/min",
        "unit": "n°/min",
        "color": "#5DA5DA",
    },
    "Dec Events (n°/min)": {
        "column": "dec events /min",
        "unit": "n°/min",
        "color": "#F2CF5B",
    },
    "19.8-25.2 km/h (m/min)": {
        "column": "distance/speed Z3 (m) /min",
        "unit": "m/min",
        "color": "#F58518",
    },
    ">25.2 km/h (m/min)": {
        "column": "distance/speed Z4 (m)/min",
        "unit": "m/min",
        "color": "#E45756",
    },
    "Speed Events (n°/min)": {
        "column": "Speed Events/min",
        "unit": "n°/min",
        "color": "#8E63CE",
    },
}



def normalise_column_key(value: str) -> str:
    """Normalizza un'intestazione per confronti robusti."""
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).strip().lower(),
    )


def ensure_exercise_metric_aliases(
    frame: pd.DataFrame,
) -> pd.DataFrame:
    """
    Crea le intestazioni canoniche usate dal PAS partendo anche
    da varianti di maiuscole, spazi o simboli.
    """
    result = frame.copy()

    alias_groups = {
        "avg speed (m/min)": [
            "avg speed (m/min)",
            "average speed (m/min)",
        ],
        "acc events/min": [
            "acc events/min",
            "acc events /min",
            "acc/min",
        ],
        "dec events /min": [
            "dec events /min",
            "dec events/min",
            "dec/min",
        ],
        "distance/speed Z3 (m) /min": [
            "distance/speed Z3 (m) /min",
            "distance/speed Z3 (m)/min",
            "z3/min",
            "z3/ min",
        ],
        "distance/speed Z4 (m)/min": [
            "distance/speed Z4 (m)/min",
            "distance/speed Z4 (m) /min",
            "z4/min",
            "z4/ min",
        ],
        "Speed Events/min": [
            "Speed Events/min",
            "Speed Events (n°/min)",
            "speed events/min",
            "speed events /min",
            "sprint/min",
        ],
    }

    current_lookup = {
        normalise_column_key(column): column
        for column in result.columns
    }

    for canonical, aliases in alias_groups.items():
        if canonical in result.columns:
            continue

        source_column = None
        for alias in aliases:
            source_column = current_lookup.get(
                normalise_column_key(alias)
            )
            if source_column is not None:
                break

        if source_column is not None:
            result[canonical] = result[source_column]

    return result



@st.cache_data(show_spinner=False)
def load_exercise_sheets(data_provider, excel_source):
    """
    Carica i fogli Esercitazioni ed Esercitazioni Avg.
    """
    exercises, averages = data_provider.load_drills_data(
        excel_source,
    )

    exercises.columns = [
        str(column).strip()
        for column in exercises.columns
    ]
    averages.columns = [
        str(column).strip()
        for column in averages.columns
    ]

    exercises = exercises.loc[
        :,
        ~exercises.columns.duplicated(keep="first"),
    ].copy()
    averages = averages.loc[
        :,
        ~averages.columns.duplicated(keep="first"),
    ].copy()

    exercises = ensure_exercise_metric_aliases(
        exercises
    )
    averages = ensure_exercise_metric_aliases(
        averages
    )

    for frame in [exercises, averages]:
        frame.replace(
            ["#DIV/0!", "#N/A", "#VALUE!", ""],
            np.nan,
            inplace=True,
        )

    if "Date" in exercises.columns:
        exercises["Date"] = pd.to_datetime(
            exercises["Date"],
            errors="coerce",
        )

    for column in exercises.columns:
        if column not in {
            "Date",
            "Drill",
            "App",
            "Role",
            "Athlete",
        }:
            exercises[column] = pd.to_numeric(
                exercises[column],
                errors="coerce",
            )

    for column in averages.columns:
        if column not in {"Drill", "Role"}:
            averages[column] = pd.to_numeric(
                averages[column],
                errors="coerce",
            )

    exercises["Drill"] = (
        exercises["Drill"]
        .astype(str)
        .str.strip()
    )
    exercises["Role"] = (
        exercises["Role"]
        .fillna("N/D")
        .astype(str)
        .str.strip()
    )
    averages["Drill"] = (
        averages["Drill"]
        .astype(str)
        .str.strip()
    )
    averages["Role"] = (
        averages["Role"]
        .fillna("N/D")
        .astype(str)
        .str.strip()
    )

    exercises = exercises[
        exercises["Drill"].notna()
        & exercises["Drill"].ne("nan")
        & exercises["Drill"].ne("/")
    ].copy()
    averages = averages[
        averages["Drill"].notna()
        & averages["Drill"].ne("nan")
        & averages["Drill"].ne("/")
    ].copy()

    return exercises, averages


def forecast_calculation(
    plan: pd.DataFrame,
    averages: pd.DataFrame,
    role: str,
) -> pd.DataFrame:
    role_data = averages[
        averages["Role"].eq(role)
    ].copy()

    result_rows = []

    for _, plan_row in plan.iterrows():
        drill_name = str(
            plan_row.get("Drill", "")
        ).strip()
        duration = pd.to_numeric(
            pd.Series(
                [plan_row.get("Duration (min)", 0)]
            ),
            errors="coerce",
        ).iloc[0]

        if not drill_name or drill_name == "—":
            continue
        if pd.isna(duration) or float(duration) <= 0:
            continue

        source_row = role_data[
            role_data["Drill"].eq(drill_name)
        ]

        row = {
            "Drill": drill_name,
            "Duration (min)": float(duration),
        }

        for metric_name, metric_meta in (
            FORECAST_METRICS.items()
        ):
            source_column = metric_meta["source"]
            rate = (
                pd.to_numeric(
                    source_row[source_column],
                    errors="coerce",
                ).mean()
                if (
                    not source_row.empty
                    and source_column in source_row.columns
                )
                else np.nan
            )
            row[metric_name] = (
                float(rate) * float(duration)
                if pd.notna(rate)
                else 0.0
            )

        result_rows.append(row)

    return pd.DataFrame(result_rows)


def forecast_metric_chart(
    calculated: pd.DataFrame,
    metric_name: str,
):
    meta = FORECAST_METRICS[metric_name]

    figure = go.Figure(
        go.Bar(
            x=calculated["Drill"],
            y=calculated[metric_name],
            text=[
                f"{value:.0f}"
                for value in calculated[metric_name]
            ],
            textposition="outside",
            marker_color=meta["color"],
            name=metric_name,
        )
    )
    figure.update_layout(
        height=350,
        margin=dict(l=25, r=20, t=25, b=80),
        xaxis_title="Drill",
        yaxis_title=meta["unit"],
        showlegend=False,
    )
    return figure



def safe_numeric_series(
    frame: pd.DataFrame | None,
    column: str,
) -> pd.Series:
    """Restituisce sempre una Series numerica valida."""
    if frame is None or not isinstance(frame, pd.DataFrame):
        return pd.Series(dtype="float64")

    if column not in frame.columns:
        return pd.Series(
            np.nan,
            index=frame.index,
            dtype="float64",
        )

    source = frame.loc[:, column]
    if isinstance(source, pd.DataFrame):
        source = source.iloc[:, 0]

    return pd.to_numeric(
        source,
        errors="coerce",
    )



def build_drill_occurrences(
    source: pd.DataFrame,
    selected_drills: list[str],
    metric_name: str,
    analysis_mode: str,
    selected_entities: list[str],
) -> pd.DataFrame:
    """
    Crea un punto per ogni occorrenza Drill-Date.

    Modalità Roles:
    - Team Average = media di tutti i giocatori presenti nell'occorrenza.
    - altri ruoli = media dei giocatori di quel ruolo nell'occorrenza.

    Modalità Players:
    - ogni punto è il valore del singolo giocatore in quella data e drill.
    """
    meta = DRILL_ANALYSIS_METRICS[metric_name]
    column = meta["column"]

    if column not in source.columns:
        return pd.DataFrame()

    base = source[
        source["Drill"].isin(selected_drills)
    ].copy()
    base[column] = pd.to_numeric(
        base[column],
        errors="coerce",
    )
    base = base.dropna(
        subset=["Date", "Drill", column]
    )

    rows = []

    if analysis_mode == "Roles":
        for entity_name in selected_entities:
            if entity_name == "Team Average":
                entity_source = base.copy()
            else:
                entity_source = base[
                    base["Role"].eq(entity_name)
                ].copy()

            if entity_source.empty:
                continue

            grouped = (
                entity_source
                .groupby(
                    ["Date", "Drill"],
                    as_index=False,
                )[column]
                .mean()
            )
            grouped["Entity"] = entity_name
            grouped.rename(
                columns={column: "Metric Value"},
                inplace=True,
            )
            rows.append(grouped)

    else:
        player_source = base[
            base["Athlete"].isin(selected_entities)
        ].copy()

        if not player_source.empty:
            grouped = (
                player_source
                .groupby(
                    ["Date", "Drill", "Athlete"],
                    as_index=False,
                )[column]
                .mean()
            )
            grouped.rename(
                columns={
                    column: "Metric Value",
                    "Athlete": "Entity",
                },
                inplace=True,
            )
            rows.append(grouped)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(
        rows,
        ignore_index=True,
    )
    result["Occurrence"] = (
        result["Date"].dt.strftime("%Y-%m-%d")
        + " | "
        + result["Drill"].astype(str)
    )
    return result


DRILL_BOXPLOT_PALETTE = [
    "#2F80ED",  # Blu PAS
    "#27AE60",  # Verde
    "#EB5757",  # Rosso
    "#F2994A",  # Arancione
    "#9B51E0",  # Viola
    "#2DCCCD",  # Ciano
    "#F2C94C",  # Giallo
    "#E056B5",  # Magenta
    "#A66A3F",  # Marrone
    "#BDBDBD",  # Grigio chiaro
]


def _drill_box_color(drill_index: int) -> str:
    """Restituisce uno dei dieci colori fissi associati ai drill selezionati."""
    return DRILL_BOXPLOT_PALETTE[drill_index % len(DRILL_BOXPLOT_PALETTE)]


def _drill_entity_short_label(entity_name: str, entity_label: str) -> str:
    """Etichetta compatta per evitare sovrapposizioni sopra i box plot."""
    label = str(entity_name).strip()
    if entity_label == "Role" or label == "Team Average":
        return label

    parts = [part for part in label.split() if part]
    if len(parts) <= 1:
        return label[:16]
    return f"{parts[0]} {parts[-1][0]}."[:18]


def drills_boxplot(
    occurrence_data: pd.DataFrame,
    selected_drills: list[str],
    selected_entities: list[str],
    metric_name: str,
    entity_label: str,
    for_report: bool = False,
):
    """
    Box plot per drill con un punto per ogni occorrenza.

    Box e punti usano un colore distinto per ciascun drill selezionato.
    La palette comprende dieci colori fissi e la legenda associa colore e drill.
    """
    meta = DRILL_ANALYSIS_METRICS[metric_name]
    figure = go.Figure()

    if occurrence_data.empty:
        return figure

    entity_count = max(1, len(selected_entities))

    for drill_index, drill_name in enumerate(selected_drills):
        drill_color = _drill_box_color(drill_index)
        drill_has_data = False

        for entity_index, entity_name in enumerate(selected_entities):
            valid = occurrence_data[
                occurrence_data["Drill"].eq(drill_name)
                & occurrence_data["Entity"].eq(entity_name)
            ].copy()

            if valid.empty:
                continue

            drill_has_data = True
            average_value = float(valid["Metric Value"].mean())
            customdata = np.column_stack(
                [
                    valid["Date"].dt.strftime("%d/%m/%Y"),
                    valid["Entity"].astype(str),
                    valid["Occurrence"].astype(str),
                ]
            )

            figure.add_trace(
                go.Box(
                    x=[drill_name] * len(valid),
                    y=valid["Metric Value"],
                    name=f"{drill_name} · {entity_name}",
                    legendgroup=drill_name,
                    offsetgroup=entity_name,
                    showlegend=False,
                    boxpoints="all",
                    jitter=0.30,
                    pointpos=0,
                    marker=dict(
                        size=9,
                        symbol="circle",
                        color=drill_color,
                        opacity=0.84,
                        line=dict(
                            width=0.9,
                            color="#FFFFFF",
                        ),
                    ),
                    line=dict(
                        color=drill_color,
                        width=1.6,
                    ),
                    fillcolor=drill_color,
                    opacity=0.72,
                    customdata=customdata,
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Data: %{customdata[0]}<br>"
                        "Occorrenza: %{customdata[2]}<br>"
                        "Valore: %{y:.2f} "
                        + meta["unit"]
                        + "<extra></extra>"
                    ),
                )
            )

            shift = (
                entity_index - (entity_count - 1) / 2
            ) * 34
            figure.add_annotation(
                x=drill_name,
                y=average_value,
                text=f"<b>AVG {average_value:.1f}</b>",
                showarrow=False,
                xshift=shift,
                yshift=13,
                font=dict(
                    size=10,
                    color=(
                        "#000000"
                        if for_report
                        else drill_color
                    ),
                    family=(
                        "Arial Black"
                        if for_report
                        else "Arial"
                    ),
                ),
            )

        if drill_has_data:
            figure.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="markers",
                    name=drill_name,
                    legendgroup=drill_name,
                    marker=dict(
                        size=11,
                        symbol="square",
                        color=drill_color,
                        line=dict(width=1, color="#FFFFFF"),
                    ),
                    hoverinfo="skip",
                    showlegend=True,
                )
            )

    figure.update_layout(
        height=540,
        margin=dict(l=30, r=20, t=85, b=80),
        yaxis_title=meta["unit"],
        xaxis_title="Drill",
        boxmode="group",
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.12,
            xanchor="left",
            x=0,
            title_text=(
                "Drill · colore box plot"
            ),
        ),
    )
    return figure


def build_historical_max_speed_references(
    raw_data: pd.DataFrame,
) -> pd.DataFrame:
    """
    Max Speed storica individuale calcolata su tutto il database.
    """
    column = METRICS["Max Speed (km/h)"]["column"]

    if column not in raw_data.columns:
        return pd.DataFrame(
            columns=["Athlete", "Historical Max Speed"]
        )

    source = raw_data[["Athlete", column]].copy()
    source[column] = pd.to_numeric(
        source[column],
        errors="coerce",
    )
    source = source.dropna(
        subset=["Athlete", column]
    )

    if source.empty:
        return pd.DataFrame(
            columns=["Athlete", "Historical Max Speed"]
        )

    return (
        source.groupby("Athlete", as_index=False)[column]
        .max()
        .rename(
            columns={
                column: "Historical Max Speed",
            }
        )
    )


def build_max_speed_percentage_data(
    values_data: pd.DataFrame,
    historical_references: pd.DataFrame,
    team_average_mode: bool = False,
) -> pd.DataFrame:
    """
    Percentuale della Max Speed raggiunta rispetto alla Max Speed
    storica individuale.

    In modalità Team Average il denominatore è la media delle
    Max Speed storiche individuali.
    """
    max_speed_column = METRICS[
        "Max Speed (km/h)"
    ]["column"]
    pct_column = f"{max_speed_column}__match_pct"

    if (
        values_data.empty
        or historical_references.empty
        or max_speed_column not in values_data.columns
    ):
        return pd.DataFrame()

    result = values_data[["Athlete"]].copy()

    if team_average_mode:
        historical_values = pd.to_numeric(
            historical_references[
                "Historical Max Speed"
            ],
            errors="coerce",
        ).dropna()
        denominator = (
            float(historical_values.mean())
            if not historical_values.empty
            else np.nan
        )
        current_values = pd.to_numeric(
            values_data[max_speed_column],
            errors="coerce",
        )
        result[pct_column] = np.where(
            pd.notna(denominator) and denominator > 0,
            current_values / denominator * 100,
            np.nan,
        )
        return result

    merged = values_data[
        ["Athlete", max_speed_column]
    ].merge(
        historical_references,
        on="Athlete",
        how="left",
    )

    current_values = pd.to_numeric(
        merged[max_speed_column],
        errors="coerce",
    )
    historical_values = pd.to_numeric(
        merged["Historical Max Speed"],
        errors="coerce",
    )

    result[pct_column] = np.where(
        historical_values.gt(0),
        current_values / historical_values * 100,
        np.nan,
    )

    return result



def max_speed_percentage_lookup(
    values_data: pd.DataFrame,
    historical_references: pd.DataFrame,
    team_average_mode: bool = False,
) -> dict[str, float]:
    """Restituisce la % di Max Speed individuale indicizzata per atleta."""
    pct_data = build_max_speed_percentage_data(
        values_data,
        historical_references,
        team_average_mode=team_average_mode,
    )
    pct_column = f"{METRICS['Max Speed (km/h)']['column']}__match_pct"
    if pct_data.empty or pct_column not in pct_data.columns:
        return {}
    return {
        str(row["Athlete"]): float(row[pct_column])
        for _, row in pct_data.dropna(subset=[pct_column]).iterrows()
    }


def build_period_match_references(
    raw_data: pd.DataFrame,
    metric_specs: dict[str, dict],
) -> pd.DataFrame:
    """
    Riferimento gara individuale per il rapporto % Match.

    - Solo Drill = Match.
    - Metriche additive: valore/minuto, outlier ±2 SD,
      media del rate e proiezione sui 90 minuti.
    - Duration, RPE e Max Speed: media assoluta dopo outlier ±2 SD.
    """
    match_rows = raw_data[
        raw_data["Drill"].astype(str).str.strip().eq("Match")
    ].copy()

    if match_rows.empty:
        return pd.DataFrame()

    match_player_day = aggregate_player_day(match_rows)
    duration_column = metric_specs["Duration (min)"]["column"]
    absolute_metrics = {
        "Duration (min)",
        "RPE",
        "Max Speed (km/h)",
    }

    references: list[dict[str, object]] = []

    for athlete, athlete_data in match_player_day.groupby("Athlete"):
        row: dict[str, object] = {"Athlete": athlete}
        durations = pd.to_numeric(
            athlete_data.get(duration_column),
            errors="coerce",
        )

        for metric_name, meta in metric_specs.items():
            column = meta["column"]
            if column not in athlete_data.columns:
                row[column] = np.nan
                continue

            values = pd.to_numeric(
                athlete_data[column],
                errors="coerce",
            )

            if metric_name in absolute_metrics:
                reference_values = values.dropna()
            else:
                valid = (
                    values.notna()
                    & durations.notna()
                    & durations.gt(0)
                )
                reference_values = (
                    values.loc[valid]
                    / durations.loc[valid]
                )

            if len(reference_values) >= 3:
                mean_value = float(reference_values.mean())
                sd_value = float(reference_values.std(ddof=0))
                if sd_value > 0:
                    reference_values = reference_values[
                        reference_values.between(
                            mean_value - 2 * sd_value,
                            mean_value + 2 * sd_value,
                        )
                    ]

            if reference_values.empty:
                row[column] = np.nan
            elif metric_name in absolute_metrics:
                row[column] = float(reference_values.mean())
            else:
                row[column] = float(reference_values.mean()) * 90

        references.append(row)

    return pd.DataFrame(references)


def attach_match_load_percentages(
    period_data: pd.DataFrame,
    match_references: pd.DataFrame,
    selected_players: list[str],
    metric_specs: dict[str, dict],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Restituisce:
    - dati periodo invariati;
    - tabella percentuali rispetto al riferimento gara.
    """
    if period_data.empty or match_references.empty:
        return period_data.copy(), pd.DataFrame()

    percentages = period_data[["Athlete"]].copy()

    if not selected_players:
        team_reference: dict[str, object] = {
            "Athlete": "TEAM AVERAGE",
        }
        for metric_name, meta in metric_specs.items():
            column = meta["column"]
            values = safe_numeric_series(
                match_references,
                column,
            ).dropna()
            team_reference[column] = (
                float(values.mean())
                if not values.empty
                else np.nan
            )
        reference_lookup = pd.DataFrame([team_reference])
    else:
        reference_lookup = match_references[
            match_references["Athlete"].isin(selected_players)
        ].copy()

    merged = period_data[["Athlete"]].merge(
        reference_lookup,
        on="Athlete",
        how="left",
    )

    for metric_name, meta in metric_specs.items():
        column = meta["column"]
        if (
            metric_name == "Duration (min)"
            or column not in period_data.columns
        ):
            continue

        period_values = pd.to_numeric(
            period_data[column],
            errors="coerce",
        )
        reference_values = pd.to_numeric(
            merged.get(column),
            errors="coerce",
        )

        pct_column = f"{column}__match_pct"
        percentages[pct_column] = np.where(
            reference_values.gt(0),
            period_values / reference_values * 100,
            np.nan,
        )

    return period_data.copy(), percentages



def match_text(info: dict | None, future: bool) -> str:
    if not info:
        return "N/D"
    days = info["days"]
    if days == 0:
        distance = "oggi"
    elif future:
        distance = f"tra {days} giorni"
    else:
        distance = f"{days} giorni fa"
    return f"{info['name']} · {distance}"


@st.cache_data(show_spinner=False)
def load_forecast_sheet(data_provider, excel_source):
    """Carica tramite PAS Data Provider la tabella usata dal Forecast."""
    averages = data_provider.load_forecast_data(excel_source)
    averages.columns = [str(column).strip() for column in averages.columns]
    return averages.loc[:, ~averages.columns.duplicated(keep="first")].copy()


base_dir = Path(__file__).resolve().parent

_sidebar_logo = (
    base_dir
    / "assets"
    / "brand"
    / "hellas_verona_logo.png"
)
if _sidebar_logo.exists():
    st.sidebar.image(
        str(_sidebar_logo),
        width=64,
    )
st.sidebar.markdown("**PAS** · Performance Analysis System")
st.sidebar.caption("Hellas Verona FC")

provider_catalog = get_available_data_providers()
requested_provider_id = st.session_state.get("pas_data_source", "excel")
provider_selection = resolve_data_provider(requested_provider_id)
data_provider = provider_selection.provider
gpexe_analysis_fallback_message = st.session_state.get("pas_gpexe_analysis_fallback_message")

database_column, settings_column = st.sidebar.columns(2, gap="small")

with database_column:
    with st.popover(
        "🗄️ Database",
        use_container_width=True,
    ):
        using_gpexe = provider_selection.requested.provider_id == "gpexe"
        if using_gpexe:
            uploaded_database = st.session_state.get("pas_gpexe_export_upload")
            st.caption(
                "L'export GPExe si carica da Settings → PAS Connect. "
                "Senza un file valido il PAS usa temporaneamente Excel."
            )
        else:
            uploaded_database = st.file_uploader(
                "Carica database Excel",
                type=["xlsx", "xls"],
                help=(
                    "Se carichi un file, il PAS lo usa per questa sessione. "
                    "Altrimenti utilizza il database presente nella cartella."
                ),
                key="pas_primary_data_upload",
            )

        try:
            excel_provider = get_data_provider("excel")
            excel_path = excel_provider.resolve_default_source(base_dir)
            database_excel_source = str(excel_path)

            gpexe_api_database = PASConnectDatabase.default(base_dir).path
            gpexe_api_has_sessions = gpexe_api_database.is_file() and bool(available_sessions(gpexe_api_database))
            prefer_gpexe_api = st.session_state.get("pas_gpexe_input_mode", "API sincronizzata") == "API sincronizzata"
            selected_api_sessions = st.session_state.get("pas_gpexe_active_session_ids", [])
            gpexe_api_ready = gpexe_api_has_sessions and has_compatible_performance_rows(
                gpexe_api_database,
                session_ids=selected_api_sessions,
            )
            if using_gpexe and prefer_gpexe_api and gpexe_api_ready:
                database_path = gpexe_api_database
                gpexe_source = {
                    "kind": "gpexe_api",
                    "database_path": gpexe_api_database,
                    "session_ids": selected_api_sessions,
                }
                try:
                    raw = data_provider.load_performance_data(gpexe_source, source_name=gpexe_api_database.name)
                    match_source = data_provider.load_match_analysis_data(gpexe_source, source_name=gpexe_api_database.name)
                    report_source = data_provider.load_report_data(gpexe_source, source_name=gpexe_api_database.name)
                    database_source_label = "GPExe API sincronizzata"
                    st.session_state.pop("pas_gpexe_analysis_fallback_message", None)
                    gpexe_analysis_fallback_message = None
                except Exception:
                    gpexe_analysis_fallback_message = (
                        "I dati GPExe sono stati importati nel database PAS Connect, ma il collegamento "
                        "alle analisi sarà disponibile in una release successiva. Il PAS continua "
                        "temporaneamente a utilizzare Excel."
                    )
                    st.session_state["pas_gpexe_analysis_fallback_message"] = gpexe_analysis_fallback_message
                    st.session_state["pas_data_source"] = "excel"
                    database_path = excel_path
                    raw = excel_provider.load_performance_data(database_excel_source, source_name=excel_path.name)
                    match_source = excel_provider.load_match_analysis_data(database_excel_source, source_name=excel_path.name)
                    report_source = excel_provider.load_report_data(database_excel_source, source_name=excel_path.name)
                    database_source_label = "Fallback Excel · dati GPExe non ancora collegati alle analisi"
            elif using_gpexe and uploaded_database is not None:
                database_path = None
                gpexe_source = uploaded_database.getvalue()
                raw = data_provider.load_performance_data(gpexe_source, source_name=uploaded_database.name)
                match_source = data_provider.load_match_analysis_data(gpexe_source, source_name=uploaded_database.name)
                report_source = data_provider.load_report_data(gpexe_source, source_name=uploaded_database.name)
                database_source_label = "Export GPExe caricato"
            elif using_gpexe:
                if prefer_gpexe_api and gpexe_api_has_sessions:
                    gpexe_analysis_fallback_message = (
                        "I dati GPExe sono stati importati nel database PAS Connect, ma il collegamento "
                        "alle analisi sarà disponibile in una release successiva. Il PAS continua "
                        "temporaneamente a utilizzare Excel."
                    )
                    st.session_state["pas_gpexe_analysis_fallback_message"] = gpexe_analysis_fallback_message
                    st.session_state["pas_data_source"] = "excel"
                database_path = excel_path
                raw = excel_provider.load_performance_data(database_excel_source, source_name=excel_path.name)
                match_source = excel_provider.load_match_analysis_data(database_excel_source, source_name=excel_path.name)
                report_source = excel_provider.load_report_data(database_excel_source, source_name=excel_path.name)
                database_source_label = "Fallback Excel · usa dati locali GPExe o carica un export"
            elif uploaded_database is not None:
                database_path = None
                database_excel_source = uploaded_database.getvalue()
                raw = data_provider.load_performance_data(database_excel_source, source_name=uploaded_database.name)
                match_source = data_provider.load_match_analysis_data(database_excel_source, source_name=uploaded_database.name)
                report_source = data_provider.load_report_data(database_excel_source, source_name=uploaded_database.name)
                database_source_label = "File caricato"
            else:
                database_path = excel_path
                raw = data_provider.load_performance_data(database_excel_source, source_name=excel_path.name)
                match_source = data_provider.load_match_analysis_data(database_excel_source, source_name=excel_path.name)
                report_source = data_provider.load_report_data(database_excel_source, source_name=excel_path.name)
                database_source_label = "File nella cartella PAS"

            # Le tabelle di libreria Drills/Forecast non fanno parte dell'export GPExe.
            # Restano lette dal database Excel incluso senza modificarlo.
            exercises_raw, exercises_avg = load_exercise_sheets(excel_provider, database_excel_source)
            forecast_exercises_avg = load_forecast_sheet(excel_provider, database_excel_source)
        except Exception as exc:
            st.error("Errore nel caricamento del database.")
            st.error(str(exc))
            st.stop()

        if raw.empty:
            st.error(
                "Il database filtrato non contiene dati "
                "della stagione 2025-26 per la rosa selezionata."
            )
            st.stop()

        database_info = database_summary(raw)

        st.caption(
            f"{database_source_label}: "
            f"{database_info['source_name']}"
        )
        if gpexe_analysis_fallback_message:
            st.info(gpexe_analysis_fallback_message)
        st.caption(
            f"{database_info['players']} giocatori · "
            f"{database_info['sessions']} sessioni · "
            f"ultimo dato "
            f"{pd.Timestamp(database_info['last_date']).strftime('%d/%m/%Y')}"
        )

        with st.expander("Dettagli database", expanded=False):
            st.write(f"**Foglio:** {database_info['sheet_name']}")
            st.write(f"**Righe importate:** {database_info['rows']}")
            if pd.notna(database_info["first_date"]):
                st.write(
                    "**Prima data:** "
                    + pd.Timestamp(
                        database_info["first_date"]
                    ).strftime("%d/%m/%Y")
                )
            st.write("**Drill trovati:**")
            st.caption(", ".join(database_info["drills"]))

            if database_info["missing_metrics"]:
                st.warning(
                    "Metriche non trovate: "
                    + ", ".join(database_info["missing_metrics"])
                )
            else:
                st.caption("Tutte le metriche PAS sono disponibili.")

        if st.button(
            "Ricarica dati",
            help="Svuota la cache e rilegge il database.",
            use_container_width=True,
        ):
            st.cache_data.clear()
            st.rerun()

with settings_column:
    with st.popover(
        "⚙️ Settings",
        use_container_width=True,
    ):
        st.caption(f"PAS · {APP_EDITION} v{APP_BUILD_VERSION}")
        if gpexe_analysis_fallback_message:
            st.info(gpexe_analysis_fallback_message)
        st.caption(
            f"Database: {database_info['source_name']} · "
            f"ultimo dato "
            f"{pd.Timestamp(database_info['last_date']).strftime('%d/%m/%Y')}"
        )

        st.divider()
        st.markdown("#### PAS Connect")
        provider_ids = tuple(item.provider_id for item in provider_catalog)
        provider_labels = {item.provider_id: item.display_name for item in provider_catalog}
        selected_provider_id = st.selectbox(
            "Sorgente dati",
            options=provider_ids,
            index=provider_ids.index(provider_selection.requested.provider_id),
            format_func=provider_labels.get,
            key="pas_data_source",
            help=(
                "Excel resta la sorgente predefinita. GPExe può usare sessioni già sincronizzate localmente oppure un export."
            ),
        )
        current_selection = resolve_data_provider(selected_provider_id)
        if current_selection.fallback_applied:
            st.warning(current_selection.requested.status_message)
        else:
            st.caption(current_selection.effective.status_message)

        if selected_provider_id == "gpexe":
            st.radio(
                "Origine GPExe",
                options=("API sincronizzata", "File export"),
                horizontal=True,
                key="pas_gpexe_input_mode",
                help="La modalità API usa esclusivamente dati già presenti nel database PAS Connect locale.",
            )
            api_database_path = PASConnectDatabase.default(base_dir).path
            api_sessions = available_sessions(api_database_path)
            if st.session_state.get("pas_gpexe_input_mode") == "API sincronizzata":
                if api_sessions:
                    session_by_id = {int(item["provider_session_id"]): item for item in api_sessions}
                    session_options = tuple(session_by_id)
                    defaults = [sid for sid in st.session_state.get("pas_gpexe_active_session_ids", []) if sid in session_by_id]
                    selected_ids = st.multiselect(
                        "TeamSession locali attive nel PAS",
                        options=session_options,
                        default=defaults,
                        format_func=lambda sid: (
                            f"{str(session_by_id[sid].get('start_timestamp') or '')[:10]} · "
                            f"{session_by_id[sid].get('session_name') or sid}"
                        ),
                        key="pas_gpexe_active_session_ids",
                        help="Senza selezione vengono utilizzate tutte le TeamSession già memorizzate localmente.",
                    )
                    st.success(
                        f"Dati GPExe locali disponibili: {len(api_sessions)} TeamSession · "
                        f"{len(selected_ids) or len(api_sessions)} selezionate."
                    )
                else:
                    st.info("Nessuna TeamSession GPExe presente nel database PAS Connect locale.")
            gpexe_export = st.file_uploader(
                "Carica export GPExe",
                type=["csv", "xlsx", "xls", "json"],
                help=(
                    "Carica un export completo GPExe. Il file viene validato e "
                    "utilizzato in memoria; il database Excel incluso non viene modificato."
                ),
                key="pas_gpexe_export_upload",
            )
            if gpexe_export is None and st.session_state.get("pas_gpexe_input_mode") == "File export":
                st.info("Nessun export GPExe caricato: il PAS continua a utilizzare Excel.")
            elif gpexe_export is not None and using_gpexe and database_source_label == "Export GPExe caricato":
                st.success(
                    f"Export GPExe attivo: {gpexe_export.name} · "
                    f"{database_info['rows']} righe importate."
                )

        st.markdown("##### Connessione GPExe")
        st.caption(
            "La connessione verifica esclusivamente l'autenticazione GraphQL. "
            "Excel resta la sorgente predefinita e non viene modificato."
        )

        is_gpexe_connected = bool(st.session_state.get("pas_gpexe_connected", False))
        if is_gpexe_connected:
            connected_team_count = st.session_state.get("pas_gpexe_team_count")
            connected_base_url = st.session_state.get("pas_gpexe_connected_base_url", "")
            status_message = "Connesso a GPExe"
            if connected_team_count is not None:
                status_message += f" · Team rilevati: {connected_team_count}"
            if connected_base_url:
                status_message += f" · {connected_base_url}"
            st.success(status_message)
        else:
            st.info("Stato connessione: non connesso")

        try:
            gpexe_secrets = dict(st.secrets.get("gpexe", {}))
        except Exception:
            gpexe_secrets = {}

        gpexe_base_url = st.text_input(
            "API base URL",
            value=str(gpexe_secrets.get("base_url", "https://e15.gpexe.com/ui/v2/")),
            key="pas_gpexe_base_url",
            help="Endpoint GraphQL verificato dell’istanza GPExe: https://e15.gpexe.com/ui/v2/",
        )
        gpexe_username = st.text_input(
            "Email GPExe",
            value=str(gpexe_secrets.get("username", "")),
            key="pas_gpexe_username",
        )
        gpexe_password = st.text_input(
            "Password",
            value=str(gpexe_secrets.get("password", "")),
            type="password",
            key="pas_gpexe_password",
        )

        if st.button(
            "Connetti a GPExe",
            key="pas_gpexe_connect",
            use_container_width=True,
        ):
            try:
                config = GPExeConfig(
                    base_url=gpexe_base_url.strip(),
                    username=gpexe_username.strip(),
                    password=gpexe_password,
                    timeout_seconds=20.0,
                    verify_tls=True,
                )
                config.validate(require_credentials=True)
                client = GPExeGraphQLClient(config)
                client.test_connection()
                runtime_token = client.token
                team_count = None

                st.session_state["pas_gpexe_runtime_token"] = runtime_token
                st.session_state["pas_gpexe_runtime_refresh_token"] = client.refresh_token
                st.session_state["pas_gpexe_connected"] = True
                st.session_state["pas_gpexe_connected_base_url"] = config.base_url.rstrip("/")
                st.session_state["pas_gpexe_team_count"] = team_count
                st.session_state["pas_gpexe_connected_at"] = pd.Timestamp.now(tz="UTC").isoformat()
                st.success("Connessione GraphQL GPExe riuscita. Token verificato nella sessione corrente.")
                st.rerun()
            except Exception as exc:
                for state_key in (
                    "pas_gpexe_runtime_token",
                    "pas_gpexe_runtime_refresh_token",
                    "pas_gpexe_connected",
                    "pas_gpexe_connected_base_url",
                    "pas_gpexe_team_count",
                    "pas_gpexe_connected_at",
                ):
                    st.session_state.pop(state_key, None)
                st.error(f"Connessione GPExe non riuscita: {exc}")

        if is_gpexe_connected:
            st.divider()
            st.markdown("##### GPExe GraphQL")
            st.success("Autenticazione GraphQL operativa. Team e TeamSession sono disponibili.")
            st.caption("Excel e il PAS Core restano invariati: l'import usa esclusivamente il database locale PAS Connect.")

            st.markdown("##### Team e TeamSession")
            teams_foundation = []
            selected_team = {}
            try:
                foundation_config = GPExeConfig(
                    base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                    token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                    timeout_seconds=30.0, verify_tls=True,
                )
                foundation_provider = GPExeAPIDataProvider(GPExeServices(GPExeClient(foundation_config)))
                team_filter = st.selectbox(
                    "Team da mostrare",
                    ("Attivi", "Scaduti", "Tutti"),
                    index=0,
                    key="pas_gpexe_team_filter",
                    on_change=invalidate_team_filter_state,
                    args=(st.session_state,),
                )
                if "pas_gpexe_teams" not in st.session_state:
                    active_filter = {"Attivi": True, "Scaduti": False, "Tutti": None}[team_filter]
                    st.session_state["pas_gpexe_teams"] = foundation_provider.get_teams(active=active_filter)
                teams_foundation = st.session_state.get("pas_gpexe_teams", [])
                if teams_foundation:
                    def _entity_label(item):
                        club = item.get("limitedClub")
                        club_name = club.get("name") if isinstance(club, dict) else None
                        parts = [item.get("name"), item.get("season"), club_name]
                        label = " · ".join(str(part) for part in parts if part not in (None, ""))
                        return label or str(item.get("id") or "Team")
                    selected_team_index = st.selectbox(
                        "Team", range(len(teams_foundation)),
                        format_func=lambda index: _entity_label(teams_foundation[index]),
                        key="pas_gpexe_selected_team_index",
                        on_change=invalidate_athlete_context_state,
                        args=(st.session_state,),
                    )
                    selected_team = teams_foundation[selected_team_index]
                    default_end = pd.Timestamp.today().date()
                    default_start = default_end - timedelta(days=6)
                    date_col1, date_col2 = st.columns(2)
                    with date_col1:
                        start_date = st.date_input("Data iniziale", value=default_start, key="pas_gpexe_start_date")
                    with date_col2:
                        end_date = st.date_input("Data finale", value=default_end, key="pas_gpexe_end_date")
                    if st.button("Recupera Team Sessions", key="pas_gpexe_get_sessions", use_container_width=True):
                        team_id = selected_team.get("id") or selected_team.get("pk") or selected_team.get("uuid")
                        if start_date > end_date:
                            st.error("La data iniziale non può essere successiva alla data finale.")
                        else:
                            st.session_state["pas_gpexe_team_sessions"] = foundation_provider.get_team_sessions(
                                team_id, start_date=start_date.isoformat(), end_date=end_date.isoformat(),
                            )
                    sessions_foundation = st.session_state.get("pas_gpexe_team_sessions", [])
                    selected_ids: set[str] = set()
                    if sessions_foundation:
                        st.success(f"TeamSession recuperate: {len(sessions_foundation)}")
                        session_rows = []
                        for session in sessions_foundation:
                            category = session.get("category")
                            session_rows.append({
                                "Seleziona": False,
                                "id": session.get("id"),
                                "categoria": category.get("name") if isinstance(category, dict) else category,
                                "data": session.get("startTimestamp"),
                                "durata": session.get("duration"),
                                "athleteCount": session.get("athleteCount"),
                                "matchCycle": session.get("matchCycle"),
                                "state": session.get("state"),
                                "drill": session.get("drill"),
                                "drillEnabled": session.get("drillEnabled"),
                            })
                        selection = st.data_editor(
                            pd.DataFrame(session_rows), hide_index=True, use_container_width=True,
                            disabled=[column for column in session_rows[0] if column != "Seleziona"],
                            key="pas_gpexe_session_selection",
                            on_change=invalidate_athlete_session_state,
                            args=(st.session_state,),
                        )
                        selected_ids = set(selection.loc[selection["Seleziona"], "id"].astype(str))
                        if st.button("Importa nel database PAS", key="pas_gpexe_import_sessions", use_container_width=True):
                            selected_sessions = [item for item in sessions_foundation if str(item.get("id")) in selected_ids]
                            if not selected_sessions:
                                st.warning("Seleziona almeno una TeamSession da importare.")
                            else:
                                team_id = selected_team.get("id")
                                mapped = [map_team_session({**item, "team": team_id}) for item in selected_sessions]
                                result = PASConnectDatabase.default().upsert_team_sessions({"sessions": mapped})
                                st.success(f"Importazione completata: {result.inserted} nuove · {result.updated} aggiornate.")
                    else:
                        st.info("Il Team non ha TeamSession nell'intervallo selezionato.")
                else:
                    st.info("Nessun Team disponibile.")
            except Exception as exc:
                st.error(f"Recupero GPExe non riuscito: {exc}")

            st.markdown("##### Athletes")
            if teams_foundation:
                athlete_filter = st.selectbox(
                    "Athletes da mostrare", ("Current", "Expired", "Tutti"), index=0,
                    key="pas_gpexe_athlete_filter", on_change=invalidate_athlete_context_state,
                    args=(st.session_state,),
                )
                athlete_scope = st.selectbox(
                    "Atleti da mostrare",
                    ("Tutti gli associati al Team", "Solo partecipanti alle TeamSession selezionate"),
                    index=1 if team_filter == "Scaduti" else 0,
                    key="pas_gpexe_athlete_scope",
                    on_change=invalidate_athlete_context_state,
                    args=(st.session_state,),
                )
                participants_only = athlete_scope == "Solo partecipanti alle TeamSession selezionate"
                needs_expired = athlete_filter in {"Expired", "Tutti"}
                automatic_club_id = resolve_team_club_id(selected_team)
                club_id = automatic_club_id
                if needs_expired:
                    club_id = resolve_team_club_id(
                        selected_team,
                        st.text_input(
                            "Club ID GPExe",
                            value=automatic_club_id or "",
                            key=f"pas_gpexe_club_id_{selected_team.get('id')}",
                            on_change=invalidate_athlete_context_state,
                            args=(st.session_state,),
                            help="Necessario per gli Athletes Expired; viene precompilato quando disponibile nel Team.",
                        ),
                    )
                if needs_expired and club_id in (None, ""):
                    st.warning("Club ID non disponibile per recuperare gli Athletes Expired.")
                if participants_only and not selected_ids:
                    st.info("Seleziona almeno una TeamSession per ricostruire la rosa del periodo.")
                if st.button("Recupera Athletes", key="pas_gpexe_get_athletes", use_container_width=True):
                    try:
                        if participants_only and not selected_ids:
                            raise ValueError("Seleziona almeno una TeamSession per ricostruire la rosa del periodo.")
                        if not participants_only and needs_expired and club_id in (None, ""):
                            raise ValueError("Club ID non disponibile per recuperare gli Athletes Expired.")
                        if participants_only:
                            participant_results = []
                            participant_errors = []
                            for team_session_id in selected_ids:
                                try:
                                    participant_results.append({
                                        "team_session_id": team_session_id,
                                        "result": foundation_provider.get_team_session_athlete_sessions(
                                            team_session_id, template_id=None, drill=None,
                                        ),
                                    })
                                except Exception as exc:
                                    participant_errors.append(team_session_error_diagnostic(
                                        exc, team_session_id=team_session_id, template_id=None,
                                        drill=None, fields_limit=None,
                                        secrets=(foundation_config.token, foundation_config.password),
                                    ))
                            fetched_athletes = athletes_from_team_session_results(participant_results)
                            st.session_state["pas_gpexe_athlete_session_results"] = participant_results
                            st.session_state["pas_gpexe_athlete_session_errors"] = participant_errors
                            diagnostics = {
                                "operationName": "TeamSessionAthletesession",
                                "received": sum(len(bundle["result"].get("athleteSessions") or []) for bundle in participant_results),
                                "count": len(fetched_athletes), "serverReceived": len(fetched_athletes),
                                "teamMatched": len(fetched_athletes), "teamId": str(selected_team.get("id")),
                            }
                        else:
                            tab = {"Current": "CURRENT", "Expired": "EXPIRED", "Tutti": None}[athlete_filter]
                            fetched_athletes = foundation_provider.get_athletes(
                                selected_team.get("id"), club_id=club_id, tab=tab,
                            )
                            diagnostics = foundation_provider.services.last_diagnostics
                        store_athlete_fetch_result(
                            st.session_state, fetched_athletes, diagnostics,
                        )
                    except Exception as exc:
                        st.session_state["pas_gpexe_athletes_loaded"] = True
                        st.session_state["pas_gpexe_athletes_diagnostics"] = {
                            "operationName": "Athletes", "error": str(exc),
                        }
                        st.error(f"Recupero Athletes non riuscito: {exc}")
                athletes_foundation = st.session_state.get("pas_gpexe_athletes", [])
                athletes_diagnostics = st.session_state.get("pas_gpexe_athletes_diagnostics", {})
                if athletes_diagnostics:
                    diagnostic_text = (
                        f"operationName: {athletes_diagnostics.get('operationName', 'Athletes')} · "
                        f"ricevuti dal server: {athletes_diagnostics.get('serverReceived', athletes_diagnostics.get('received', 0))} · "
                        f"appartenenti al Team: {athletes_diagnostics.get('teamMatched', athletes_diagnostics.get('received', 0))} · "
                        f"count server: {athletes_diagnostics.get('count', 'n/d')} · "
                        f"teamId: {athletes_diagnostics.get('teamId', selected_team.get('id', 'n/d'))}"
                    )
                    if athletes_diagnostics.get("error"):
                        diagnostic_text += f" · errore: {athletes_diagnostics['error']}"
                    st.caption(diagnostic_text)
                if athletes_foundation:
                    athlete_rows = [{
                        "Seleziona": False, "id": item.get("id"),
                        "cognome": item.get("lastName"), "nome": item.get("firstName"),
                        "shortName": item.get("shortName"), "attivo": item.get("isActive"),
                        "hasTracks": item.get("hasTracks"),
                        "Presenze TeamSession": item.get("teamSessionAppearances"),
                    } for item in athletes_foundation]
                    athlete_selection = st.data_editor(
                        pd.DataFrame(athlete_rows), hide_index=True, use_container_width=True,
                        disabled=[column for column in athlete_rows[0] if column != "Seleziona"],
                        key="pas_gpexe_athlete_selection",
                    )
                    selected_athlete_ids = set(
                        athlete_selection.loc[athlete_selection["Seleziona"], "id"].astype(str)
                    )
                    if st.button("Importa Athletes nel database PAS", key="pas_gpexe_import_athletes", use_container_width=True):
                        chosen = [item for item in athletes_foundation if str(item.get("id")) in selected_athlete_ids]
                        if not chosen:
                            st.warning("Seleziona almeno un Athlete da importare.")
                        else:
                            mapped = [map_graphql_athlete(item, team_id=selected_team.get("id")) for item in chosen]
                            inserted, updated = PASConnectDatabase.default().upsert_graphql_athletes(mapped)
                            st.success(f"Athletes importati: {inserted} nuovi · {updated} aggiornati.")
                elif st.session_state.get("pas_gpexe_athletes_loaded") and not athletes_diagnostics.get("error"):
                    if int(athletes_diagnostics.get("serverReceived") or 0) > 0 and int(athletes_diagnostics.get("teamMatched") or 0) == 0:
                        st.info("Nessun atleta associato al Team selezionato.")
                    else:
                        st.info("Nessun atleta trovato per il Team e il filtro selezionati.")

                st.markdown("##### Athlete Sessions e KPI")
                template_id = st.text_input("Template ID (opzionale)", key="pas_gpexe_template_id")
                drill_id = st.text_input("Drill ID (opzionale)", key="pas_gpexe_drill_id")
                fields_limit_text = st.text_input("Fields limit (opzionale)", key="pas_gpexe_fields_limit")
                if st.button("Recupera Athlete Sessions", key="pas_gpexe_get_athlete_sessions", use_container_width=True):
                    if not selected_ids:
                        st.warning("Seleziona almeno una TeamSession.")
                    else:
                        results = []
                        errors = []
                        for team_session_id in selected_ids:
                            try:
                                result = foundation_provider.get_team_session_athlete_sessions(
                                    team_session_id,
                                    template_id=template_id,
                                    drill=drill_id,
                                    fields_limit=fields_limit_text,
                                )
                                results.append({"team_session_id": team_session_id, "result": result})
                            except Exception as exc:
                                errors.append(team_session_error_diagnostic(
                                    exc, team_session_id=team_session_id,
                                    template_id=template_id, drill=drill_id,
                                    fields_limit=fields_limit_text,
                                    secrets=(foundation_config.token, foundation_config.password),
                                ))
                        st.session_state["pas_gpexe_athlete_session_results"] = results
                        st.session_state["pas_gpexe_athlete_session_errors"] = errors
                athlete_session_results = st.session_state.get("pas_gpexe_athlete_session_results", [])
                athlete_session_errors = normalize_team_session_error_diagnostics(
                    st.session_state.get("pas_gpexe_athlete_session_errors", [])
                )
                st.session_state["pas_gpexe_athlete_session_errors"] = athlete_session_errors
                if athlete_session_results or athlete_session_errors:
                    summary = []
                    for bundle in athlete_session_results:
                        sessions = bundle["result"].get("athleteSessions") or []
                        kpi_count = sum(len(item.get("identifierKpi") or []) + len(item.get("kpi") or []) for item in sessions)
                        summary.append({"TeamSession": bundle["team_session_id"], "AthleteSession": len(sessions), "KPI": kpi_count, "Errori": 0})
                    summary.extend({"TeamSession": item["teamSessionId"], "AthleteSession": 0, "KPI": 0, "Errori": 1} for item in athlete_session_errors)
                    st.dataframe(pd.DataFrame(summary), hide_index=True, use_container_width=True)
                    if athlete_session_errors:
                        st.markdown("###### Diagnostica TeamSessionAthletesession")
                        diagnostic_frame = pd.DataFrame(athlete_session_errors).reindex(
                            columns=TEAM_SESSION_DIAGNOSTIC_COLUMNS,
                        )
                        st.dataframe(
                            diagnostic_frame,
                            hide_index=True, use_container_width=True,
                        )
                    if st.button("Importa Athlete Sessions e KPI nel database PAS", key="pas_gpexe_import_athlete_sessions", use_container_width=True):
                        try:
                            mapped_sessions = []
                            for bundle in athlete_session_results:
                                for item in bundle["result"].get("athleteSessions") or []:
                                    mapped_sessions.append(map_graphql_athlete_session(
                                        item, team_session_id=bundle["team_session_id"], template_id=template_id or None,
                                    ))
                            athlete_session_database = PASConnectDatabase.default()
                            parent_sessions = [
                                map_team_session({**item, "team": selected_team.get("id")})
                                for item in sessions_foundation
                                if str(item.get("id")) in {str(bundle["team_session_id"]) for bundle in athlete_session_results}
                            ]
                            if parent_sessions:
                                athlete_session_database.upsert_team_sessions({"sessions": parent_sessions})
                            encountered_athletes = athletes_from_team_session_results(athlete_session_results)
                            if encountered_athletes:
                                athlete_session_database.upsert_graphql_athletes([
                                    map_graphql_athlete(item, team_id=selected_team.get("id"))
                                    for item in encountered_athletes
                                ])
                            inserted, updated, tracks, kpis = athlete_session_database.upsert_graphql_athlete_sessions(mapped_sessions)
                            st.session_state["pas_gpexe_last_athlete_session_import"] = {
                                "status": "success",
                                "message": f"Athlete Sessions: {inserted} nuove · {updated} aggiornate · {tracks} Tracks in UPSERT · {kpis} KPI sostituiti.",
                            }
                        except Exception as exc:
                            st.session_state["pas_gpexe_last_athlete_session_import"] = {
                                "status": "error",
                                "message": f"Importazione Athlete Sessions e KPI non riuscita: {exc}",
                            }
                    last_import = st.session_state.get("pas_gpexe_last_athlete_session_import")
                    if isinstance(last_import, dict):
                        if last_import.get("status") == "success":
                            st.success(str(last_import.get("message") or "Importazione completata."))
                        else:
                            st.error(str(last_import.get("message") or "Importazione non riuscita."))

            st.divider()
            st.markdown("##### Sincronizzazione completa")
            st.caption(
                "Esegue in ordine anagrafiche, Team Sessions, dettagli Team Sessions e Athlete Sessions. "
                "Excel resta la sorgente operativa e non viene modificato."
            )
            if st.button(
                "🚀 Sincronizzazione completa GPExe",
                key="pas_gpexe_full_sync",
                use_container_width=True,
                type="primary",
                disabled=True,
            ):
                try:
                    runtime_config = GPExeConfig(
                        base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                        token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                        timeout_seconds=120.0,
                        verify_tls=True,
                    )
                    runtime_config.validate(require_credentials=True)
                    runtime_client = GPExeClient(runtime_config)
                    full_database = PASConnectDatabase.default()
                    progress_bar = st.progress(0, text="Preparazione sincronizzazione...")
                    log_box = st.empty()
                    sync_log: list[str] = []

                    def _full_sync_progress(event):
                        percent = int(((event.index - (0 if event.status == "success" else 1)) / event.total) * 100)
                        percent = max(0, min(100, percent))
                        progress_bar.progress(percent, text=event.message)
                        sync_log.append(f"{event.step}: {event.status} · {event.message}")
                        log_box.code("\n".join(sync_log[-12:]), language=None)

                    full_result = run_full_sync(
                        runtime_client, full_database, progress=_full_sync_progress
                    )
                    progress_bar.progress(100, text="Sincronizzazione completa terminata")
                    st.session_state["pas_gpexe_last_full_sync"] = full_result
                    ref_counts = full_result["steps"]["reference"]["counts"]
                    ses = full_result["steps"]["team_sessions"]
                    det = full_result["steps"]["team_session_details"]
                    ath = full_result["steps"]["athlete_sessions"]
                    tracks = full_result["steps"].get("tracks", {})
                    st.success(
                        "Sincronizzazione completa: "
                        f"{ref_counts.get('athletes', 0)} atleti · "
                        f"{ses.get('received', 0)} Team Sessions · "
                        f"{det.get('received', 0)} dettagli sessione · "
                        f"{ath.get('received', 0)} Athlete Sessions · "
                        f"{tracks.get('received', 0)} Tracks."
                    )
                except Exception as exc:
                    st.error(f"Sincronizzazione completa GPExe non riuscita: {exc}")

            st.divider()
            st.markdown("##### Sincronizzazioni manuali")
            st.caption("I comandi seguenti restano disponibili per diagnostica e recuperi mirati.")
            st.markdown("##### Prima sincronizzazione")
            st.caption(
                "Scarica Teams, Categories, Tags e Athletes e li salva nel database PAS Connect "
                "separato. Il database Excel e le analisi del PAS restano invariati."
            )
            if st.button(
                "Sincronizza anagrafiche GPExe",
                key="pas_gpexe_sync_reference",
                use_container_width=True,
                disabled=True,
            ):
                try:
                    runtime_config = GPExeConfig(
                        base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                        token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                        timeout_seconds=30.0,
                        verify_tls=True,
                    )
                    runtime_config.validate(require_credentials=True)
                    runtime_client = GPExeClient(runtime_config)
                    with st.spinner("Sincronizzazione anagrafiche GPExe in corso..."):
                        snapshot = sync_reference_data(runtime_client)
                        snapshot_path = SnapshotStore.default().save(snapshot)
                        database_result = PASConnectDatabase.default().replace_reference_data(snapshot)
                    st.session_state["pas_gpexe_last_snapshot"] = snapshot
                    st.session_state["pas_gpexe_last_snapshot_path"] = str(snapshot_path)
                    st.session_state["pas_gpexe_last_database_path"] = str(database_result.database_path)
                    st.success(
                        "Sincronizzazione completata nel database PAS Connect: "
                        f"{database_result.counts['teams']} team, "
                        f"{database_result.counts['categories']} categorie, "
                        f"{database_result.counts['tags']} tag e "
                        f"{database_result.counts['athletes']} atleti."
                    )
                except Exception as exc:
                    st.error(f"Sincronizzazione GPExe non riuscita: {exc}")

            try:
                reference_database = PASConnectDatabase.default()
                database_counts = reference_database.counts()
                last_database_sync = reference_database.last_successful_sync()
            except Exception:
                database_counts = {"teams": 0, "categories": 0, "tags": 0, "athletes": 0}
                last_database_sync = None
            if any(database_counts.values()):
                sync_time = ""
                if isinstance(last_database_sync, dict):
                    sync_time = str(last_database_sync.get("completed_at") or "")
                st.caption(
                    "Database PAS Connect: "
                    f"{database_counts.get('teams', 0)} team · "
                    f"{database_counts.get('categories', 0)} categorie · "
                    f"{database_counts.get('tags', 0)} tag · "
                    f"{database_counts.get('athletes', 0)} atleti"
                    + (f" · ultima sincronizzazione {sync_time}" if sync_time else "")
                )
                st.caption(
                    "Nota Streamlit Cloud: il database locale è isolato dall’Excel ma viene "
                    "ricreato dopo reboot o nuovo deploy. La persistenza cloud sarà introdotta "
                    "in una fase successiva."
                )

            st.divider()
            st.markdown("##### Team Sessions")
            st.caption(
                "Scarica le Team Sessions GPExe nel database PAS Connect separato. "
                "Dashboard, report e database Excel restano invariati."
            )
            if st.button(
                "Sincronizza Team Sessions GPExe",
                key="pas_gpexe_sync_team_sessions",
                use_container_width=True,
                disabled=True,
            ):
                try:
                    runtime_config = GPExeConfig(
                        base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                        token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                        timeout_seconds=60.0,
                        verify_tls=True,
                    )
                    runtime_config.validate(require_credentials=True)
                    runtime_client = GPExeClient(runtime_config)
                    session_database = PASConnectDatabase.default()
                    updated_since = session_database.latest_team_session_updated_at()
                    with st.spinner("Sincronizzazione Team Sessions GPExe in corso..."):
                        session_payload = sync_team_sessions(
                            runtime_client, updated_since=updated_since
                        )
                        session_result = session_database.upsert_team_sessions(session_payload)
                    st.success(
                        "Team Sessions sincronizzate: "
                        f"{session_result.received} ricevute · "
                        f"{session_result.inserted} nuove · "
                        f"{session_result.updated} aggiornate."
                    )
                except Exception as exc:
                    st.error(f"Sincronizzazione Team Sessions non riuscita: {exc}")

            try:
                session_database = PASConnectDatabase.default()
                stored_sessions = session_database.team_session_count()
                last_session_sync = session_database.last_team_session_sync()
            except Exception:
                stored_sessions = 0
                last_session_sync = None
            if stored_sessions:
                details = ""
                if isinstance(last_session_sync, dict):
                    details = (
                        f" · ultima sync {last_session_sync.get('completed_at', '')}"
                        f" · nuove {last_session_sync.get('inserted_count', 0)}"
                        f" · aggiornate {last_session_sync.get('updated_count', 0)}"
                    )
                st.caption(f"Team Sessions nel database PAS Connect: {stored_sessions}{details}")


            st.divider()
            st.markdown("##### Dettaglio Team Sessions")
            st.caption(
                "Scarica header, stato, timing, metriche dinamiche e righe atleta per le Team Sessions "
                "già presenti nel database PAS Connect. Excel e analisi restano invariati."
            )
            if st.button(
                "Sincronizza dettagli Team Sessions GPExe",
                key="pas_gpexe_sync_team_session_details",
                use_container_width=True,
                disabled=True,
            ):
                try:
                    runtime_config = GPExeConfig(
                        base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                        token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                        timeout_seconds=90.0,
                        verify_tls=True,
                    )
                    runtime_config.validate(require_credentials=True)
                    runtime_client = GPExeClient(runtime_config)
                    detail_database = PASConnectDatabase.default()
                    session_ids = detail_database.team_session_ids_for_detail_sync(only_missing=True)
                    if not session_ids:
                        st.info("Nessuna Team Session senza dettaglio da sincronizzare.")
                    else:
                        with st.spinner(f"Sincronizzazione dettaglio di {len(session_ids)} Team Sessions..."):
                            detail_payload = sync_team_session_details(runtime_client, session_ids)
                            detail_result = detail_database.upsert_team_session_details(detail_payload)
                        st.success(
                            "Dettagli Team Sessions sincronizzati: "
                            f"{detail_result.received} sessioni · "
                            f"{detail_result.inserted} nuove · "
                            f"{detail_result.updated} aggiornate · "
                            f"{detail_result.athlete_rows} righe atleta · "
                            f"{detail_result.metric_headers} intestazioni metriche"
                            + (f" · {detail_result.failed} errori" if detail_result.failed else "")
                        )
                except Exception as exc:
                    st.error(f"Sincronizzazione dettagli Team Sessions non riuscita: {exc}")

            try:
                detail_database = PASConnectDatabase.default()
                stored_details = detail_database.team_session_detail_count()
                last_detail_sync = detail_database.last_team_session_detail_sync()
            except Exception:
                stored_details = 0
                last_detail_sync = None
            if stored_details:
                detail_text = ""
                if isinstance(last_detail_sync, dict):
                    detail_text = (
                        f" · ultima sync {last_detail_sync.get('completed_at', '')}"
                        f" · errori {last_detail_sync.get('failed_count', 0)}"
                    )
                st.caption(f"Dettagli Team Sessions nel database PAS Connect: {stored_details}{detail_text}")

            st.divider()
            st.markdown("##### Athlete Sessions")
            st.caption(
                "Scarica il dettaglio individuale delle Athlete Sessions già collegate alle Team Sessions. "
                "I dati restano nel database PAS Connect separato; Excel e analisi non cambiano."
            )
            if st.button(
                "Sincronizza Athlete Sessions GPExe",
                key="pas_gpexe_sync_athlete_session_details",
                use_container_width=True,
                disabled=True,
            ):
                try:
                    runtime_config = GPExeConfig(
                        base_url=str(st.session_state.get("pas_gpexe_connected_base_url", gpexe_base_url)).strip(),
                        token=str(st.session_state.get("pas_gpexe_runtime_token", "")).strip(),
                        timeout_seconds=120.0,
                        verify_tls=True,
                    )
                    runtime_config.validate(require_credentials=True)
                    runtime_client = GPExeClient(runtime_config)
                    athlete_database = PASConnectDatabase.default()
                    athlete_refs = athlete_database.athlete_session_refs_for_detail_sync(only_missing=True)
                    if not athlete_refs:
                        st.info("Nessuna Athlete Session senza dettaglio da sincronizzare.")
                    else:
                        with st.spinner(f"Sincronizzazione di {len(athlete_refs)} Athlete Sessions..."):
                            athlete_payload = sync_athlete_session_details(runtime_client, athlete_refs)
                            athlete_result = athlete_database.upsert_athlete_session_details(athlete_payload)
                        st.success(
                            "Athlete Sessions sincronizzate: "
                            f"{athlete_result.received} ricevute · "
                            f"{athlete_result.inserted} nuove · "
                            f"{athlete_result.updated} aggiornate"
                            + (f" · {athlete_result.failed} errori" if athlete_result.failed else "")
                        )
                except Exception as exc:
                    st.error(f"Sincronizzazione Athlete Sessions non riuscita: {exc}")

            try:
                athlete_database = PASConnectDatabase.default()
                stored_athlete_details = athlete_database.athlete_session_detail_count()
                last_athlete_sync = athlete_database.last_athlete_session_detail_sync()
            except Exception:
                stored_athlete_details = 0
                last_athlete_sync = None
            if stored_athlete_details:
                athlete_text = ""
                if isinstance(last_athlete_sync, dict):
                    athlete_text = (
                        f" · ultima sync {last_athlete_sync.get('completed_at', '')}"
                        f" · errori {last_athlete_sync.get('failed_count', 0)}"
                    )
                st.caption(
                    f"Athlete Sessions nel database PAS Connect: {stored_athlete_details}{athlete_text}"
                )

            if st.button(
                "Disconnetti GPExe",
                key="pas_gpexe_disconnect",
                use_container_width=True,
            ):
                for state_key in (
                    "pas_gpexe_runtime_token",
                    "pas_gpexe_runtime_refresh_token",
                    "pas_gpexe_connected",
                    "pas_gpexe_connected_base_url",
                    "pas_gpexe_team_count",
                    "pas_gpexe_connected_at",
                ):
                    st.session_state.pop(state_key, None)
                st.rerun()

        with st.expander("Configurazione Streamlit Secrets", expanded=False):
            st.code(
                '[gpexe]\n'
                'base_url = "https://e15.gpexe.com/ui/v2/"\n'
                'token = "INSERISCI_TOKEN"\n'
                '# oppure username = "..." e password = "..."',
                language="toml",
            )
            st.caption(
                "Non inserire mai token o password nel repository GitHub. "
                "Su Streamlit Cloud usa App settings → Secrets."
            )

        st.divider()
        if st.button(
            "Esci dalla Demo",
            key="pas_demo_logout_settings",
            help="Chiude la sessione Demo corrente.",
            use_container_width=True,
        ):
            st.session_state["pas_demo_authenticated"] = False
            st.rerun()

st.sidebar.divider()

def open_planner_from_dashboard(
    selected_month_key: str,
) -> None:
    """
    Callback eseguita prima del rerun di Streamlit.
    In questo modo la navigazione può essere aggiornata
    senza modificare il valore del widget dopo la sua creazione.
    """
    st.session_state["planner_view"] = "calendar"
    st.session_state["planner_selected_date"] = (
        selected_month_key
    )
    st.session_state["pas_navigation"] = "🗓️ Planner"


if st.session_state.get("pas_pending_navigation"):
    st.session_state["pas_navigation"] = st.session_state.pop("pas_pending_navigation")

render_pas_brand_header(base_dir)

st.markdown(
    """
    <style>
    div[data-testid="stRadio"] > div[role="radiogroup"] {
        display: flex;
        flex-wrap: wrap;
        gap: 0.35rem 0.55rem;
        align-items: center;
        padding: 0.45rem 0.55rem;
        border: 1px solid rgba(128, 128, 128, 0.25);
        border-radius: 0.75rem;
        background: rgba(128, 128, 128, 0.05);
    }
    div[data-testid="stRadio"] > div[role="radiogroup"] label {
        margin: 0;
        padding: 0.25rem 0.4rem;
        border-radius: 0.5rem;
        white-space: nowrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

page = st.radio(
    "Navigazione principale",
    [
        "🏠 Dashboard",
        "📊 Period Load",
        "🗓️ Planner",
        "🔮 Forecast",
        "🧩 Drills",
        "⚽ Match Analysis",
        "🎯 Performance Model",
        "🔬 Performance Research",
        "🏥 Return To Play",
        "👤 Player Profiles",
    ],
    key="pas_navigation",
    horizontal=True,
    label_visibility="collapsed",
)

st.divider()
if page in {"🏠 Dashboard", "📊 Period Load"}:
    with st.expander("✨ PAS Intelligence", expanded=False):
        render_pas_assistant(raw, page)


if page == "🔬 Performance Research":
    st.title("🔬 Performance Research")
    st.caption(
        "Scegli ciò che vuoi studiare: il PAS riconosce la struttura dei dati e seleziona "
        "automaticamente il percorso statistico coerente."
    )

    analysis_source = raw.copy()
    analysis_source["Date"] = pd.to_datetime(analysis_source["Date"], errors="coerce")
    analysis_source = analysis_source.dropna(subset=["Date", "Athlete"])
    role_column = "Role Clean" if "Role Clean" in analysis_source.columns else "Role"

    available_metrics = [
        metric for metric, meta in METRICS.items()
        if meta["column"] in analysis_source.columns
    ]
    default_metrics = [metric for metric in ["Distance (m)"] if metric in available_metrics]

    factor_specs = {
        "Starters / No Starters": "Starters / No Starters",
        "Match Cycle": "Cycle",
        "Match Day": "Match Day +/-",
        "Ruolo": role_column,
        "Giocatore": "Athlete",
        "Drill": "Drill",
        "Tipo seduta": "Type Session",
        "Settimana": "Week",
        "Mese": "__month__",
        "Casa / Trasferta": "Home / Away",
        "Avversario": "Opponent",
    }
    factor_specs = {
        label: column for label, column in factor_specs.items()
        if column == "__month__" or column in analysis_source.columns
    }
    analysis_source["__month__"] = analysis_source["Date"].dt.to_period("M").astype(str)

    st.markdown("### 1. Cosa vuoi studiare?")
    metric_col, level_col = st.columns([2, 1])
    with metric_col:
        selected_stat_metrics = st.multiselect(
            "Metriche",
            available_metrics,
            default=default_metrics,
            key="research_metrics",
            help="Con una metrica il PAS confronta gruppi o descrive l'andamento; con più metriche aggiunge le correlazioni.",
        )
    with level_col:
        observation_level = st.selectbox(
            "Unità di osservazione",
            ["Giocatore per giornata", "Giocatore per Match Cycle"],
            key="research_observation_level",
        )

    match_cycle_comparison_mode = None
    if observation_level == "Giocatore per Match Cycle":
        match_cycle_comparison_mode = st.radio(
            "Tipo di confronto Match Cycle",
            ["Confronta un ciclo gara", "Confronta più cicli gara · Linear Mixed Model"],
            horizontal=True,
            key="research_match_cycle_comparison_mode",
            help=(
                "Il confronto multiplo usa un Linear Mixed Model con Match Cycle e fattore "
                "principale come effetti fissi e giocatore come random intercept."
            ),
        )

    st.markdown("### 2. Come vuoi organizzare il confronto?")
    factor_col_1, factor_col_2 = st.columns(2)
    factor_options = ["Nessun fattore"] + list(factor_specs)
    with factor_col_1:
        factor_1_label = st.selectbox("Fattore principale", factor_options, key="research_factor_1")
    with factor_col_2:
        second_options = ["Nessun secondo fattore"] + [f for f in factor_specs if f != factor_1_label]
        factor_2_label = st.selectbox("Secondo fattore · opzionale", second_options, key="research_factor_2")

    st.markdown("### 3. Filtri")
    all_dates = sorted(analysis_source["Date"].dt.date.unique())
    filter_cols = st.columns(4)
    with filter_cols[0]:
        date_range = st.date_input(
            "Periodo",
            value=(all_dates[0], all_dates[-1]) if all_dates else (),
            min_value=all_dates[0] if all_dates else None,
            max_value=all_dates[-1] if all_dates else None,
            key="research_dates",
        )
    with filter_cols[1]:
        player_filter = st.multiselect(
            "Giocatori",
            sorted(analysis_source["Athlete"].dropna().astype(str).unique()),
            key="research_players",
        )
    with filter_cols[2]:
        role_filter = st.multiselect(
            "Ruoli",
            sorted(analysis_source[role_column].dropna().astype(str).unique()) if role_column in analysis_source else [],
            key="research_roles",
        )
    with filter_cols[3]:
        cycle_filter = st.multiselect(
            "Match Cycle",
            analysis_source.dropna(subset=["Cycle"]).sort_values("Date")["Cycle"].astype(str).drop_duplicates().tolist()
            if "Cycle" in analysis_source else [],
            key="research_cycles",
        )

    extra_filter_cols = st.columns(3)
    with extra_filter_cols[0]:
        status_filter = st.multiselect(
            "S / NS", ["S", "NS"], key="research_statuses"
        ) if "Starters / No Starters" in analysis_source else []
    with extra_filter_cols[1]:
        if observation_level == "Giocatore per Match Cycle":
            cycle_session_options = [
                "Full Training",
                "Match",
                "Different Training",
                "Active Recovery",
                "Individual Training",
                "Return to Play",
            ]
            cycle_session_categories = st.multiselect(
                "Sedute incluse nel totale del ciclo",
                cycle_session_options,
                default=["Full Training", "Match", "Different Training"],
                key="research_cycle_session_categories",
                help=(
                    "Il totale individuale del Match Cycle somma esclusivamente le sedute selezionate. "
                    "I conteggi della tabella sono calcolati come giornate uniche per giocatore."
                ),
            )
            drill_filter = []
        else:
            allowed_research_drills = [
                "Active Recovery",
                "Individual Training",
                "Return to Play",
                "Full Training",
                "Match",
                "Different Training",
            ]
            if "Drill" in analysis_source:
                normalized_research_drills = (
                    analysis_source["Drill"]
                    .dropna()
                    .astype(str)
                    .str.strip()
                    .replace({"Different Traning": "Different Training"})
                )
                available_research_drills = [
                    drill_name
                    for drill_name in allowed_research_drills
                    if drill_name in set(normalized_research_drills.tolist())
                ]
                drill_filter = st.multiselect(
                    "Drill",
                    available_research_drills,
                    key="research_drills_v3710",
                )
            else:
                drill_filter = []
            cycle_session_categories = []
    with extra_filter_cols[2]:
        session_filter = st.multiselect(
            "Tipo seduta",
            sorted(analysis_source["Type Session"].dropna().astype(str).unique()),
            key="research_sessions",
        ) if "Type Session" in analysis_source else []

    # Applica prima i filtri contestuali. Nel percorso Match Cycle la scelta finale
    # dei giocatori avviene dopo la tabella di copertura FT/Match/DT.
    filtered_base = analysis_source.copy()
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        filtered_base = filtered_base[
            filtered_base["Date"].between(pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]))
        ]
    if player_filter:
        filtered_base = filtered_base[filtered_base["Athlete"].astype(str).isin(player_filter)]
    if role_filter and role_column in filtered_base:
        filtered_base = filtered_base[filtered_base[role_column].astype(str).isin(role_filter)]
    if cycle_filter and "Cycle" in filtered_base:
        filtered_base = filtered_base[filtered_base["Cycle"].astype(str).isin(cycle_filter)]
    if status_filter and "Starters / No Starters" in filtered_base:
        filtered_base = filtered_base[
            filtered_base["Starters / No Starters"].astype(str).str.upper().isin(status_filter)
        ]
    if session_filter and "Type Session" in filtered_base:
        filtered_base = filtered_base[filtered_base["Type Session"].astype(str).isin(session_filter)]

    if observation_level == "Giocatore per Match Cycle":
        if not cycle_session_categories:
            st.warning("Seleziona almeno un tipo di seduta da includere nel totale del ciclo.")
            st.stop()

        # Le sole categorie previste per questa analisi entrano nei conteggi e nel
        # totale analitico del Match Cycle. La normalizzazione corregge il refuso
        # storico Different Traning senza modificare il database originale.
        normalized_drill = filtered_base["Drill"].astype(str).str.strip().replace(
            {"Different Traning": "Different Training"}
        )
        coverage_source = filtered_base.assign(__cycle_session__=normalized_drill)
        coverage_source = coverage_source[
            coverage_source["__cycle_session__"].isin(cycle_session_options)
        ].copy()

        st.markdown("#### Controllo copertura giocatori")
        st.caption(
            "I conteggi indicano il numero di giornate uniche svolte nel periodo e nei Match Cycle selezionati. "
            "Deseleziona un giocatore nella colonna Includi per escluderlo dall'analisi."
        )
        threshold_row_1 = st.columns(3)
        threshold_row_2 = st.columns(3)
        with threshold_row_1[0]:
            min_full_training = st.number_input(
                "Full Training minimi", min_value=0, value=0, step=1,
                key="research_min_full_training",
            )
        with threshold_row_1[1]:
            min_match = st.number_input(
                "Match minimi", min_value=0, value=0, step=1,
                key="research_min_match",
            )
        with threshold_row_1[2]:
            min_different_training = st.number_input(
                "Different Training minimi", min_value=0, value=0, step=1,
                key="research_min_different_training",
            )
        with threshold_row_2[0]:
            min_active_recovery = st.number_input(
                "Active Recovery minimi", min_value=0, value=0, step=1,
                key="research_min_active_recovery",
            )
        with threshold_row_2[1]:
            min_individual_training = st.number_input(
                "Individual Training minimi", min_value=0, value=0, step=1,
                key="research_min_individual_training",
            )
        with threshold_row_2[2]:
            min_return_to_play = st.number_input(
                "Return to Play minimi", min_value=0, value=0, step=1,
                key="research_min_return_to_play",
            )

        if coverage_source.empty:
            st.warning("Nessuna delle sedute previste è disponibile con i filtri selezionati.")
            st.stop()

        exposure = (
            coverage_source.groupby(["Athlete", "__cycle_session__"], dropna=False)["Date"]
            .nunique()
            .unstack(fill_value=0)
            .reindex(columns=cycle_session_options, fill_value=0)
            .reset_index()
        )
        cycles_present = (
            coverage_source.dropna(subset=["Cycle"])
            .groupby("Athlete")["Cycle"].nunique()
            .rename("Match Cycle presenti")
        )
        exposure = exposure.merge(cycles_present, on="Athlete", how="left")
        exposure["Match Cycle presenti"] = exposure["Match Cycle presenti"].fillna(0).astype(int)
        exposure["Totale sedute"] = exposure[cycle_session_options].sum(axis=1)
        eligible = (
            (exposure["Full Training"] >= int(min_full_training))
            & (exposure["Match"] >= int(min_match))
            & (exposure["Different Training"] >= int(min_different_training))
            & (exposure["Active Recovery"] >= int(min_active_recovery))
            & (exposure["Individual Training"] >= int(min_individual_training))
            & (exposure["Return to Play"] >= int(min_return_to_play))
        )
        exposure.insert(0, "Includi", eligible)
        exposure = exposure.sort_values("Athlete").reset_index(drop=True)

        edited_exposure = st.data_editor(
            exposure,
            use_container_width=True,
            hide_index=True,
            disabled=[
                "Athlete", *cycle_session_options,
                "Totale sedute", "Match Cycle presenti",
            ],
            column_config={
                "Includi": st.column_config.CheckboxColumn("Includi", default=True),
                "Athlete": st.column_config.TextColumn("Giocatore"),
            },
            key="research_cycle_player_inclusion",
        )
        included_players = edited_exposure.loc[
            edited_exposure["Includi"].fillna(False), "Athlete"
        ].astype(str).tolist()
        st.caption(
            f"Giocatori inclusi: {len(included_players)} su {len(exposure)} · "
            f"sedute usate nel totale: {', '.join(cycle_session_categories)}"
        )
        if not included_players:
            st.warning("Nessun giocatore incluso nell'analisi.")
            st.stop()

        filtered = coverage_source[
            coverage_source["Athlete"].astype(str).isin(included_players)
            & coverage_source["__cycle_session__"].isin(cycle_session_categories)
        ].copy()
    else:
        filtered = filtered_base.copy()
        if drill_filter and "Drill" in filtered:
            filtered = filtered[filtered["Drill"].astype(str).isin(drill_filter)]

    selected_factors = []
    if factor_1_label != "Nessun fattore":
        selected_factors.append((factor_1_label, factor_specs[factor_1_label]))
    if factor_2_label != "Nessun secondo fattore":
        selected_factors.append((factor_2_label, factor_specs[factor_2_label]))

    def _aggregate_research(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        keys = ["Athlete"]
        keys.append("Cycle" if observation_level == "Giocatore per Match Cycle" and "Cycle" in frame else "Date")
        for _, factor_column in selected_factors:
            if factor_column not in keys:
                keys.append(factor_column)
        keys = [key for key in keys if key in frame.columns]
        rows = frame[keys].drop_duplicates().copy()
        for metric in selected_stat_metrics:
            column = METRICS[metric]["column"]
            values = frame[keys + [column]].copy()
            values[column] = pd.to_numeric(values[column], errors="coerce")
            if observation_level == "Giocatore per Match Cycle":
                # Match Cycle: ogni riga deve rappresentare il totale individuale
                # del ciclo. Tutte le giornate incluse vengono quindi sommate;
                # le medie S/NS vengono calcolate solo successivamente sui totali
                # individuali, mai sulle singole giornate.
                grouped = values.groupby(keys, dropna=False)[column].sum(min_count=1)
            else:
                accumulation = METRICS[metric].get(
                    "accumulation",
                    METRICS[metric].get("aggregation", "sum"),
                )
                if accumulation == "max":
                    grouped = values.groupby(keys, dropna=False)[column].max()
                elif accumulation == "mean":
                    grouped = values.groupby(keys, dropna=False)[column].mean()
                else:
                    grouped = values.groupby(keys, dropna=False)[column].sum(min_count=1)
            rows = rows.merge(grouped.rename(column), on=keys, how="left")
        return rows

    run_analysis = st.button("Analizza", type="primary", use_container_width=True)
    if not selected_stat_metrics:
        st.info("Seleziona almeno una metrica.")
        st.stop()
    if not run_analysis and "research_last_run" not in st.session_state:
        st.info("Configura metriche, fattori e filtri, quindi premi **Analizza**.")
        st.stop()
    if run_analysis:
        st.session_state["research_last_run"] = True

    analysis_data = _aggregate_research(filtered)
    if analysis_data.empty:
        st.warning("Nessuna osservazione disponibile con i filtri selezionati.")
        st.stop()

    if observation_level == "Giocatore per Match Cycle" and "Cycle" in analysis_data:
        selected_cycle_count = analysis_data["Cycle"].dropna().astype(str).nunique()
        if match_cycle_comparison_mode == "Confronta un ciclo gara" and selected_cycle_count != 1:
            st.warning("Per questa modalità seleziona esattamente un Match Cycle nel filtro.")
            st.stop()
        if match_cycle_comparison_mode == "Confronta più cicli gara · Linear Mixed Model" and selected_cycle_count < 2:
            st.warning("Per il Linear Mixed Model seleziona almeno due Match Cycle.")
            st.stop()

    factor_levels = [analysis_data[column].dropna().nunique() for _, column in selected_factors]
    plan = infer_analysis_plan(len(selected_stat_metrics), len(selected_factors), factor_levels)
    st.markdown("### Percorso riconosciuto dal PAS")
    plan_cols = st.columns(3)
    plan_cols[0].metric("Analisi", plan["title"])
    plan_cols[1].metric("Osservazioni", len(analysis_data))
    plan_cols[2].metric("Metriche", len(selected_stat_metrics))
    st.caption(plan["method"])

    descriptive_rows = []
    test_rows = []

    def _pairwise_independent_rows(frame, value_column, group_column, metric_name, stratum_name, factor_name, extra=None):
        """Confronti a coppie con correzione Holm per fattori con almeno due livelli."""
        valid_levels = [
            level for level in frame[group_column].dropna().unique()
            if len(frame[frame[group_column] == level]) >= 2
        ]
        raw_rows = []
        for idx, level_a in enumerate(valid_levels):
            for level_b in valid_levels[idx + 1:]:
                values_a = frame.loc[frame[group_column] == level_a, value_column]
                values_b = frame.loc[frame[group_column] == level_b, value_column]
                result = compare_independent_groups(values_a, values_b)
                raw_rows.append((level_a, level_b, result))
        if not raw_rows:
            return []
        raw_p = [row[2]["p_value"] for row in raw_rows]
        finite = [pd.notna(value) for value in raw_p]
        adjusted = [np.nan] * len(raw_p)
        if any(finite):
            corrected = multipletests([raw_p[i] for i, ok in enumerate(finite) if ok], method="holm")[1]
            cursor = 0
            for i, ok in enumerate(finite):
                if ok:
                    adjusted[i] = float(corrected[cursor])
                    cursor += 1
        output = []
        for (level_a, level_b, result), p_adj in zip(raw_rows, adjusted):
            row = {
                "Metrica": metric_name, "Strato": stratum_name, "Fattore": factor_name,
                "Confronto": f"{level_a} vs {level_b}", "Gruppo A": str(level_a), "Gruppo B": str(level_b),
                "Test": f"{result['test']} · post-hoc Holm",
                "Statistica": result["statistic"], "p grezzo": result["p_value"], "p": p_adj,
                "Effect size": result["effect_size"], "Indice": result["effect_name"],
                "Entità effetto": result["effect_magnitude"], "Post-hoc": True,
                "Media A": float(pd.to_numeric(values_a, errors="coerce").mean()),
                "Media B": float(pd.to_numeric(values_b, errors="coerce").mean()),
            }
            if extra:
                row.update(extra)
            output.append(row)
        return output
    first_factor = selected_factors[0] if selected_factors else None
    second_factor = selected_factors[1] if len(selected_factors) > 1 else None

    group_combinations = [("Totale", analysis_data)]
    if selected_factors:
        group_columns = [column for _, column in selected_factors]
        group_combinations = [
            (" · ".join(map(str, key if isinstance(key, tuple) else (key,))), part)
            for key, part in analysis_data.groupby(group_columns, dropna=False, sort=False)
        ]

    for metric in selected_stat_metrics:
        metric_column = METRICS[metric]["column"]
        for group_name, group_data in group_combinations:
            summary = descriptive_statistics(group_data[metric_column])
            normality = shapiro_result(group_data[metric_column])
            descriptive_rows.append({
                "Metrica": metric, "Gruppo": group_name, "N": summary["count"],
                "Media": summary["mean"], "Mediana": summary["median"], "SD": summary["sd"],
                "CV %": summary["cv"], "Min": summary["min"], "Max": summary["max"],
                "IC95% inf": summary["ci_low"], "IC95% sup": summary["ci_high"],
                "Shapiro p": normality["p_value"],
            })

        if first_factor:
            factor_label, factor_column = first_factor
            levels = [level for level in analysis_data[factor_column].dropna().unique()]
            strata = [("Totale", analysis_data)]
            if second_factor:
                second_label, second_column = second_factor
                strata = [(str(value), part) for value, part in analysis_data.groupby(second_column, dropna=False)]
            for stratum_name, stratum_data in strata:
                valid_levels = [level for level in levels if len(stratum_data[stratum_data[factor_column] == level]) >= 2]
                if len(valid_levels) == 2:
                    a = stratum_data.loc[stratum_data[factor_column] == valid_levels[0], metric_column]
                    b = stratum_data.loc[stratum_data[factor_column] == valid_levels[1], metric_column]
                    result = compare_independent_groups(a, b)
                    test_rows.append({
                        "Metrica": metric, "Strato": stratum_name, "Fattore": factor_label,
                        "Confronto": f"{valid_levels[0]} vs {valid_levels[1]}", "Test": result["test"],
                        "Statistica": result["statistic"], "p": result["p_value"],
                        "Effect size": result["effect_size"], "Indice": result["effect_name"],
                        "Entità effetto": result["effect_magnitude"],
                        "Gruppo A": str(valid_levels[0]), "Gruppo B": str(valid_levels[1]),
                        "Media A": float(pd.to_numeric(a, errors="coerce").mean()),
                        "Media B": float(pd.to_numeric(b, errors="coerce").mean()),
                    })
                elif len(valid_levels) > 2:
                    result = compare_multiple_groups(stratum_data[metric_column], stratum_data[factor_column])
                    test_rows.append({
                        "Metrica": metric, "Strato": stratum_name, "Fattore": factor_label,
                        "Confronto": f"Test globale · {len(valid_levels)} livelli", "Test": result["test"],
                        "Statistica": result["statistic"], "p": result["p_value"],
                        "Effect size": result["effect_size"], "Indice": result["effect_name"],
                        "Entità effetto": result["effect_magnitude"], "Test globale": True,
                    })
                    if pd.notna(result["p_value"]) and result["p_value"] < 0.05:
                        test_rows.extend(_pairwise_independent_rows(
                            stratum_data, metric_column, factor_column, metric, stratum_name, factor_label
                        ))

            # Nei disegni a due fattori il PAS confronta anche i livelli del
            # secondo fattore all'interno di ogni livello del primo. Questo
            # rende immediata, per esempio, la lettura S vs NS in ciascun ciclo.
            if second_factor:
                second_label, second_column = second_factor
                for primary_value, primary_data in analysis_data.groupby(factor_column, dropna=False, sort=False):
                    secondary_levels = [
                        level for level in primary_data[second_column].dropna().unique()
                        if len(primary_data[primary_data[second_column] == level]) >= 2
                    ]
                    if len(secondary_levels) == 2:
                        a = primary_data.loc[primary_data[second_column] == secondary_levels[0], metric_column]
                        b = primary_data.loc[primary_data[second_column] == secondary_levels[1], metric_column]
                        result = compare_independent_groups(a, b)
                        test_rows.append({
                            "Metrica": metric,
                            "Strato": str(primary_value),
                            "Fattore": second_label,
                            "Confronto": f"{secondary_levels[0]} vs {secondary_levels[1]}",
                            "Gruppo A": str(secondary_levels[0]), "Gruppo B": str(secondary_levels[1]),
                            "Test": result["test"],
                            "Statistica": result["statistic"],
                            "p": result["p_value"],
                            "Effect size": result["effect_size"],
                            "Indice": result["effect_name"],
                            "Entità effetto": result["effect_magnitude"],
                            "Media A": float(pd.to_numeric(a, errors="coerce").mean()),
                            "Media B": float(pd.to_numeric(b, errors="coerce").mean()),
                            "Confronto nel fattore principale": True,
                        })
                    elif len(secondary_levels) > 2:
                        global_result = compare_multiple_groups(primary_data[metric_column], primary_data[second_column])
                        test_rows.append({
                            "Metrica": metric, "Strato": str(primary_value), "Fattore": second_label,
                            "Confronto": f"Test globale · {len(secondary_levels)} livelli",
                            "Test": global_result["test"], "Statistica": global_result["statistic"],
                            "p": global_result["p_value"], "Effect size": global_result["effect_size"],
                            "Indice": global_result["effect_name"], "Entità effetto": global_result["effect_magnitude"],
                            "Test globale": True, "Confronto nel fattore principale": True,
                        })
                        if pd.notna(global_result["p_value"]) and global_result["p_value"] < 0.05:
                            test_rows.extend(_pairwise_independent_rows(
                                primary_data, metric_column, second_column, metric, str(primary_value), second_label,
                                {"Confronto nel fattore principale": True}
                            ))

    tabs = st.tabs(["Sintesi", "Visualizzazioni", "Correlazioni", "Dati grezzi"])

    def _sig_symbol(p_value):
        if pd.isna(p_value):
            return "ns"
        if p_value < 0.0001:
            return "****"
        if p_value < 0.001:
            return "***"
        if p_value < 0.01:
            return "**"
        if p_value < 0.05:
            return "*"
        return "ns"

    def _effect_score(effect_value, p_value):
        """Classificazione sintetica, descrittiva e non valutativa."""
        if pd.isna(p_value) or p_value >= 0.05:
            return "Nessuna differenza significativa", "🟢"
        value = abs(float(effect_value)) if pd.notna(effect_value) else 0.0
        if value >= 1.2:
            return "Differenza molto elevata", "🔴"
        if value >= 0.8:
            return "Differenza elevata", "🟠"
        if value >= 0.5:
            return "Differenza moderata", "🟡"
        return "Differenza lieve", "🟡"

    def _fit_cycle_mixed_model(data, value_column, primary_column):
        """Stima EMM per Cycle × fattore primario con random intercept del giocatore."""
        model_data = data[["Athlete", "Cycle", primary_column, value_column]].copy()
        model_data.columns = ["__athlete", "__cycle", "__factor", "__value"]
        model_data["__value"] = pd.to_numeric(model_data["__value"], errors="coerce")
        model_data = model_data.dropna()
        model_data["__athlete"] = model_data["__athlete"].astype(str)
        cycle_levels = model_data["__cycle"].astype(str).drop_duplicates().tolist()
        factor_levels_local = model_data["__factor"].astype(str).drop_duplicates().tolist()
        model_data["__cycle"] = pd.Categorical(model_data["__cycle"].astype(str), categories=cycle_levels, ordered=True)
        model_data["__factor"] = pd.Categorical(model_data["__factor"].astype(str), categories=factor_levels_local, ordered=True)
        if len(cycle_levels) < 2 or len(factor_levels_local) < 2 or model_data["__athlete"].nunique() < 2:
            raise ValueError("Servono almeno due cicli, due livelli del fattore e due giocatori.")
        mixed_model = smf.mixedlm(
            "__value ~ C(__cycle) * C(__factor)",
            model_data, groups=model_data["__athlete"], re_formula="1",
        )
        fitted = None
        fit_errors = []
        for fit_method in ("powell", "lbfgs", "nm"):
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    candidate = mixed_model.fit(
                        reml=True, method=fit_method, maxiter=1000, disp=False
                    )
                if candidate.converged:
                    fitted = candidate
                    break
                fit_errors.append(f"{fit_method}: mancata convergenza")
            except Exception as exc:
                fit_errors.append(f"{fit_method}: {exc}")
        if fitted is None:
            raise RuntimeError("; ".join(fit_errors))
        grid = pd.MultiIndex.from_product(
            [cycle_levels, factor_levels_local], names=["__cycle", "__factor"]
        ).to_frame(index=False)
        grid["__cycle"] = pd.Categorical(grid["__cycle"], categories=cycle_levels, ordered=True)
        grid["__factor"] = pd.Categorical(grid["__factor"], categories=factor_levels_local, ordered=True)
        design = build_design_matrices([fitted.model.data.design_info], grid, return_type="dataframe")[0]
        fixed_names = list(fitted.fe_params.index)
        design = design.loc[:, fixed_names]
        covariance = fitted.cov_params().loc[fixed_names, fixed_names]
        estimate = design.to_numpy() @ fitted.fe_params.to_numpy()
        variance = np.einsum("ij,jk,ik->i", design.to_numpy(), covariance.to_numpy(), design.to_numpy())
        se = np.sqrt(np.clip(variance, 0, None))
        grid["estimate"] = estimate
        grid["se"] = se
        grid["ci_low"] = estimate - 1.96 * se
        grid["ci_high"] = estimate + 1.96 * se
        counts = (model_data.groupby(["__cycle", "__factor"], observed=True)["__athlete"]
                  .nunique().rename("players").reset_index())
        grid = grid.merge(counts, on=["__cycle", "__factor"], how="left")
        return fitted, grid, cycle_levels, factor_levels_local

    with tabs[0]:
        st.markdown("#### Statistiche descrittive")
        st.dataframe(pd.DataFrame(descriptive_rows), use_container_width=True, hide_index=True)
        if test_rows:
            st.markdown("#### Test scelti automaticamente")
            st.dataframe(pd.DataFrame(test_rows), use_container_width=True, hide_index=True)
            st.markdown("#### Performance Interpretation")
            significant_rows = [row for row in test_rows if pd.notna(row["p"]) and row["p"] < 0.05]
            if significant_rows:
                st.error(
                    f"🚨 **DIFFERENZE SIGNIFICATIVE RILEVATE**  \n"
                    f"Il PAS ha individuato **{len(significant_rows)} confronto/i significativo/i**. "
                    "Le evidenze sono riportate di seguito con entità dell'effetto e lettura operativa."
                )
            for row in test_rows:
                p_value = row["p"]
                if pd.notna(p_value) and p_value < 0.05:
                    stars = _sig_symbol(p_value)
                    effect_text = row["Entità effetto"].lower()
                    relevance = (
                        "molto rilevante sul piano pratico" if abs(row["Effect size"] or 0) >= 0.8
                        else "potenzialmente rilevante sul piano pratico"
                    )
                    mean_a = row.get("Media A")
                    mean_b = row.get("Media B")
                    direction = ""
                    if pd.notna(mean_a) and pd.notna(mean_b) and row.get("Gruppo A") and row.get("Gruppo B"):
                        higher = row["Gruppo A"] if mean_a > mean_b else row["Gruppo B"]
                        lower = row["Gruppo B"] if mean_a > mean_b else row["Gruppo A"]
                        direction = f" **{higher} presenta una media superiore a {lower}** ({max(mean_a, mean_b):.2f} vs {min(mean_a, mean_b):.2f})."
                    p_label = "p corretto" if row.get("Post-hoc") else "p"
                    st.error(
                        f"### {stars} {row['Metrica']} · {row['Strato']}\n"
                        f"**Differenza significativa tra {row['Confronto']}** · {row['Test']} · **{p_label}={p_value:.3f}**  \n"
                        f"Effect size: **{row['Indice']} = {row['Effect size']:.2f} ({effect_text})**.  \n"
                        f"La differenza è statisticamente significativa e **{relevance}**.{direction} "
                        "Lo staff può considerare questo risultato nella lettura del carico e nella programmazione compensativa, "
                        "senza attribuire giudizi qualitativi ai gruppi."
                    )
                else:
                    p_text = f"p={p_value:.3f}" if pd.notna(p_value) else "p non disponibile"
                    st.info(
                        f"**{row['Metrica']} · {row['Strato']}** — Non emerge una differenza statisticamente "
                        f"significativa nel confronto {row['Confronto']} ({row['Test']}, {p_text}). "
                        f"L'entità dell'effetto è **{row['Entità effetto'].lower()}**."
                    )
        else:
            st.info("Il percorso selezionato produce per ora descrittive e visualizzazioni. Aggiungi un fattore con almeno due livelli per il confronto inferenziale.")

    with tabs[1]:
        view_choice = st.radio(
            "Mostra visualizzazioni",
            ["Tutti", "Distribuzione (Raincloud)", "Trend", "Totali per ciclo"],
            horizontal=True,
            key="research_visual_mode",
        )
        cycle_totals_mode = observation_level == "Giocatore per Match Cycle"
        control_cols = st.columns([2, 1])
        with control_cols[0]:
            if cycle_totals_mode:
                total_stat = "Media"
                st.info(
                    "Match Cycle: il PAS somma prima tutte le giornate di ogni "
                    "giocatore e calcola poi la media dei totali individuali per gruppo."
                )
            else:
                total_stat = st.selectbox(
                    "Sintesi nel grafico Totali",
                    ["Media", "Somma", "Mediana"],
                    index=0,
                    key="research_total_stat",
                    help="La statistica viene applicata alle osservazioni aggregate secondo l'unità selezionata.",
                )
        with control_cols[1]:
            show_team_trend = st.checkbox(
                "Mostra Team nel Trend",
                value=False,
                key="research_show_team_trend",
                help="La linea Team è opzionale; il confronto principale resta tra i due gruppi selezionati.",
            )
        st.caption("Significatività: * p<0,05 · ** p<0,01 · *** p<0,001 · **** p<0,0001 · ns = non significativo")

        STARTERS_COLOR = "#1565C0"
        NON_STARTERS_COLOR = "#F57C00"

        def _research_group_style(levels):
            """Colori di gruppo stabili: blu per S/Starters, arancione per NS/No Starters."""
            styles = {}
            fallback = [STARTERS_COLOR, NON_STARTERS_COLOR]
            for idx, raw_level in enumerate(levels):
                level = str(raw_level)
                normalized = level.strip().upper().replace("_", " ")
                is_non_starter = normalized in {"NS", "NO STARTERS", "NON STARTERS", "NO STARTER", "NON STARTER"}
                is_starter = normalized in {"S", "STARTERS", "STARTER"}
                if is_non_starter:
                    color, label = NON_STARTERS_COLOR, "No Starters (NS)"
                elif is_starter:
                    color, label = STARTERS_COLOR, "Starters (S)"
                else:
                    color, label = fallback[idx % len(fallback)], level
                styles[level] = {"color": color, "label": label}
            return styles

        research_report_items = []

        for metric in selected_stat_metrics:
            metric_column = METRICS[metric]["column"]
            metric_unit = METRICS[metric].get("unit", "")
            metric_color = METRICS[metric].get("color", "#4C78A8")
            st.markdown(f"### {metric}")

            if not first_factor:
                fig = go.Figure(go.Histogram(x=analysis_data[metric_column], nbinsx=18, marker_color=metric_color))
                fig.update_layout(title=f"Distribuzione · {metric}", xaxis_title=metric, yaxis_title="Frequenza", height=480)
                st.plotly_chart(fig, use_container_width=True, key=f"research_hist_{metric}")
                research_report_items.append({
                    "title": f"{metric} - Distribuzione",
                    "figure_json": fig.to_json(),
                })
                continue

            factor_label, factor_column = first_factor
            ordered_levels = analysis_data[factor_column].dropna().astype(str).drop_duplicates().tolist()
            within_tests = [
                row for row in test_rows
                if row["Metrica"] == metric and row.get("Confronto nel fattore principale")
            ]
            test_by_level = {}
            for comparison_row in within_tests:
                if comparison_row.get("Test globale"):
                    continue
                test_by_level.setdefault(str(comparison_row["Strato"]), []).append(comparison_row)

            figures = []

            # 1. RAINCLOUD — distribuzione completa con colori fissi per gruppo.
            rain = go.Figure()
            if second_factor:
                second_label, second_column = second_factor
                second_levels = analysis_data[second_column].dropna().astype(str).drop_duplicates().tolist()
                group_styles = _research_group_style(second_levels)
                offsets = np.linspace(-0.20, 0.20, max(len(second_levels), 2))[:len(second_levels)]
                all_y = pd.to_numeric(analysis_data[metric_column], errors="coerce").dropna()
                y_min = float(all_y.min()) if not all_y.empty else 0.0
                y_max = float(all_y.max()) if not all_y.empty else 1.0
                span = max(y_max - y_min, abs(y_max) * 0.10, 1.0)
                annotation_top = y_max

                for group_idx, second_value in enumerate(second_levels):
                    style = group_styles[str(second_value)]
                    for level_idx, level in enumerate(ordered_levels):
                        part = analysis_data[
                            (analysis_data[factor_column].astype(str) == level)
                            & (analysis_data[second_column].astype(str) == second_value)
                        ].dropna(subset=[metric_column])
                        if part.empty:
                            continue
                        xpos = level_idx + offsets[group_idx]
                        rain.add_trace(go.Violin(
                            x=[xpos] * len(part), y=part[metric_column],
                            name=style["label"], legendgroup=str(second_value),
                            side="positive" if group_idx % 2 == 0 else "negative",
                            width=0.34, box_visible=False, meanline_visible=False,
                            points=False, spanmode="hard", scalemode="width",
                            line_color=style["color"], fillcolor=style["color"], opacity=0.30,
                            showlegend=level_idx == 0, hoverinfo="skip",
                        ))
                        rain.add_trace(go.Box(
                            x=[xpos] * len(part), y=part[metric_column],
                            name=style["label"], legendgroup=str(second_value),
                            boxpoints="all", jitter=0.28,
                            pointpos=-1.25 if group_idx % 2 == 0 else 1.25,
                            width=0.10, fillcolor="rgba(255,255,255,0.72)",
                            line=dict(color=style["color"], width=1.8),
                            marker=dict(color=style["color"], size=5, opacity=0.82),
                            customdata=part[["Athlete"]].to_numpy(),
                            hovertemplate="%{customdata[0]}<br>%{y:.2f}<extra></extra>",
                            showlegend=False,
                        ))

                # Barre di significatività tracciate come serie Scatter: restano
                # sopra i raincloud e non vengono nascoste dal rendering Plotly.
                for level_idx, level in enumerate(ordered_levels):
                    rows = [row for row in test_by_level.get(level, []) if pd.notna(row.get("p")) and row["p"] < 0.05]
                    if not rows or len(second_levels) < 2:
                        continue
                    level_values = pd.to_numeric(
                        analysis_data.loc[analysis_data[factor_column].astype(str) == level, metric_column],
                        errors="coerce",
                    ).dropna()
                    local_max = float(level_values.max()) if not level_values.empty else y_max
                    for pair_idx, row in enumerate(rows):
                        group_a = str(row.get("Gruppo A", row["Confronto"].split(" vs ")[0]))
                        group_b = str(row.get("Gruppo B", row["Confronto"].split(" vs ")[-1]))
                        if group_a not in second_levels or group_b not in second_levels:
                            continue
                        bracket_y = local_max + span * (0.115 + pair_idx * 0.105)
                        cap = span * 0.035
                        annotation_top = max(annotation_top, bracket_y + span * 0.08)
                        x0 = level_idx + offsets[second_levels.index(group_a)]
                        x1 = level_idx + offsets[second_levels.index(group_b)]
                        sig_text = _sig_symbol(row["p"])
                        rain.add_trace(go.Scatter(
                            x=[x0, x0, x1, x1], y=[bracket_y-cap, bracket_y, bracket_y, bracket_y-cap],
                            mode="lines", line=dict(color="#111111", width=2.5),
                            hovertemplate=f"{row['Confronto']}<br>{row['Test']}<br>p corretto={row['p']:.4f}<extra></extra>",
                            showlegend=False, cliponaxis=False,
                        ))
                        rain.add_annotation(
                            x=(x0+x1)/2, y=bracket_y+span*0.025, text=f"<b>{sig_text}</b>",
                            showarrow=False, font=dict(color="#111111", size=17), yanchor="bottom",
                        )
                    rain.add_vrect(
                        x0=level_idx - 0.43, x1=level_idx + 0.43,
                        fillcolor="rgba(220,53,69,0.065)", line_width=0, layer="below",
                    )

                rain.update_xaxes(
                    tickmode="array", tickvals=list(range(len(ordered_levels))),
                    ticktext=ordered_levels, categoryorder="array", categoryarray=ordered_levels,
                )
                rain.update_layout(
                    title=f"Distribuzione (Raincloud) · {factor_label} × {second_label}",
                    xaxis_title=factor_label,
                    yaxis_title=f"{metric} {f'({metric_unit})' if metric_unit else ''}",
                    violinmode="overlay", boxmode="overlay",
                    yaxis_range=[y_min - span * 0.06, max(y_max + span * 0.32, annotation_top + span * 0.05)],
                )
            else:
                for level in ordered_levels:
                    part = analysis_data[analysis_data[factor_column].astype(str) == level].dropna(subset=[metric_column])
                    if part.empty:
                        continue
                    rain.add_trace(go.Violin(
                        x=[level] * len(part), y=part[metric_column], name=level,
                        side="positive", width=0.85, box_visible=True, meanline_visible=True,
                        points=False, spanmode="hard", scalemode="width",
                        line_color=metric_color, fillcolor=metric_color, opacity=0.30,
                        hoverinfo="skip", showlegend=False,
                    ))
                    rain.add_trace(go.Box(
                        x=[level] * len(part), y=part[metric_column], name=level,
                        boxpoints="all", jitter=0.28, pointpos=-1.35, width=0.16,
                        fillcolor="rgba(255,255,255,0.65)", line=dict(color=metric_color, width=1.5),
                        marker=dict(color=metric_color, size=5, opacity=0.78),
                        customdata=part[["Athlete"]].to_numpy(),
                        hovertemplate="%{customdata[0]}<br>%{y:.2f}<extra></extra>", showlegend=False,
                    ))
                pair_rows = [
                    row for row in test_rows
                    if row["Metrica"] == metric and row["Strato"] == "Totale"
                    and not row.get("Test globale") and pd.notna(row.get("p")) and row["p"] < 0.05
                ]
                all_y = pd.to_numeric(analysis_data[metric_column], errors="coerce").dropna()
                y_min = float(all_y.min()) if not all_y.empty else 0.0
                y_max = float(all_y.max()) if not all_y.empty else 1.0
                span = max(y_max-y_min, abs(y_max)*0.10, 1.0)
                top = y_max
                for pair_idx, row in enumerate(pair_rows):
                    group_a = str(row.get("Gruppo A", row["Confronto"].split(" vs ")[0]))
                    group_b = str(row.get("Gruppo B", row["Confronto"].split(" vs ")[-1]))
                    if group_a not in ordered_levels or group_b not in ordered_levels:
                        continue
                    x0, x1 = ordered_levels.index(group_a), ordered_levels.index(group_b)
                    bracket_y = y_max + span*(0.12 + pair_idx*0.10)
                    cap = span*0.03
                    top = max(top, bracket_y+span*0.07)
                    rain.add_trace(go.Scatter(
                        x=[group_a, group_a, group_b, group_b], y=[bracket_y-cap, bracket_y, bracket_y, bracket_y-cap],
                        mode="lines", line=dict(color="#111111", width=2.5), showlegend=False, cliponaxis=False,
                        hovertemplate=f"{row['Confronto']}<br>{row['Test']}<br>p corretto={row['p']:.4f}<extra></extra>",
                    ))
                    rain.add_annotation(x=(x0+x1)/2, y=bracket_y+span*0.02, xref="x", text=f"<b>{_sig_symbol(row['p'])}</b>", showarrow=False, font=dict(size=17))
                rain.update_layout(
                    title=f"Distribuzione (Raincloud) · {metric} per {factor_label}",
                    xaxis_title=factor_label, yaxis_title=metric,
                    yaxis_range=[y_min-span*0.06, top+span*0.05] if pair_rows else None,
                )
            rain.update_layout(height=540, margin=dict(l=35, r=20, t=85, b=50), legend=dict(orientation="h", y=-0.15))
            figures.append(("rain", rain))

            if second_factor:
                second_label, second_column = second_factor
                second_levels = analysis_data[second_column].dropna().astype(str).drop_duplicates().tolist()
                group_styles = _research_group_style(second_levels)

                # 2. TREND — con più cicli usa un LMM: Cycle × fattore principale + (1|giocatore).
                trend = go.Figure()
                use_cycle_lmm = (
                    cycle_totals_mode
                    and match_cycle_comparison_mode == "Confronta più cicli gara · Linear Mixed Model"
                    and second_column == "Cycle"
                    and factor_column != "Cycle"
                )
                if use_cycle_lmm:
                    try:
                        fitted_lmm, emm, cycle_order, primary_levels = _fit_cycle_mixed_model(
                            analysis_data, metric_column, factor_column
                        )
                        primary_styles = _research_group_style(primary_levels)
                        for primary_value in primary_levels:
                            style = primary_styles[str(primary_value)]
                            part = emm[emm["__factor"].astype(str) == str(primary_value)].copy()
                            part["__cycle"] = pd.Categorical(part["__cycle"].astype(str), categories=cycle_order, ordered=True)
                            part = part.sort_values("__cycle")
                            custom = np.column_stack([part["players"].fillna(0).astype(int), part["ci_low"], part["ci_high"]])
                            trend.add_trace(go.Scatter(
                                x=part["__cycle"].astype(str), y=part["estimate"],
                                error_y=dict(type="data", array=1.96 * part["se"], visible=True, thickness=1.4),
                                mode="lines+markers", name=style["label"],
                                line=dict(color=style["color"], width=3),
                                marker=dict(size=9, color=style["color"]),
                                customdata=custom,
                                hovertemplate=(
                                    f"{factor_label}: {primary_value}<br>Match Cycle: %{{x}}<br>"
                                    "Media marginale stimata: %{y:.2f}<br>IC95%: %{customdata[1]:.2f} – %{customdata[2]:.2f}<br>"
                                    "Giocatori nel ciclo/gruppo: %{customdata[0]:.0f}<extra></extra>"
                                ),
                            ))
                        trend.update_xaxes(categoryorder="array", categoryarray=cycle_order)
                        trend.update_layout(
                            title=f"Trend LMM delle medie marginali · {metric}",
                            xaxis_title="Match Cycle",
                            yaxis_title=f"Media marginale stimata · {metric} {f'({metric_unit})' if metric_unit else ''}",
                            hovermode="x unified", height=500, legend=dict(orientation="h", y=-0.18),
                        )
                        st.caption(
                            f"Linear Mixed Model: {metric} ~ Match Cycle × {factor_label} + (1 | Giocatore). "
                            f"N={len(fitted_lmm.model.endog)} osservazioni giocatore-ciclo; "
                            f"{analysis_data['Athlete'].nunique()} giocatori. Le linee sono medie marginali stimate."
                        )
                    except Exception as exc:
                        st.error(f"Linear Mixed Model non stimabile con i dati selezionati: {exc}")
                else:
                    if (cycle_totals_mode and match_cycle_comparison_mode == "Confronta più cicli gara · Linear Mixed Model"
                            and second_column != "Cycle"):
                        st.warning("Per il confronto LMM imposta Match Cycle come secondo fattore.")
                    for second_value in second_levels:
                        style = group_styles[str(second_value)]
                        part = analysis_data[analysis_data[second_column].astype(str) == second_value].copy()
                        summary = part.groupby(factor_column, dropna=False)[metric_column].agg(["mean", "std", "count"]).reset_index()
                        summary["level"] = summary[factor_column].astype(str)
                        summary["ci95"] = 1.96 * summary["std"] / np.sqrt(summary["count"].clip(lower=1))
                        summary["level"] = pd.Categorical(summary["level"], categories=ordered_levels, ordered=True)
                        summary = summary.sort_values("level")
                        trend.add_trace(go.Scatter(
                            x=summary["level"].astype(str), y=summary["mean"],
                            error_y=dict(type="data", array=summary["ci95"], visible=True, thickness=1.4),
                            mode="lines+markers", name=style["label"],
                            line=dict(color=style["color"], width=3), marker=dict(size=9, color=style["color"]),
                            hovertemplate=f"{second_label}: {second_value}<br>{factor_label}: %{{x}}<br>Media: %{{y:.2f}}<extra></extra>",
                        ))
                    trend.update_xaxes(categoryorder="array", categoryarray=ordered_levels)
                    trend.update_layout(
                        title=f"Trend delle medie · {factor_label}", xaxis_title=factor_label,
                        yaxis_title=f"{metric} {f'({metric_unit})' if metric_unit else ''}", hovermode="x unified",
                        height=500, legend=dict(orientation="h", y=-0.18),
                    )
                figures.append(("trend", trend))

                # 3. TOTALI — nel Match Cycle sono sempre la media dei totali
                # individuali. Con più cicli il confronto S/NS è mostrato con
                # due linee: blu per S e arancione per NS.
                agg_name = "mean" if cycle_totals_mode else {
                    "Media": "mean", "Somma": "sum", "Mediana": "median"
                }[total_stat]
                totals = go.Figure()
                multi_cycle_lines = (
                    cycle_totals_mode
                    and factor_column == "Cycle"
                    and len(ordered_levels) > 1
                )
                for second_value in second_levels:
                    style = group_styles[str(second_value)]
                    part = analysis_data[analysis_data[second_column].astype(str) == second_value].copy()
                    grouped = part.groupby(factor_column, dropna=False)[metric_column].agg(agg_name).reset_index()
                    grouped["level"] = grouped[factor_column].astype(str)
                    grouped["level"] = pd.Categorical(grouped["level"], categories=ordered_levels, ordered=True)
                    grouped = grouped.sort_values("level")
                    if multi_cycle_lines:
                        totals.add_trace(go.Scatter(
                            x=grouped["level"].astype(str),
                            y=grouped[metric_column],
                            mode="lines+markers",
                            name=style["label"],
                            line=dict(color=style["color"], width=3),
                            marker=dict(color=style["color"], size=9),
                            hovertemplate=(
                                f"{second_label}: {second_value}<br>Match Cycle: %{{x}}<br>"
                                "Media totali individuali: %{y:.2f}<extra></extra>"
                            ),
                        ))
                    else:
                        totals.add_trace(go.Bar(
                            x=grouped["level"].astype(str), y=grouped[metric_column], name=style["label"],
                            marker_color=style["color"],
                            hovertemplate=f"{second_label}: {second_value}<br>{factor_label}: %{{x}}<br>{total_stat}: %{{y:.2f}}<extra></extra>",
                        ))
                total_y = [v for trace in totals.data for v in trace.y if pd.notna(v)]
                y_max_total = max(total_y) if total_y else 1.0
                for level in ordered_levels:
                    level_rows = test_by_level.get(str(level), [])
                    significant_level_rows = [
                        row for row in level_rows
                        if pd.notna(row.get("p")) and row["p"] < 0.05
                    ]
                    if significant_level_rows:
                        # Un ciclo può contenere più confronti pairwise (es. più ruoli).
                        # Mostra tutti i simboli significativi senza assumere che la
                        # struttura sia una singola riga statistica.
                        significant_level_rows = sorted(
                            significant_level_rows, key=lambda item: float(item["p"])
                        )
                        symbols = " ".join(_sig_symbol(row["p"]) for row in significant_level_rows)
                        hover_text = "<br>".join(
                            f"{row.get('Confronto', 'Confronto')}: p={row['p']:.4f}"
                            for row in significant_level_rows
                        )
                        totals.add_annotation(
                            x=level, y=y_max_total * 1.10,
                            text=f"<b>{symbols}</b>", showarrow=False,
                            font=dict(color="#111111", size=17),
                            hovertext=hover_text,
                        )
                totals.update_xaxes(categoryorder="array", categoryarray=ordered_levels)
                totals.update_layout(
                    title=(
                        f"Media dei totali individuali per {factor_label}"
                        if cycle_totals_mode
                        else f"{total_stat} per {factor_label}"
                    ),
                    xaxis_title="Match Cycle" if multi_cycle_lines else factor_label,
                    yaxis_title=(
                        f"Media totali individuali · {metric}"
                        if cycle_totals_mode
                        else f"{total_stat} · {metric}"
                    ),
                    barmode="group",
                    height=500,
                    yaxis_range=[0, y_max_total * 1.22],
                    legend=dict(orientation="h", y=-0.18),
                )
                figures.append(("totals", totals))

            # Render coerente con il selettore, con Tutti come vista predefinita.
            selected_kinds = {
                "Tutti": {"rain", "trend", "totals"},
                "Distribuzione (Raincloud)": {"rain"},
                "Trend": {"trend"},
                "Totali per ciclo": {"totals"},
            }[view_choice]
            visible_figures = [(kind, fig) for kind, fig in figures if kind in selected_kinds]
            if view_choice == "Tutti" and len(visible_figures) >= 2:
                cols = st.columns(min(3, len(visible_figures)))
                for idx, (kind, fig) in enumerate(visible_figures):
                    with cols[idx % len(cols)]:
                        st.plotly_chart(fig, use_container_width=True, key=f"research_{kind}_{metric}")
            else:
                for kind, fig in visible_figures:
                    st.plotly_chart(fig, use_container_width=True, key=f"research_{kind}_{metric}")

            kind_labels = {
                "rain": "Distribuzione",
                "trend": "Trend",
                "totals": "Totali",
            }
            for kind, fig in visible_figures:
                research_report_items.append({
                    "title": f"{metric} - {kind_labels.get(kind, kind.title())}",
                    "figure_json": fig.to_json(),
                })

            if within_tests:
                st.markdown("#### Performance Score per livello")
                score_cols = st.columns(min(6, max(1, len(ordered_levels))))
                for idx, level in enumerate(ordered_levels):
                    level_rows = test_by_level.get(str(level), [])
                    if not level_rows:
                        continue
                    valid_rows = [row for row in level_rows if pd.notna(row.get("p"))]
                    if not valid_rows:
                        continue
                    # Per la card sintetica usa il confronto con il p-value più basso;
                    # i dettagli completi di tutte le coppie restano nella Sintesi.
                    row = min(valid_rows, key=lambda item: float(item["p"]))
                    score_text, icon = _effect_score(row.get("Effect size"), row["p"])
                    comparison = row.get("Confronto", "Confronto")
                    with score_cols[idx % len(score_cols)]:
                        st.metric(
                            str(level),
                            f"{icon} {_sig_symbol(row['p'])}",
                            f"{comparison} · {score_text}",
                        )
        st.divider()
        st.subheader("Stampa grafici")
        st.caption(
            "Crea un PDF A4 orizzontale pronto per la stampa: massimo 4 grafici per pagina. "
            "Titoli, legende e annotazioni di significatività vengono mantenuti."
        )
        research_print_titles = [item["title"] for item in research_report_items]
        selected_research_print_titles = st.multiselect(
            "Grafici da stampare",
            research_print_titles,
            default=research_print_titles,
            key="research_print_chart_selection_v3715",
        )
        selected_research_report_items = [
            item for item in research_report_items
            if item["title"] in selected_research_print_titles
        ]
        research_report_title = st.text_input(
            "Titolo del report",
            value="PERFORMANCE RESEARCH REPORT",
            key="research_print_report_title_v3715",
        )
        print_col, info_col = st.columns([1, 2])
        with print_col:
            if st.button(
                "Genera PDF dei grafici",
                type="primary",
                use_container_width=True,
                disabled=not selected_research_report_items,
                key="research_generate_print_pdf_v3715",
            ):
                factor_context = ", ".join(
                    f"{label}: {', '.join(analysis_data[column].dropna().astype(str).drop_duplicates().tolist())}"
                    for label, column in selected_factors
                )
                with pas_loader("Creazione PDF dei grafici..."):
                    st.session_state["research_print_pdf_v3715"] = build_pdf_report(
                        selected_research_report_items,
                        research_report_title,
                        [
                            f"Unità di osservazione: {observation_level}",
                            f"Fattori: {factor_context or 'nessuno'}",
                            f"Metriche: {', '.join(selected_stat_metrics)}",
                            "Significatività: * p<0,05; ** p<0,01; *** p<0,001; **** p<0,0001.",
                        ],
                    )
        with info_col:
            st.info(
                f"Grafici selezionati: {len(selected_research_report_items)}. "
                "Dal quinto grafico viene creata automaticamente una nuova pagina."
            )
        if st.session_state.get("research_print_pdf_v3715"):
            st.download_button(
                "Scarica / stampa PDF",
                data=st.session_state["research_print_pdf_v3715"],
                file_name="Performance_Research_Graphs.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="research_download_print_pdf_v3715",
            )

    with tabs[2]:
        if len(selected_stat_metrics) < 2:
            st.info("Seleziona almeno due metriche per studiarne la relazione.")
        else:
            correlation_rows = []
            for i, metric_x in enumerate(selected_stat_metrics):
                for metric_y in selected_stat_metrics[i + 1:]:
                    result = correlation_analysis(
                        analysis_data[METRICS[metric_x]["column"]],
                        analysis_data[METRICS[metric_y]["column"]],
                    )
                    correlation_rows.append({
                        "Metrica X": metric_x, "Metrica Y": metric_y,
                        "Test": result["test"], "Coefficiente": result["coefficient"],
                        "p": result["p_value"], "Entità": result["magnitude"],
                    })
            st.dataframe(pd.DataFrame(correlation_rows), use_container_width=True, hide_index=True)

    with tabs[3]:
        display_columns = [column for column in ["Athlete", "Date", "Cycle"] if column in analysis_data]
        display_columns += [column for _, column in selected_factors if column not in display_columns]
        display_columns += [METRICS[metric]["column"] for metric in selected_stat_metrics]
        st.dataframe(analysis_data[display_columns], use_container_width=True, hide_index=True)
    st.stop()

if page == "📊 Period Load":
    st.title("📊 Period Load")
    st.caption(
        "Carico cumulativo individuale per intervallo di date "
        "oppure per uno o più Match Cycle."
    )

    allowed_period_drills = {
        "Full Training",
        "Individual Training",
        "Return to Play",
        "Active Recovery",
        "Different Training",
        "Different Traning",
        "Match",
        "Recovery",
    }

    st.sidebar.header("Period Load Filters")

    period_selection_mode = st.sidebar.radio(
        "Selezione periodo",
        ["Intervallo di date", "Uno o più Match Cycle"],
        index=1,
        key="period_totals_mode",
        help=(
            "Di default viene selezionato il ciclo gara corrente. "
            "Puoi passare manualmente all'intervallo di date."
        ),
    )

    all_dates = sorted(raw["Date"].dt.date.unique())
    latest_date = pd.Timestamp(max(all_dates))
    default_period_start = max(
        pd.Timestamp(min(all_dates)),
        latest_date - timedelta(days=27),
    )

    selected_period_cycles: list[str] = []

    if period_selection_mode == "Intervallo di date":
        period_total_dates = st.sidebar.date_input(
            "Intervallo",
            value=(
                default_period_start.date(),
                latest_date.date(),
            ),
            min_value=min(all_dates),
            max_value=max(all_dates),
            format="DD/MM/YYYY",
            key="period_totals_dates",
        )

        if (
            isinstance(period_total_dates, tuple)
            and len(period_total_dates) == 2
        ):
            period_total_start = pd.Timestamp(
                period_total_dates[0]
            )
            period_total_end = pd.Timestamp(
                period_total_dates[1]
            )
        else:
            period_total_start = pd.Timestamp(
                period_total_dates
            )
            period_total_end = pd.Timestamp(
                period_total_dates
            )

        period_totals_raw = raw[
            raw["Date"].dt.normalize().between(
                period_total_start.normalize(),
                period_total_end.normalize(),
            )
        ].copy()

        period_totals_description = (
            f"{period_total_start.strftime('%d/%m/%Y')} → "
            f"{period_total_end.strftime('%d/%m/%Y')}"
        )
    else:
        cycle_order = (
            raw[["Cycle", "Date"]]
            .dropna(subset=["Cycle", "Date"])
            .groupby("Cycle", as_index=False)["Date"]
            .max()
            .sort_values("Date")
        )
        available_period_cycles = (
            cycle_order["Cycle"].astype(str).tolist()
        )

        selected_period_cycles = st.sidebar.multiselect(
            "Match Cycle",
            available_period_cycles,
            default=available_period_cycles[-1:],
            key="period_totals_cycles",
        )

        period_totals_raw = raw[
            raw["Cycle"].astype(str).isin(
                selected_period_cycles
            )
        ].copy()

        period_totals_description = (
            ", ".join(selected_period_cycles)
            if selected_period_cycles
            else "Nessun ciclo selezionato"
        )

    period_totals_raw = period_totals_raw[
        period_totals_raw["Drill"].isin(
            allowed_period_drills
        )
    ].copy()

    period_intelligence_request = st.session_state.get("period_intelligence_request")
    if period_intelligence_request is not None:
        requested_roles = getattr(period_intelligence_request, "roles", [])
        requested_statuses = getattr(period_intelligence_request, "starter_statuses", [])
        role_column = "Role Clean" if "Role Clean" in period_totals_raw.columns else ("Role" if "Role" in period_totals_raw.columns else None)
        if requested_roles and role_column:
            period_totals_raw = period_totals_raw[period_totals_raw[role_column].astype(str).isin(requested_roles)].copy()
        if requested_statuses and "Starters / No Starters" in period_totals_raw.columns:
            period_totals_raw = period_totals_raw[period_totals_raw["Starters / No Starters"].astype(str).str.upper().isin(requested_statuses)].copy()

    available_period_players = sorted(
        period_totals_raw["Athlete"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if "period_totals_players" in st.session_state:
        st.session_state["period_totals_players"] = [
            player for player in st.session_state["period_totals_players"]
            if player in available_period_players
        ]

    selected_period_players = st.sidebar.multiselect(
        "Giocatori",
        available_period_players,
        default=available_period_players,
        key="period_totals_players",
        help=(
            "Tutti i giocatori sono inclusi di default. "
            "Deseleziona dalla lista quelli che vuoi escludere."
        ),
    )

    selected_period_metrics = st.sidebar.multiselect(
        "Metriche",
        list(METRICS.keys()),
        default=list(METRICS.keys()),
        key="period_totals_metrics",
    )

    period_totals_source_raw = period_totals_raw.copy()

    if selected_period_players:
        period_totals_raw = period_totals_raw[
            period_totals_raw["Athlete"].isin(
                selected_period_players
            )
        ].copy()

    period_player_day = aggregate_player_day(
        period_totals_raw
    )

    def aggregate_period_players(
        player_day_frame: pd.DataFrame,
        selected_players: list[str],
    ) -> pd.DataFrame:
        if player_day_frame.empty:
            return pd.DataFrame()

        # Nessun giocatore selezionato:
        # Team Average giornaliero, poi accumulo del periodo.
        if not selected_players:
            team_row: dict[str, object] = {
                "Athlete": "TEAM AVERAGE",
                "Role Clean": "",
            }

            for metric_name, meta in METRICS.items():
                column = meta["column"]
                if column not in player_day_frame.columns:
                    team_row[column] = np.nan
                    continue

                daily_team_average = (
                    player_day_frame.assign(
                        _metric_value=pd.to_numeric(
                            player_day_frame[column],
                            errors="coerce",
                        )
                    )
                    .dropna(subset=["_metric_value"])
                    .groupby(
                        "Date",
                        as_index=False,
                    )["_metric_value"]
                    .mean()
                )

                if daily_team_average.empty:
                    team_row[column] = np.nan
                    continue

                values = daily_team_average[
                    "_metric_value"
                ]

                if metric_name == "Max Speed (km/h)":
                    team_row[column] = float(values.max())
                elif metric_name == "RPE":
                    team_row[column] = float(values.mean())
                else:
                    team_row[column] = float(values.sum())

            return pd.DataFrame([team_row])

        # Uno o più giocatori selezionati:
        # accumulo individuale.
        rows: list[dict[str, object]] = []

        for athlete, athlete_data in player_day_frame.groupby(
            "Athlete"
        ):
            row: dict[str, object] = {
                "Athlete": athlete,
            }

            if "Role Clean" in athlete_data.columns:
                role_values = (
                    athlete_data["Role Clean"]
                    .dropna()
                    .astype(str)
                )
                row["Role Clean"] = (
                    role_values.iloc[0]
                    if not role_values.empty
                    else ""
                )

            if "Starters / No Starters" in athlete_data.columns:
                status_values = (
                    athlete_data["Starters / No Starters"]
                    .dropna()
                    .astype(str)
                    .str.upper()
                )
                status_values = status_values[status_values.isin(["S", "NS"])]
                row["Starters / No Starters"] = (
                    status_values.mode().iloc[0]
                    if not status_values.empty
                    else ""
                )

            for metric_name, meta in METRICS.items():
                column = meta["column"]
                if column not in athlete_data.columns:
                    row[column] = np.nan
                    continue

                values = pd.to_numeric(
                    athlete_data[column],
                    errors="coerce",
                ).dropna()

                if values.empty:
                    row[column] = np.nan
                elif metric_name == "Max Speed (km/h)":
                    row[column] = float(values.max())
                elif metric_name == "RPE":
                    row[column] = float(values.mean())
                else:
                    row[column] = float(values.sum())

            rows.append(row)

        return pd.DataFrame(rows)

    period_totals_data = aggregate_period_players(
        period_player_day,
        selected_period_players,
    )

    period_match_references = build_period_match_references(
        raw,
        METRICS,
    )
    (
        period_totals_data,
        period_match_percentages,
    ) = attach_match_load_percentages(
        period_totals_data,
        period_match_references,
        selected_period_players,
        METRICS,
    )

    historical_max_speed_references = (
        build_historical_max_speed_references(report_source)
    )
    period_max_speed_percentages = (
        build_max_speed_percentage_data(
            period_totals_data,
            historical_max_speed_references,
            team_average_mode=not selected_period_players,
        )
    )

    max_speed_pct_column = (
        f"{METRICS['Max Speed (km/h)']['column']}"
        "__match_pct"
    )

    if not period_max_speed_percentages.empty:
        if period_match_percentages.empty:
            period_match_percentages = (
                period_max_speed_percentages.copy()
            )
        else:
            period_match_percentages = (
                period_match_percentages.drop(
                    columns=[max_speed_pct_column],
                    errors="ignore",
                )
                .merge(
                    period_max_speed_percentages[
                        ["Athlete", max_speed_pct_column]
                    ],
                    on="Athlete",
                    how="left",
                )
            )

    st.subheader("Riepilogo selezione")
    c1, c2, c3 = st.columns(3)
    c1.metric("Periodo", period_totals_description)
    c2.metric(
        (
            "Modalità"
            if not selected_period_players
            else "Giocatori"
        ),
        (
            "Team Average"
            if not selected_period_players
            else len(period_totals_data)
        ),
    )
    c3.metric(
        "Sedute incluse",
        period_totals_raw[
            ["Date", "Drill"]
        ].drop_duplicates().shape[0],
    )

    if period_totals_data.empty:
        st.warning(
            "Nessun dato disponibile per i filtri selezionati."
        )
        st.stop()

    period_totals_view_label = (
        "Team Average del periodo"
        if not selected_period_players
        else "Totali individuali"
    )
    st.subheader(period_totals_view_label)

    for metric_name in selected_period_metrics:
        meta = METRICS[metric_name]
        metric_column = meta["column"]

        if metric_column not in period_totals_data.columns:
            continue

        metric_values = (
            period_totals_data[
                ["Athlete", metric_column]
            ]
            .dropna(subset=[metric_column])
            .sort_values(
                metric_column,
                ascending=True,
            )
        )

        if metric_values.empty:
            continue

        comparison = metric_values.rename(
            columns={
                "Athlete": "Label",
                metric_column: "Value",
            }
        )
        comparison["Type"] = "Player"

        pct_column = f"{metric_column}__match_pct"
        if (
            metric_name not in {"Duration (min)", "RPE"}
            and not period_match_percentages.empty
            and pct_column in period_match_percentages.columns
        ):
            comparison = comparison.merge(
                period_match_percentages[
                    ["Athlete", pct_column]
                ].rename(
                    columns={
                        "Athlete": "Label",
                        pct_column: "MatchPercent",
                    }
                ),
                on="Label",
                how="left",
            )
            comparison["DisplayLabel"] = [
                (
                    f"{fmt_metric(value, metric_name)}"
                    + (
                        (
                            f"<br>{match_pct:.0f}%"
                        )
                        if pd.notna(match_pct)
                        else ""
                    )
                )
                for value, match_pct in zip(
                    comparison["Value"],
                    comparison["MatchPercent"],
                )
            ]

        st.markdown(
            f'<div class="pas-section-title">'
            f'{metric_name}</div>',
            unsafe_allow_html=True,
        )

        period_figure = player_comparison_chart(
            comparison=comparison,
            unit=meta.get("unit", ""),
            color=meta.get("color"),
            decimals=int(meta.get("decimals", 0)),
            format_type=str(
                meta.get("format", "number")
            ),
        )
        st.plotly_chart(
            period_figure,
            use_container_width=True,
            key=f"period_totals_{metric_name}",
        )

    st.divider()
    st.subheader("Match Load Percentage Summary")
    if not period_match_percentages.empty:
        with st.expander(
            "Show percentage summary",
            expanded=True,
        ):
            summary_rows = []
            for _, period_row in period_totals_data.iterrows():
                athlete_name = period_row.get("Athlete", "N/D")
                pct_row = period_match_percentages[
                    period_match_percentages["Athlete"].eq(
                        athlete_name
                    )
                ]
                if pct_row.empty:
                    continue
                pct_row = pct_row.iloc[0]
                for metric_name in selected_period_metrics:
                    if metric_name in {"Duration (min)", "RPE"}:
                        continue
                    column = METRICS[metric_name]["column"]
                    pct_value = pct_row.get(
                        f"{column}__match_pct"
                    )
                    absolute_value = period_row.get(column)
                    if pd.isna(absolute_value):
                        continue
                    summary_rows.append(
                        {
                            "Giocatore": athlete_name,
                            "Parametro": metric_name,
                            "Valore": fmt_metric(
                                absolute_value,
                                metric_name,
                            ),
                            (
                                "%"
                                if metric_name
                                == "Max Speed (km/h)"
                                else "% gara"
                            ): (
                                f"{float(pct_value):.0f}%"
                                if pd.notna(pct_value)
                                else "N/D"
                            ),
                        }
                    )
            if summary_rows:
                st.dataframe(
                    pd.DataFrame(summary_rows),
                    use_container_width=True,
                    hide_index=True,
                )


    st.divider()
    st.subheader("Period Load Report PDF")

    period_report_title = st.text_input(
        "Titolo report",
        value="PERIOD LOAD REPORT",
        key="period_report_title",
    )

    period_report_metrics = st.multiselect(
        "Metriche nel report",
        list(METRICS.keys()),
        default=selected_period_metrics,
        key="period_report_metrics",
    )

    if st.button(
        "Genera Period Load Report PDF",
        type="primary",
        use_container_width=True,
        disabled=(
            period_totals_data.empty
            or not period_report_metrics
        ),
    ):
        report_context = {
            "date": period_totals_description,
            "match_day": (
                "Team Average cumulativo"
                if not selected_period_players
                else "Periodo cumulativo individuale"
            ),
            "cycle": (
                ", ".join(selected_period_cycles)
                if selected_period_cycles
                else "Intervallo di date"
            ),
            "drill": (
                "Full Training, Individual Training, Return to Play, "
                "Active Recovery, Different Training, Match, Recovery"
            ),
            "time_of_day": "",
        }

        with pas_loader(
            "Creazione Period Load Report..."
        ):
            st.session_state[
                "generated_period_report_pdf"
            ] = build_session_report_pdf(
                session_data=period_totals_data,
                selected_metrics=period_report_metrics,
                metric_specs=METRICS,
                report_title=period_report_title,
                session_context=report_context,
                different_training_data=None,
                percentage_data=period_match_percentages,
                percentage_label="",
                fit_rows_to_page=True,
                group_column=(
                    "Starters / No Starters"
                    if "Starters / No Starters" in period_totals_data.columns
                    else None
                ),
                group_order=["S", "NS"],
                show_group_prefix=True,
                show_group_separator=True,
            )

    if st.session_state.get(
        "generated_period_report_pdf"
    ):
        st.download_button(
            "Scarica / stampa Period Load Report",
            data=st.session_state[
                "generated_period_report_pdf"
            ],
            file_name="Period_Load_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    with st.expander(
        "Verifica sedute incluse",
        expanded=False,
    ):
        audit_source = (
            period_totals_source_raw
            if not selected_period_players
            else period_totals_raw
        )

        audit_columns = [
            column
            for column in [
                "Date",
                "Athlete",
                "Drill",
                "Cycle",
            ]
            if column in audit_source.columns
        ]

        audit_table = (
            audit_source[audit_columns]
            .drop_duplicates()
            .sort_values(
                ["Date", "Athlete", "Drill"]
            )
            .copy()
        )
        if "Date" in audit_table.columns:
            audit_table["Date"] = pd.to_datetime(
                audit_table["Date"]
            ).dt.strftime("%d/%m/%Y")

        st.dataframe(
            audit_table,
            use_container_width=True,
            hide_index=True,
        )

    st.stop()




if page == "🗓️ Planner":
    st.title("🗓️ Planner")
    st.caption(
        "Pianifica la settimana, entra nella giornata con un click "
        "e costruisci allenamenti o partite in modo rapido."
    )

    planner_store = load_planner_store(base_dir)
    planner_store.setdefault("days", {})
    planner_store.setdefault("templates", {})
    planner_store.setdefault("exercise_library", {})

    all_planner_players = sorted(
        raw["Athlete"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    library_exercise_names = list(
        planner_store.get("exercise_library", {}).keys()
    )

    all_drill_names = sorted(
        {
            *exercises_raw["Drill"]
            .dropna()
            .astype(str)
            .tolist(),
            *exercises_avg["Drill"]
            .dropna()
            .astype(str)
            .tolist(),
            *library_exercise_names,
        }
    )

    if "planner_selected_date" not in st.session_state:
        st.session_state["planner_selected_date"] = (
            pd.Timestamp.today().strftime("%Y-%m-%d")
        )

    if "planner_view" not in st.session_state:
        st.session_state["planner_view"] = "calendar"

    selected_date_key = st.session_state["planner_selected_date"]
    selected_date = pd.Timestamp(selected_date_key)

    # =====================================================
    # CALENDAR VIEW
    # =====================================================
    if st.session_state["planner_view"] == "calendar":
        nav_cols = st.columns([1, 2, 1])

        if nav_cols[0].button(
            "◀ Mese precedente",
            use_container_width=True,
        ):
            previous_month = selected_date - pd.offsets.MonthBegin(1)
            st.session_state["planner_selected_date"] = (
                previous_month.strftime("%Y-%m-%d")
            )
            st.rerun()

        nav_cols[1].markdown(
            (
                "<div style='text-align:center;"
                "font-size:1.35rem;font-weight:850;"
                "padding:0.4rem 0;'>"
                f"{selected_date.strftime('%B %Y')}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        if nav_cols[2].button(
            "Mese successivo ▶",
            use_container_width=True,
        ):
            next_month = selected_date + pd.offsets.MonthBegin(1)
            st.session_state["planner_selected_date"] = (
                next_month.strftime("%Y-%m-%d")
            )
            st.rerun()

        clicked_day = render_planner_calendar(
            planner_store,
            selected_date,
        )

        if clicked_day:
            st.session_state["planner_selected_date"] = clicked_day
            st.session_state["planner_view"] = "day"
            st.rerun()

        st.caption(
            "Clicca su un giorno per entrare nella giornata. "
            "Allenamenti e partite già salvati sono visibili nel calendario."
        )

    # =====================================================
    # DAY VIEW
    # =====================================================
    else:
        header_cols = st.columns([0.18, 0.62, 0.20])

        if header_cols[0].button(
            "← Calendario",
            use_container_width=True,
        ):
            st.session_state["planner_view"] = "calendar"
            st.rerun()

        header_cols[1].markdown(
            (
                "<div style='text-align:center;"
                "font-size:1.25rem;font-weight:850;"
                "padding:0.4rem 0;'>"
                f"{selected_date.strftime('%A %d/%m/%Y')}"
                "</div>"
            ),
            unsafe_allow_html=True,
        )

        new_date = header_cols[2].date_input(
            "Data",
            value=selected_date.date(),
            format="DD/MM/YYYY",
            label_visibility="collapsed",
        )

        new_date_key = pd.Timestamp(new_date).strftime("%Y-%m-%d")
        if new_date_key != selected_date_key:
            st.session_state["planner_selected_date"] = new_date_key
            st.rerun()

        day_payload = planner_store["days"].get(
            selected_date_key,
            {},
        )

        activities = sort_planner_activities(
            day_payload.get("activities", [])
        )

        # -------------------------------------------------
        # EMPTY DAY
        # -------------------------------------------------
        if not day_payload:
            st.subheader("Cosa vuoi pianificare?")

            choice_cols = st.columns(2)

            if choice_cols[0].button(
                "🏋️ Allenamento",
                type="primary",
                use_container_width=True,
            ):
                planner_store["days"][selected_date_key] = {
                    "day_type": "Training",
                    "title": "",
                    "match_day": "",
                    "general_notes": "",
                    "activities": [
                        planner_default_activity(
                            all_planner_players
                        )
                    ],
                    "participants": list(
                        all_planner_players
                    ),
                    "player_statuses": {
                        player: "Full Training"
                        for player in all_planner_players
                    },
                    "player_notes": {},
                }
                save_planner_store(base_dir, planner_store)
                st.rerun()

            if choice_cols[1].button(
                "⚽ Partita",
                use_container_width=True,
            ):
                planner_store["days"][selected_date_key] = {
                    "day_type": "Match",
                    "activities": [
                        {
                            "type": "Official Match",
                            "title": "",
                            "opponent": "",
                            "location": "Home",
                            "competition": "",
                            "start_time": "",
                            "notes": "",
                            "participants": list(
                                all_planner_players
                            ),
                            "drills": [],
                        }
                    ],
                    "participants": list(
                        all_planner_players
                    ),
                }
                save_planner_store(base_dir, planner_store)
                st.rerun()

            template_names = sorted(
                planner_store.get("templates", {}).keys()
            )

            if template_names:
                st.divider()
                st.subheader("Oppure usa un template")

                template_cols = st.columns([0.72, 0.28])
                selected_template = template_cols[0].selectbox(
                    "Template",
                    template_names,
                    label_visibility="collapsed",
                )

                if template_cols[1].button(
                    "Applica template",
                    use_container_width=True,
                ):
                    planner_store["days"][
                        selected_date_key
                    ] = json.loads(
                        json.dumps(
                            planner_store["templates"][
                                selected_template
                            ]
                        )
                    )
                    save_planner_store(
                        base_dir,
                        planner_store,
                    )
                    st.rerun()

            st.stop()

        day_type = day_payload.get(
            "day_type",
            "Training",
        )

        # -------------------------------------------------
        # MATCH DAY
        # -------------------------------------------------
        if day_type == "Match":
            st.subheader("⚽ Partita")

            match_activity = activities[0]

            with st.form(
                f"planner_match_{selected_date_key}"
            ):
                match_cols = st.columns(
                    [0.20, 0.28, 0.18, 0.16, 0.18]
                )

                match_type = match_cols[0].selectbox(
                    "Tipo",
                    ["Official Match", "Friendly Match"],
                    index=(
                        0
                        if match_activity.get("type")
                        == "Official Match"
                        else 1
                    ),
                )

                opponent = match_cols[1].text_input(
                    "Avversario",
                    value=str(
                        match_activity.get(
                            "opponent",
                            "",
                        )
                    ),
                )

                location = match_cols[2].selectbox(
                    "Sede",
                    ["Home", "Away", "Neutral"],
                    index=(
                        ["Home", "Away", "Neutral"].index(
                            match_activity.get(
                                "location",
                                "Home",
                            )
                        )
                        if match_activity.get(
                            "location",
                            "Home",
                        )
                        in ["Home", "Away", "Neutral"]
                        else 0
                    ),
                )

                kick_off = match_cols[3].text_input(
                    "Kick-off",
                    value=str(
                        match_activity.get(
                            "start_time",
                            "",
                        )
                    ),
                    placeholder="20:45",
                )

                competition = match_cols[4].text_input(
                    "Competizione",
                    value=str(
                        match_activity.get(
                            "competition",
                            "",
                        )
                    ),
                )

                match_players = st.multiselect(
                    "Giocatori convocati / partecipanti",
                    all_planner_players,
                    default=[
                        player
                        for player in match_activity.get(
                            "participants",
                            all_planner_players,
                        )
                        if player in all_planner_players
                    ],
                )

                match_notes = st.text_area(
                    "Note",
                    value=str(
                        match_activity.get(
                            "notes",
                            "",
                        )
                    ),
                )

                save_match = st.form_submit_button(
                    "Salva partita",
                    type="primary",
                    use_container_width=True,
                )

            if save_match:
                venue_code = {
                    "Home": "H",
                    "Away": "A",
                    "Neutral": "N",
                }.get(location, "N")

                title = (
                    f"{opponent.strip().upper()} ({venue_code})"
                    if opponent.strip()
                    else f"MATCH ({venue_code})"
                )

                planner_store["days"][
                    selected_date_key
                ] = {
                    **day_payload,
                    "day_type": "Match",
                    "activities": [
                        {
                            "type": match_type,
                            "title": title,
                            "opponent": opponent,
                            "location": location,
                            "competition": competition,
                            "start_time": kick_off,
                            "notes": match_notes,
                            "participants": match_players,
                            "drills": [],
                        }
                    ],
                    "participants": match_players,
                }

                save_planner_store(
                    base_dir,
                    planner_store,
                )
                st.success("Partita salvata.")
                st.rerun()

        # -------------------------------------------------
        # TRAINING DAY
        # -------------------------------------------------
        else:
            st.subheader("🏋️ Allenamento")

            top_info_cols = st.columns([0.28, 0.18, 0.54])

            training_title = top_info_cols[0].text_input(
                "Titolo giornata",
                value=str(
                    day_payload.get("title", "")
                ),
                placeholder="Es. MD-4",
            )

            match_day = top_info_cols[1].text_input(
                "Match Day",
                value=str(
                    day_payload.get("match_day", "")
                ),
                placeholder="MD-4",
            )

            general_notes = top_info_cols[2].text_input(
                "Note generali",
                value=str(
                    day_payload.get(
                        "general_notes",
                        "",
                    )
                ),
            )

            # ---------------------------------------------
            # PLAYER STATUS - COMPACT
            # ---------------------------------------------
            st.markdown("### Stato giocatori")

            stored_statuses = day_payload.get(
                "player_statuses",
                {},
            )

            stored_notes = day_payload.get(
                "player_notes",
                {},
            )

            player_status_rows = [
                {
                    "Player": player,
                    "Status": stored_statuses.get(
                        player,
                        "Full Training",
                    ),
                    "Note": stored_notes.get(
                        player,
                        "",
                    ),
                }
                for player in all_planner_players
            ]

            status_frame = pd.DataFrame(
                player_status_rows
            )

            status_counts = (
                status_frame["Status"]
                .value_counts()
                .to_dict()
            )

            status_metric_cols = st.columns(4)

            for index, status_name in enumerate(
                [
                    "Full Training",
                    "Different Training",
                    "Return to Play",
                    "Not Available",
                ]
            ):
                status_metric_cols[index].metric(
                    status_name,
                    int(
                        status_counts.get(
                            status_name,
                            0,
                        )
                    ),
                )

            with st.expander(
                "Gestisci stato giocatori",
                expanded=False,
            ):
                status_editor = st.data_editor(
                    status_frame,
                    use_container_width=True,
                    hide_index=True,
                    disabled=["Player"],
                    key=(
                        f"planner_status_"
                        f"{selected_date_key}"
                    ),
                    column_config={
                        "Player": (
                            st.column_config.TextColumn(
                                "Player"
                            )
                        ),
                        "Status": (
                            st.column_config.SelectboxColumn(
                                "Status",
                                options=(
                                    PLANNER_PLAYER_STATUSES
                                ),
                                required=True,
                            )
                        ),
                        "Note": (
                            st.column_config.TextColumn(
                                "Note",
                                max_chars=120,
                            )
                        ),
                    },
                )

            player_statuses = dict(
                zip(
                    status_editor["Player"],
                    status_editor["Status"],
                )
            )

            player_notes = dict(
                zip(
                    status_editor["Player"],
                    status_editor["Note"],
                )
            )

            eligible_players = [
                player
                for player in all_planner_players
                if player_statuses.get(player)
                not in {
                    "Not Available",
                    "National Team",
                    "Rest",
                }
            ]

            field_default_players = [
                player
                for player in all_planner_players
                if player_statuses.get(player)
                in {
                    "Full Training",
                    "Different Training",
                }
            ]

            st.divider()

            # ---------------------------------------------
            # QUICK ADD ACTIVITY
            # ---------------------------------------------
            st.markdown("### Aggiungi attività")

            quick_add_cols = st.columns(6)

            quick_activity_types = [
                "Field Session",
                "Gym Session",
                "Pre-Activation",
                "Video Analysis",
                "Recovery",
                "Other",
            ]

            activity_added = None

            for index, activity_name in enumerate(
                quick_activity_types
            ):
                if quick_add_cols[index].button(
                    activity_name,
                    use_container_width=True,
                    key=(
                        f"planner_quick_add_"
                        f"{selected_date_key}_"
                        f"{activity_name}"
                    ),
                ):
                    activity_added = activity_name

            if activity_added:
                default_activity_players = (
                    field_default_players
                    if activity_added in {
                        "Field Session",
                        "Pre-Activation",
                    }
                    else eligible_players
                )

                activities.append(
                    {
                        "type": activity_added,
                        "title": "",
                        "start_time": "",
                        "duration": 0,
                        "notes": "",
                        "participants": list(
                            default_activity_players
                        ),
                        "drills": [],
                        "attachment": None,
                    }
                )

                planner_store["days"][
                    selected_date_key
                ] = {
                    **day_payload,
                    "day_type": "Training",
                    "title": training_title,
                    "match_day": match_day,
                    "general_notes": general_notes,
                    "activities": sort_planner_activities(activities),
                    "participants": eligible_players,
                    "player_statuses": player_statuses,
                    "player_notes": player_notes,
                }

                save_planner_store(
                    base_dir,
                    planner_store,
                )
                st.rerun()

            st.divider()
            st.markdown("### Programma della giornata")

            if not activities:
                st.info(
                    "Aggiungi la prima attività usando i pulsanti sopra."
                )

            activities = sort_planner_activities(
                activities
            )

            for activity_index, activity in enumerate(
                activities
            ):
                activity_type = activity.get(
                    "type",
                    "Other",
                )

                activity_color = (
                    PLANNER_ACTIVITY_COLORS.get(
                        activity_type,
                        "#8A98A8",
                    )
                )

                total_minutes = (
                    sum(
                        int(
                            drill.get(
                                "duration",
                                0,
                            )
                            or 0
                        )
                        for drill in activity.get(
                            "drills",
                            [],
                        )
                    )
                    if activity_type
                    in PLANNER_EXERCISE_ACTIVITY_TYPES
                    else int(
                        activity.get(
                            "duration",
                            0,
                        )
                        or 0
                    )
                )

                activity_label = (
                    f"{activity_type}"
                    f" · {activity.get('start_time', '') or 'orario N/D'}"
                    f" · {total_minutes} min"
                )

                with st.expander(
                    activity_label,
                    expanded=True,
                ):
                    activity_header_cols = st.columns(
                        [0.30, 0.18, 0.14, 0.20, 0.18]
                    )

                    activity_title = (
                        activity_header_cols[0].text_input(
                            "Titolo",
                            value=str(
                                activity.get(
                                    "title",
                                    "",
                                )
                            ),
                            key=(
                                f"planner_activity_title_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                        )
                    )

                    activity_time = (
                        activity_header_cols[1].text_input(
                            "Orario",
                            value=str(
                                activity.get(
                                    "start_time",
                                    "",
                                )
                            ),
                            key=(
                                f"planner_activity_time_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                        )
                    )

                    activity_duration = (
                        activity_header_cols[2].number_input(
                            "Durata",
                            min_value=0,
                            max_value=240,
                            value=int(
                                activity.get(
                                    "duration",
                                    0,
                                )
                                or 0
                            ),
                            step=1,
                            disabled=(
                                activity_type
                                in PLANNER_EXERCISE_ACTIVITY_TYPES
                            ),
                            key=(
                                f"planner_activity_duration_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                        )
                    )

                    participants_label = (
                        f"{len(activity.get('participants', []))} player"
                    )

                    activity_header_cols[3].metric(
                        "Partecipanti",
                        participants_label,
                    )

                    delete_activity = (
                        activity_header_cols[4].button(
                            "Elimina",
                            use_container_width=True,
                            key=(
                                f"planner_delete_activity_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                        )
                    )

                    activity_default_pool = (
                        field_default_players
                        if activity_type in {
                            "Field Session",
                            "Pre-Activation",
                        }
                        else eligible_players
                    )

                    with st.expander(
                        "Modifica partecipanti",
                        expanded=False,
                    ):
                        activity_participants = st.multiselect(
                            "Partecipanti",
                            eligible_players,
                            default=[
                                player
                                for player in activity.get(
                                    "participants",
                                    activity_default_pool,
                                )
                                if player in eligible_players
                            ],
                            key=(
                                f"planner_activity_players_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                        )

                    activity_notes = st.text_input(
                        "Note attività",
                        value=str(
                            activity.get(
                                "notes",
                                "",
                            )
                        ),
                        key=(
                            f"planner_activity_notes_"
                            f"{selected_date_key}_"
                            f"{activity_index}"
                        ),
                    )

                    existing_attachment = activity.get(
                        "attachment"
                    )

                    with st.expander(
                        "Allegato attività",
                        expanded=False,
                    ):
                        uploaded_attachment = st.file_uploader(
                            "Carica scheda, note o documento",
                            type=[
                                "pdf",
                                "doc",
                                "docx",
                                "xls",
                                "xlsx",
                                "ppt",
                                "pptx",
                                "txt",
                                "csv",
                                "jpg",
                                "jpeg",
                                "png",
                            ],
                            key=(
                                f"planner_attachment_"
                                f"{selected_date_key}_"
                                f"{activity_index}"
                            ),
                            help=(
                                "L'allegato viene salvato nel Planner. "
                                "Per mantenere l'app veloce, usa file "
                                "preferibilmente inferiori a 5 MB."
                            ),
                        )

                        remove_attachment = False

                        if existing_attachment:
                            st.caption(
                                "Allegato presente: "
                                + str(
                                    existing_attachment.get(
                                        "name",
                                        "file",
                                    )
                                )
                            )

                            try:
                                attachment_bytes = base64.b64decode(
                                    existing_attachment.get(
                                        "data",
                                        "",
                                    )
                                )
                                st.download_button(
                                    "Scarica allegato",
                                    data=attachment_bytes,
                                    file_name=str(
                                        existing_attachment.get(
                                            "name",
                                            "allegato",
                                        )
                                    ),
                                    mime=str(
                                        existing_attachment.get(
                                            "mime",
                                            "application/octet-stream",
                                        )
                                    ),
                                    key=(
                                        f"planner_download_attachment_"
                                        f"{selected_date_key}_"
                                        f"{activity_index}"
                                    ),
                                    use_container_width=True,
                                )
                            except Exception:
                                st.warning(
                                    "L'allegato salvato non è leggibile."
                                )

                            remove_attachment = st.checkbox(
                                "Rimuovi allegato",
                                key=(
                                    f"planner_remove_attachment_"
                                    f"{selected_date_key}_"
                                    f"{activity_index}"
                                ),
                            )

                    attachment_payload = existing_attachment

                    if remove_attachment:
                        attachment_payload = None

                    if uploaded_attachment is not None:
                        uploaded_bytes = (
                            uploaded_attachment.getvalue()
                        )

                        if len(uploaded_bytes) > 5 * 1024 * 1024:
                            st.warning(
                                "Allegato superiore a 5 MB: "
                                "potrebbe rallentare il Planner."
                            )

                        attachment_payload = {
                            "name": uploaded_attachment.name,
                            "mime": uploaded_attachment.type
                            or "application/octet-stream",
                            "data": base64.b64encode(
                                uploaded_bytes
                            ).decode("ascii"),
                        }

                    updated_activity = {
                        **activity,
                        "title": activity_title,
                        "start_time": activity_time,
                        "duration": int(
                            activity_duration
                        ),
                        "participants": (
                            activity_participants
                        ),
                        "notes": activity_notes,
                        "attachment": attachment_payload,
                    }

                    if (
                        activity_type
                        in PLANNER_EXERCISE_ACTIVITY_TYPES
                    ):
                        item_label = planner_activity_item_label(
                            activity_type
                        )
                        section_title = (
                            "Esercitazioni"
                            if activity_type == "Field Session"
                            else "Esercizi"
                        )
                        st.markdown(
                            f"#### {section_title}"
                        )

                        drills = list(
                            activity.get(
                                "drills",
                                [],
                            )
                        )

                        drill_rows = []

                        for drill in drills:
                            drill_rows.append(
                                {
                                    item_label: (
                                        drill.get(
                                            "name",
                                            "",
                                        )
                                    ),
                                    "Minuti": int(
                                        drill.get(
                                            "duration",
                                            0,
                                        )
                                        or 0
                                    ),
                                    "Partecipanti": len(
                                        drill.get(
                                            "participants",
                                            [],
                                        )
                                    ),
                                }
                            )

                        if drill_rows:
                            st.dataframe(
                                pd.DataFrame(
                                    drill_rows
                                ),
                                use_container_width=True,
                                hide_index=True,
                            )

                        drill_add_cols = st.columns(
                            [0.46, 0.16, 0.38]
                        )

                        selected_drill_name = (
                            drill_add_cols[0].selectbox(
                                item_label,
                                [
                                    "Custom",
                                    *all_drill_names,
                                ],
                                key=(
                                    f"planner_new_drill_name_"
                                    f"{selected_date_key}_"
                                    f"{activity_index}"
                                ),
                            )
                        )

                        custom_drill_name = ""
                        custom_exercise_category = "Other"
                        save_custom_to_library = False

                        if selected_drill_name == "Custom":
                            custom_drill_name = (
                                drill_add_cols[0].text_input(
                                    "Nome personalizzato",
                                    key=(
                                        f"planner_custom_drill_"
                                        f"{selected_date_key}_"
                                        f"{activity_index}"
                                    ),
                                )
                            )

                            custom_library_cols = st.columns(
                                [0.50, 0.50]
                            )
                            custom_exercise_category = (
                                custom_library_cols[0].selectbox(
                                    "Categoria",
                                    PLANNER_EXERCISE_CATEGORIES,
                                    index=(
                                        PLANNER_EXERCISE_CATEGORIES.index(
                                            "Other"
                                        )
                                    ),
                                    key=(
                                        f"planner_custom_category_"
                                        f"{selected_date_key}_"
                                        f"{activity_index}"
                                    ),
                                )
                            )
                            save_custom_to_library = (
                                custom_library_cols[1].checkbox(
                                    "Aggiungi alla libreria",
                                    value=True,
                                    key=(
                                        f"planner_save_custom_library_"
                                        f"{selected_date_key}_"
                                        f"{activity_index}"
                                    ),
                                )
                            )

                        new_drill_minutes = (
                            drill_add_cols[1].number_input(
                                "Minuti",
                                min_value=0,
                                max_value=180,
                                value=0,
                                step=1,
                                key=(
                                    f"planner_new_drill_minutes_"
                                    f"{selected_date_key}_"
                                    f"{activity_index}"
                                ),
                            )
                        )

                        add_drill = (
                            drill_add_cols[2].button(
                                f"Aggiungi {item_label.lower()}",
                                use_container_width=True,
                                key=(
                                    f"planner_add_drill_"
                                    f"{selected_date_key}_"
                                    f"{activity_index}"
                                ),
                            )
                        )

                        if add_drill:
                            final_drill_name = (
                                custom_drill_name
                                if selected_drill_name
                                == "Custom"
                                else selected_drill_name
                            )

                            if final_drill_name:
                                if (
                                    selected_drill_name == "Custom"
                                    and save_custom_to_library
                                ):
                                    planner_store.setdefault(
                                        "exercise_library",
                                        {},
                                    )[final_drill_name] = {
                                        "category": (
                                            custom_exercise_category
                                        ),
                                        "activity_types": [
                                            activity_type
                                        ],
                                    }

                                drills.append(
                                    {
                                        "name": final_drill_name,
                                        "category": (
                                            custom_exercise_category
                                            if selected_drill_name
                                            == "Custom"
                                            else planner_store.get(
                                                "exercise_library",
                                                {},
                                            ).get(
                                                final_drill_name,
                                                {},
                                            ).get(
                                                "category",
                                                "",
                                            )
                                        ),
                                        "duration": int(
                                            new_drill_minutes
                                        ),
                                        "participants": list(
                                            activity_participants
                                        ),
                                    }
                                )

                                updated_activity[
                                    "drills"
                                ] = drills

                                activities[
                                    activity_index
                                ] = updated_activity

                                planner_store["days"][
                                    selected_date_key
                                ] = {
                                    **day_payload,
                                    "day_type": "Training",
                                    "title": training_title,
                                    "match_day": match_day,
                                    "general_notes": general_notes,
                                    "activities": sort_planner_activities(activities),
                                    "participants": eligible_players,
                                    "player_statuses": player_statuses,
                                    "player_notes": player_notes,
                                }

                                save_planner_store(
                                    base_dir,
                                    planner_store,
                                )
                                st.rerun()

                        if drills:
                            remove_drill_index = (
                                st.selectbox(
                                    f"{item_label} da eliminare",
                                    options=list(
                                        range(
                                            len(drills)
                                        )
                                    ),
                                    format_func=lambda idx: (
                                        f"{idx + 1}. "
                                        f"{drills[idx].get('name', '')}"
                                    ),
                                    key=(
                                        f"planner_remove_drill_"
                                        f"{selected_date_key}_"
                                        f"{activity_index}"
                                    ),
                                )
                            )

                            if st.button(
                                f"Elimina {item_label.lower()} selezionato",
                                use_container_width=True,
                                key=(
                                    f"planner_delete_drill_"
                                    f"{selected_date_key}_"
                                    f"{activity_index}"
                                ),
                            ):
                                drills.pop(
                                    remove_drill_index
                                )

                                updated_activity[
                                    "drills"
                                ] = drills

                                activities[
                                    activity_index
                                ] = updated_activity

                                planner_store["days"][
                                    selected_date_key
                                ] = {
                                    **day_payload,
                                    "day_type": "Training",
                                    "title": training_title,
                                    "match_day": match_day,
                                    "general_notes": general_notes,
                                    "activities": sort_planner_activities(activities),
                                    "participants": eligible_players,
                                    "player_statuses": player_statuses,
                                    "player_notes": player_notes,
                                }

                                save_planner_store(
                                    base_dir,
                                    planner_store,
                                )
                                st.rerun()

                    activities[activity_index] = (
                        updated_activity
                    )

                    if delete_activity:
                        activities.pop(
                            activity_index
                        )

                        planner_store["days"][
                            selected_date_key
                        ] = {
                            **day_payload,
                            "day_type": "Training",
                            "title": training_title,
                            "match_day": match_day,
                            "general_notes": general_notes,
                            "activities": sort_planner_activities(activities),
                            "participants": eligible_players,
                            "player_statuses": player_statuses,
                            "player_notes": player_notes,
                        }

                        save_planner_store(
                            base_dir,
                            planner_store,
                        )
                        st.rerun()

            st.divider()

            save_cols = st.columns([0.34, 0.22, 0.22, 0.22])

            if save_cols[0].button(
                "Salva giornata",
                type="primary",
                use_container_width=True,
            ):
                planner_store["days"][
                    selected_date_key
                ] = {
                    **day_payload,
                    "day_type": "Training",
                    "title": training_title,
                    "match_day": match_day,
                    "general_notes": general_notes,
                    "activities": sort_planner_activities(activities),
                    "participants": eligible_players,
                    "player_statuses": player_statuses,
                    "player_notes": player_notes,
                }

                save_planner_store(
                    base_dir,
                    planner_store,
                )
                st.success("Giornata salvata.")

            if save_cols[1].button(
                "Duplica",
                use_container_width=True,
            ):
                next_key = (
                    selected_date
                    + pd.Timedelta(days=1)
                ).strftime("%Y-%m-%d")

                planner_store["days"][
                    next_key
                ] = json.loads(
                    json.dumps(
                        planner_store["days"][
                            selected_date_key
                        ]
                    )
                )

                save_planner_store(
                    base_dir,
                    planner_store,
                )

                st.session_state[
                    "planner_selected_date"
                ] = next_key

                st.rerun()

            if save_cols[2].button(
                "Salva template",
                use_container_width=True,
            ):
                st.session_state[
                    "planner_show_template_name"
                ] = True

            if save_cols[3].button(
                "PDF",
                use_container_width=True,
            ):
                st.session_state[
                    "daily_planner_pdf"
                ] = (
                    build_daily_planner_report_pdf(
                        planner_date=(
                            selected_date.strftime(
                                "%d/%m/%Y"
                            )
                        ),
                        day_payload=(
                            planner_store["days"].get(
                                selected_date_key,
                                {},
                            )
                        ),
                        activity_colors=(
                            PLANNER_ACTIVITY_COLORS
                        ),
                    )
                )

            if st.session_state.get(
                "planner_show_template_name"
            ):
                template_cols = st.columns(
                    [0.72, 0.28]
                )

                template_name = template_cols[
                    0
                ].text_input(
                    "Nome template",
                    placeholder="Es. MD-4 Standard",
                )

                if template_cols[1].button(
                    "Conferma template",
                    use_container_width=True,
                ):
                    if template_name:
                        planner_store[
                            "templates"
                        ][template_name] = json.loads(
                            json.dumps(
                                planner_store[
                                    "days"
                                ].get(
                                    selected_date_key,
                                    {},
                                )
                            )
                        )

                        save_planner_store(
                            base_dir,
                            planner_store,
                        )

                        st.session_state[
                            "planner_show_template_name"
                        ] = False

                        st.success(
                            "Template salvato."
                        )

            if st.session_state.get(
                "daily_planner_pdf"
            ):
                st.download_button(
                    "Scarica Planner PDF",
                    data=st.session_state[
                        "daily_planner_pdf"
                    ],
                    file_name=(
                        f"Planner_"
                        f"{selected_date.strftime('%Y%m%d')}.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                )

        st.divider()

        if st.button(
            "Elimina giornata",
            use_container_width=True,
        ):
            planner_store["days"].pop(
                selected_date_key,
                None,
            )

            save_planner_store(
                base_dir,
                planner_store,
            )

            st.session_state[
                "planner_view"
            ] = "calendar"

            st.rerun()

        with st.expander(
            "Backup Planner",
            expanded=False,
        ):
            planner_json_bytes = json.dumps(
                planner_store,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")

            backup_cols = st.columns(2)

            backup_cols[0].download_button(
                "Esporta Planner JSON",
                data=planner_json_bytes,
                file_name="planner_backup.json",
                mime="application/json",
                use_container_width=True,
            )

            imported_planner = backup_cols[
                1
            ].file_uploader(
                "Importa backup JSON",
                type=["json"],
                key="planner_backup_upload",
            )

            if imported_planner is not None:
                if st.button(
                    "Conferma importazione",
                    use_container_width=True,
                ):
                    try:
                        imported_payload = json.loads(
                            imported_planner
                            .getvalue()
                            .decode("utf-8")
                        )

                        if not isinstance(
                            imported_payload.get(
                                "days"
                            ),
                            dict,
                        ):
                            raise ValueError(
                                "Sezione days non valida."
                            )

                        imported_payload.setdefault(
                            "templates",
                            {},
                        )

                        save_planner_store(
                            base_dir,
                            imported_payload,
                        )

                        st.success(
                            "Planner importato."
                        )

                        st.rerun()

                    except Exception as exc:
                        st.error(
                            f"Backup non valido: {exc}"
                        )

    st.stop()


if page == "🔮 Forecast":
    st.title("🔮 Forecast")
    st.caption(
        "Build a forecast session by selecting the role, "
        "the drills and their expected duration."
    )

    forecast_roles = sorted(
        forecast_exercises_avg["Role"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not forecast_roles:
        st.error(
            "No roles are available in the "
            "'Esercitazioni Avg' worksheet."
        )
        st.stop()

    forecast_role = st.sidebar.selectbox(
        "Forecast role",
        forecast_roles,
        index=(
            forecast_roles.index("Team Average")
            if "Team Average" in forecast_roles
            else 0
        ),
        key="forecast_role",
    )

    forecast_drills = sorted(
        forecast_exercises_avg.loc[
            forecast_exercises_avg["Role"].eq(forecast_role),
            "Drill",
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    if not forecast_drills:
        st.warning(
            "No drills are available for the selected role."
        )
        st.stop()

    st.subheader("Session Builder")
    st.caption(
        "Each row is updated immediately. Changing the role "
        "refreshes the available drill list."
    )

    forecast_row_count = st.number_input(
        "Number of drills",
        min_value=1,
        max_value=12,
        value=8,
        step=1,
        key="forecast_row_count",
    )

    plan_rows = []

    header_cols = st.columns([0.10, 0.62, 0.28])
    header_cols[0].markdown("**#**")
    header_cols[1].markdown("**Drill**")
    header_cols[2].markdown("**Duration (min)**")

    for row_index in range(int(forecast_row_count)):
        row_cols = st.columns([0.10, 0.62, 0.28])
        row_cols[0].markdown(
            f"<div style='padding-top:0.55rem;"
            f"font-weight:800;'>{row_index + 1}</div>",
            unsafe_allow_html=True,
        )

        drill_value = row_cols[1].selectbox(
            f"Drill {row_index + 1}",
            ["—", *forecast_drills],
            index=0,
            key=(
                f"forecast_drill_{forecast_role}_"
                f"{row_index}"
            ),
            label_visibility="collapsed",
        )

        duration_value = row_cols[2].number_input(
            f"Duration {row_index + 1}",
            min_value=0,
            max_value=120,
            value=0,
            step=1,
            key=(
                f"forecast_duration_{forecast_role}_"
                f"{row_index}"
            ),
            label_visibility="collapsed",
        )

        plan_rows.append(
            {
                "Drill": drill_value,
                "Duration (min)": duration_value,
            }
        )

    forecast_plan = pd.DataFrame(plan_rows)

    forecast_result = forecast_calculation(
        forecast_plan,
        forecast_exercises_avg,
        forecast_role,
    )

    if forecast_result.empty:
        st.info(
            "Select at least one drill and enter a "
            "duration greater than zero."
        )
        st.stop()

    forecast_display = forecast_result.copy()
    for metric_name, meta in FORECAST_METRICS.items():
        forecast_display[metric_name] = (
            forecast_display[metric_name]
            .round(meta["decimals"])
        )
    forecast_display["Duration (min)"] = (
        forecast_display["Duration (min)"]
        .round(0)
        .astype(int)
    )

    total_row = {
        "Drill": "TOTAL",
        "Duration (min)": int(
            forecast_result["Duration (min)"].sum()
        ),
    }
    for metric_name in FORECAST_METRICS:
        total_row[metric_name] = float(
            forecast_result[metric_name].sum()
        )

    forecast_with_total = pd.concat(
        [
            forecast_display,
            pd.DataFrame([total_row]),
        ],
        ignore_index=True,
    )

    st.subheader("Forecast Session")
    st.dataframe(
        forecast_with_total,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Duration (min)": st.column_config.NumberColumn(
                "Duration",
                format="%d min",
            ),
            "Distance (m)": st.column_config.NumberColumn(
                "Distance",
                format="%.0f m",
            ),
            "Acc Events (n°)": st.column_config.NumberColumn(
                "ACC",
                format="%.0f",
            ),
            "Dec Events (n°)": st.column_config.NumberColumn(
                "DEC",
                format="%.0f",
            ),
            "Distance 19.8-25.2 km/h (m)": st.column_config.NumberColumn(
                "Z3",
                format="%.0f m",
            ),
            "Distance >25.2 km/h (m)": st.column_config.NumberColumn(
                "Z4",
                format="%.0f m",
            ),
            "Speed Events (n°)": (
                st.column_config.NumberColumn(
                    "Speed Events",
                    format="%.0f",
                )
            ),
        },
    )

    st.subheader("Forecast Totals")
    total_columns = st.columns(3)
    all_total_metrics = [
        "Distance (m)",
        "Acc Events (n°)",
        "Dec Events (n°)",
        "Distance 19.8-25.2 km/h (m)",
        "Distance >25.2 km/h (m)",
        "Speed Events (n°)",
    ]
    for idx, metric_name in enumerate(
        all_total_metrics
    ):
        total_value = total_row[metric_name]
        unit = FORECAST_METRICS[
            metric_name
        ]["unit"]
        total_columns[idx % 3].metric(
            metric_name,
            (
                f"{total_value:.0f} {unit}"
                if unit
                else f"{total_value:.0f}"
            ),
        )

    st.subheader("Load by Drill")
    for metric_name in all_total_metrics:
        st.markdown(
            f'<div class="pas-section-title">'
            f'{metric_name}</div>',
            unsafe_allow_html=True,
        )
        figure = forecast_metric_chart(
            forecast_result,
            metric_name,
        )
        st.plotly_chart(
            figure,
            use_container_width=True,
            key=f"forecast_{metric_name}",
        )

    st.divider()
    st.subheader("Forecast Session Report PDF")

    forecast_report_date = st.date_input(
        "Report date",
        value=pd.Timestamp.today().date(),
        format="DD/MM/YYYY",
        key="forecast_report_date",
    )

    forecast_report_title = st.text_input(
        "Report title",
        value="FORECAST SESSION REPORT",
        key="forecast_report_title",
    )

    if st.button(
        "Generate Forecast Session Report PDF",
        type="primary",
        use_container_width=True,
    ):
        with pas_loader(
            "Creating Forecast Session Report..."
        ):
            st.session_state[
                "forecast_report_pdf"
            ] = build_forecast_report_pdf(
                forecast_data=forecast_result,
                report_title=forecast_report_title,
                role=forecast_role,
                report_date=pd.Timestamp(
                    forecast_report_date
                ).strftime("%d/%m/%Y"),
                metric_specs=FORECAST_METRICS,
            )

    if st.session_state.get(
        "forecast_report_pdf"
    ):
        st.download_button(
            "Download / print Forecast Report",
            data=st.session_state[
                "forecast_report_pdf"
            ],
            file_name="Forecast_Session_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.stop()


if page == "🧩 Drills":
    st.title("🧩 Drills")
    st.caption(
        "Compare the historical distribution of drills "
        "using values normalised per minute."
    )

    drill_roles = [
        "Team Average",
        *sorted(
            role
            for role in exercises_raw["Role"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
            if role not in {"N/D", "#N/A", "Team Average"}
        ),
    ]

    drill_analysis_mode = st.sidebar.radio(
        "Analysis by",
        ["Roles", "Players"],
        key="drills_analysis_mode",
    )

    drill_source = exercises_raw.copy()
    intelligence_cycles = st.session_state.get("drills_intelligence_cycles", [])
    if intelligence_cycles and "Cycle" in drill_source.columns:
        drill_source = drill_source[drill_source["Cycle"].astype(str).isin(intelligence_cycles)].copy()
        st.caption("PAS Intelligence · Match Cycle: " + ", ".join(intelligence_cycles))
    drills_intelligence_request = st.session_state.get("drills_intelligence_request")
    requested_statuses = getattr(drills_intelligence_request, "starter_statuses", []) if drills_intelligence_request is not None else []
    if requested_statuses and "Starters / No Starters" in drill_source.columns:
        drill_source = drill_source[drill_source["Starters / No Starters"].astype(str).str.upper().isin(requested_statuses)].copy()

    if drill_analysis_mode == "Roles":
        selected_drill_entities = st.sidebar.multiselect(
            "Roles",
            drill_roles,
            default=["Team Average"],
            key="drills_roles",
            help=(
                "Select one or more roles. Every point represents "
                "one Drill-Date occurrence for that role."
            ),
        )
        entity_label = "Role"
    else:
        available_drill_players = sorted(
            drill_source["Athlete"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )
        player_selection_mode = st.sidebar.radio(
            "Players",
            ["All players", "Selected players"],
            key="drills_player_mode",
        )
        if player_selection_mode == "All players":
            selected_drill_entities = available_drill_players
        else:
            selected_drill_entities = st.sidebar.multiselect(
                "Select players",
                available_drill_players,
                default=available_drill_players[:1],
                key="drills_players",
            )
        entity_label = "Player"

    normalized_available_drills = (
        drill_source["Drill"]
        .dropna()
        .astype(str)
        .str.strip()
        .replace({"Different Traning": "Different Training"})
    )
    available_drills = [
        drill_name
        for drill_name in normalized_available_drills.value_counts().index.tolist()
        if drill_name and drill_name.lower() not in {"nan", "none"}
    ]

    if not available_drills:
        st.warning("Nessun drill disponibile con i filtri correnti.")
        st.stop()

    if not selected_drill_entities:
        st.warning("Select at least one role or player.")
        st.stop()

    default_drills = available_drills[:3]

    selected_drills = st.sidebar.multiselect(
        "Drills",
        available_drills,
        default=default_drills,
        max_selections=10,
        key="drills_selected_v3725",
        help="Puoi confrontare fino a 10 drill, ciascuno con un colore dedicato.",
    )

    selected_drill_metrics = st.sidebar.multiselect(
        "Metrics",
        list(DRILL_ANALYSIS_METRICS.keys()),
        default=list(
            DRILL_ANALYSIS_METRICS.keys()
        ),
        key="drills_metrics",
    )

    if not selected_drills:
        st.warning("Select at least one drill.")
        st.stop()

    if not selected_drill_metrics:
        st.warning("Select at least one metric.")
        st.stop()

    filtered_drill_source = drill_source.copy()
    filtered_drill_source["Drill"] = (
        filtered_drill_source["Drill"]
        .astype(str)
        .str.strip()
        .replace({"Different Traning": "Different Training"})
    )
    filtered_drill_source = filtered_drill_source[
        filtered_drill_source["Drill"].isin(selected_drills)
    ].copy()

    st.subheader("Drill Distributions")
    st.caption(
        "Each point represents one Drill-Date occurrence. "
        "In Roles mode the point is the average of the selected role; "
        "in Players mode it is the selected player's value. "
        "All metrics are expressed per minute."
    )

    drill_report_items = []

    for metric_name in selected_drill_metrics:
        meta = DRILL_ANALYSIS_METRICS[
            metric_name
        ]
        if meta["column"] not in filtered_drill_source.columns:
            st.info(
                f"{metric_name}: dato non disponibile "
                "nel foglio Esercitazioni."
            )
            continue

        st.markdown(
            f'<div class="pas-section-title">'
            f'{metric_name}</div>',
            unsafe_allow_html=True,
        )

        occurrence_data = build_drill_occurrences(
            filtered_drill_source,
            selected_drills,
            metric_name,
            drill_analysis_mode,
            selected_drill_entities,
        )

        figure = drills_boxplot(
            occurrence_data,
            selected_drills,
            selected_drill_entities,
            metric_name,
            entity_label,
            for_report=False,
        )
        st.plotly_chart(
            figure,
            use_container_width=True,
            key=f"drill_box_{metric_name}",
        )

        report_figure = drills_boxplot(
            occurrence_data,
            selected_drills,
            selected_drill_entities,
            metric_name,
            entity_label,
            for_report=True,
        )
        drill_report_items.append(
            {
                "title": metric_name,
                "figure_json": report_figure.to_json(),
            }
        )

    missing_drill_columns = [
        DRILL_ANALYSIS_METRICS[metric_name]["column"]
        for metric_name in selected_drill_metrics
        if (
            DRILL_ANALYSIS_METRICS[metric_name]["column"]
            not in filtered_drill_source.columns
        )
    ]

    if missing_drill_columns:
        st.warning(
            "Some drill metrics are not available in the "
            "'Esercitazioni' worksheet: "
            + ", ".join(sorted(set(missing_drill_columns)))
        )

    st.subheader("Statistical Summary")
    summary_rows = []

    for metric_name in selected_drill_metrics:
        occurrence_data = build_drill_occurrences(
            filtered_drill_source,
            selected_drills,
            metric_name,
            drill_analysis_mode,
            selected_drill_entities,
        )

        if occurrence_data.empty:
            continue

        for (
            drill_name,
            entity_name,
        ), group in occurrence_data.groupby(
            ["Drill", "Entity"]
        ):
            values = group["Metric Value"].dropna()
            if values.empty:
                continue

            summary_rows.append(
                {
                    "Drill": drill_name,
                    entity_label: entity_name,
                    "Metric": metric_name,
                    "Occurrences": int(
                        group["Occurrence"].nunique()
                    ),
                    "Mean": float(values.mean()),
                    "Median": float(values.median()),
                    "SD": float(values.std(ddof=0)),
                    "Min": float(values.min()),
                    "Max": float(values.max()),
                }
            )

    st.dataframe(
        pd.DataFrame(summary_rows),
        use_container_width=True,
        hide_index=True,
    )

    st.divider()
    st.subheader("Drills Analysis Report PDF")
    st.caption("PDF A4 orizzontale pronto per la stampa, con massimo 4 grafici per pagina.")

    drill_pdf_metrics = st.multiselect(
        "Charts to print",
        [
            item["title"]
            for item in drill_report_items
        ],
        default=[
            item["title"]
            for item in drill_report_items
        ],
        key="drill_pdf_metrics",
    )

    selected_drill_pdf_items = [
        item
        for item in drill_report_items
        if item["title"] in drill_pdf_metrics
    ]

    drill_report_title = st.text_input(
        "Report title",
        value=(
            "DRILLS ANALYSIS REPORT - "
            + " / ".join(selected_drill_entities)
        ),
        key="drill_report_title",
    )

    if st.button(
        "Generate Drills Analysis Report PDF",
        type="primary",
        use_container_width=True,
        disabled=not selected_drill_pdf_items,
    ):
        with pas_loader(
            "Creating Drills Analysis Report..."
        ):
            st.session_state[
                "drills_report_pdf"
            ] = build_pdf_report(
                selected_drill_pdf_items,
                drill_report_title,
                [
                    entity_label + "s: " + ", ".join(selected_drill_entities),
                    (
                        "Drills: "
                        + ", ".join(selected_drills)
                    ),
                    (
                        "Analysis mode: "
                        + drill_analysis_mode
                        + ". Each point is one Drill-Date occurrence."
                    ),
                    "All values normalised per minute using the units shown in each metric.",
                ],
            )

    if st.session_state.get(
        "drills_report_pdf"
    ):
        st.download_button(
            "Download / print Drills Report",
            data=st.session_state[
                "drills_report_pdf"
            ],
            file_name="Drills_Analysis_Report.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.stop()


if page in {"⚽ Match Analysis", "🎯 Performance Model"}:
    match_metrics = {
        "Duration (min)": METRICS["Duration (min)"],
        "Distance (m)": METRICS["Distance (m)"],
        "Relative Distance (m/min)": {
            "color": "#577590",
            "column": "avg speed (m/min)",
            "unit": "m/min",
            "aggregation": "mean",
            "accumulation": "mean",
            "decimals": 1,
            "format": "number",
        },
        "MPE Rec Avg Time (s)": {
            "color": "#2A9D8F",
            "column": "MPE rec avg time (s)",
            "unit": "s",
            "aggregation": "mean",
            "accumulation": "mean",
            "decimals": 1,
            "format": "number",
        },
        "Acc Events (n°)": METRICS["Acc Events (n°)"],
        "Dec Events (n°)": METRICS["Dec Events (n°)"],
        "Distance 19.8-25.2 km/h (m)": METRICS[
            "Distance 19.8-25.2 km/h (m)"
        ],
        "Distance >25.2 km/h (m)": METRICS[
            "Distance >25.2 km/h (m)"
        ],
        "High Intensity Running (m)": {
            "color": "#D1495B",
            "column": "high intensity running (m)",
            "unit": "m",
            "aggregation": "sum",
            "accumulation": "sum",
            "decimals": 0,
            "format": "number",
        },
        "Speed Events (n°)": METRICS["Speed Events (n°)"],
        "Max Speed (km/h)": METRICS["Max Speed (km/h)"],
    }

    match_raw = match_source[
        match_source["Drill"].astype(str).str.strip().eq("Match")
    ].copy()
    match_raw["MPE rec avg time (s)"] = pd.to_numeric(
        match_raw.get("MPE rec avg time (s)"),
        errors="coerce",
    )
    match_raw["avg speed (m/min)"] = pd.to_numeric(
        match_raw.get("avg speed (m/min)"),
        errors="coerce",
    )
    match_raw["high intensity running (m)"] = (
        pd.to_numeric(
            match_raw.get("distance/speed Z3 (m)"),
            errors="coerce",
        ).fillna(0)
        + pd.to_numeric(
            match_raw.get("distance/speed Z4 (m)"),
            errors="coerce",
        ).fillna(0)
    )

    match_player_day = aggregate_player_day(match_raw)

    # Metriche specifiche delle partite non gestite dal loader generale.
    match_specific_daily = (
        match_raw.groupby(
            ["Date", "Athlete"],
            as_index=False,
        )
        .agg(
            {
                "avg speed (m/min)": "mean",
                "MPE rec avg time (s)": "mean",
                "high intensity running (m)": "sum",
            }
        )
    )

    match_player_day = match_player_day.merge(
        match_specific_daily,
        on=["Date", "Athlete"],
        how="left",
    )

    performance_model = build_performance_model(
        match_player_day,
        match_metrics,
        min_matches=5,
    )

if page == "🎯 Performance Model":
    st.title("🎯 Performance Model")
    st.caption(
        "Riferimento individuale calcolato esclusivamente sulle partite. "
        "Le metriche di volume/evento sono normalizzate al minuto. "
        "Nelle card vengono proiettate sui 90 minuti e viene mostrato "
        "anche il valore al minuto. "
        "Outlier esclusi oltre ±2 SD; modello consolidato da 5 partite."
    )

    model_player = st.sidebar.selectbox(
        "Giocatore",
        sorted(performance_model["Athlete"].dropna().unique()),
        key="model_player",
    )
    performance_model_metric_options = [
        metric_name
        for metric_name in match_metrics.keys()
        if metric_name != "Duration (min)"
    ]

    model_metrics = st.sidebar.multiselect(
        "Metriche del modello",
        performance_model_metric_options,
        default=performance_model_metric_options,
        key="model_metrics",
    )

    player_model = performance_model[
        performance_model["Athlete"].eq(model_player)
    ]

    if player_model.empty:
        st.warning("Modello non disponibile.")
        st.stop()

    model_row = player_model.iloc[0]

    player_photo = find_player_photo(
        base_dir,
        model_player,
    )

    player_match_rows = match_raw[
        match_raw["Athlete"].astype(str).eq(model_player)
    ].copy()

    player_match_count = int(
        player_match_rows["Date"]
        .dropna()
        .dt.normalize()
        .nunique()
    )

    player_match_labels = (
        player_match_rows[["Date", "Match Day +/-"]]
        .drop_duplicates()
        .sort_values("Date")
        .copy()
    )
    player_match_labels["Match Label"] = (
        player_match_labels["Date"].dt.strftime("%d/%m/%Y")
        + " · "
        + player_match_labels["Match Day +/-"]
        .fillna("MATCH")
        .astype(str)
    )
    player_match_lookup = dict(
        zip(
            player_match_labels["Match Label"],
            player_match_labels["Date"],
        )
    )

    highlighted_match_label = st.sidebar.selectbox(
        "Partita da evidenziare",
        ["Nessuna", *list(player_match_lookup.keys())],
        index=0,
        key="performance_model_highlighted_match",
    )
    highlighted_match_date = (
        None
        if highlighted_match_label == "Nessuna"
        else pd.Timestamp(
            player_match_lookup[highlighted_match_label]
        )
    )

    player_last_match = (
        player_match_rows["Date"].max()
        if not player_match_rows.empty
        else pd.NaT
    )

    player_roles = (
        player_match_rows["Role Clean"]
        .dropna()
        .astype(str)
        if "Role Clean" in player_match_rows.columns
        else pd.Series(dtype="object")
    )
    player_role = (
        player_roles.mode().iloc[0]
        if not player_roles.empty
        else "N/D"
    )

    profile_photo_col, profile_info_col = st.columns(
        [0.28, 0.72],
        gap="large",
    )

    with profile_photo_col:
        if player_photo is not None:
            st.image(
                str(player_photo),
                use_container_width=True,
            )
        else:
            with st.container(border=True):
                st.markdown(
                    "<div style='text-align:center;"
                    "font-size:4rem;padding:2rem 0;'>👤</div>",
                    unsafe_allow_html=True,
                )
                st.caption("Foto non disponibile")

    with profile_info_col:
        st.markdown(
            f"<div style='font-size:2.1rem;"
            f"font-weight:900;line-height:1.05;'>"
            f"{model_player.title()}</div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<div style='font-size:1.05rem;"
            f"color:#B9C6D8;margin-top:0.4rem;'>"
            f"{player_role}</div>",
            unsafe_allow_html=True,
        )

        info_col_1, info_col_2, info_col_3 = st.columns(3)
        info_col_1.metric(
            "Stato modello",
            model_row["Model Status"],
        )
        info_col_2.metric(
            "Partite disponibili",
            player_match_count,
        )
        info_col_3.metric(
            "Ultima partita",
            (
                pd.Timestamp(player_last_match)
                .strftime("%d/%m/%Y")
                if pd.notna(player_last_match)
                else "N/D"
            ),
        )

    st.divider()
    st.subheader("Parametri del modello prestativo")

    cols = st.columns(3)
    for idx, metric_name in enumerate(model_metrics):
        meta = match_metrics[metric_name]
        column = meta["column"]
        with cols[idx % 3]:
            with st.container(border=True):
                st.markdown(f"**{metric_name}**")
                (
                    model_value,
                    model_unit,
                    per_minute_value,
                ) = model_display_value(
                    model_row,
                    metric_name,
                    meta,
                )

                st.caption("AVG")
                st.markdown(
                    f"### {model_value}"
                    + (
                        f" {model_unit}"
                        if model_unit
                        else ""
                    )
                )

                selected_match_value = (
                    performance_model_selected_match_value(
                        player_match_rows,
                        metric_name,
                        meta,
                        highlighted_match_date,
                    )
                )

                if pd.notna(selected_match_value):
                    selected_decimals = int(
                        meta.get("decimals", 0)
                    )
                    selected_display = format(
                        float(selected_match_value),
                        f".{selected_decimals}f",
                    ).replace(".", ",")

                    st.markdown(
                        f"<div style='margin-top:0.35rem;"
                        f"font-size:0.78rem;color:#B9C6D8;'>"
                        f"SELECTED MATCH</div>"
                        f"<div style='font-size:1.1rem;"
                        f"font-weight:800;color:#F4C430;'>"
                        f"{selected_display}"
                        f"{(' ' + model_unit) if model_unit else ''}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

                if per_minute_value is not None:
                    per_minute_unit = (
                        f"{model_unit}/min"
                        if model_unit
                        else "/min"
                    )
                    st.markdown(
                        f"<div style='font-size:0.88rem;"
                        f"color:#B9C6D8;margin-top:-0.35rem;'>"
                        f"{per_minute_value} "
                        f"{per_minute_unit}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(
                        "Valore principale proiettato sui 90'"
                    )

                st.caption(
                    f"Partite valide: "
                    f"{int(model_row.get(f'{column}__n', 0))}"
                )

    st.divider()
    st.subheader("Distribuzione delle partite")
    st.caption(
        "Ogni punto rappresenta una partita, comprese quelle escluse dal calcolo del modello per il filtro ±2 SD. "
        "La partita selezionata nel filtro laterale è evidenziata "
        "in giallo; la linea rossa tratteggiata indica l'AVG. "
        "Le metriche di volume/evento sono confrontate al minuto."
    )

    performance_boxplot_items: list[dict[str, str]] = []

    boxplot_model_metrics = [
        metric_name
        for metric_name in model_metrics
        if metric_name != "Distance (m)"
    ]

    for metric_name in boxplot_model_metrics:
        meta = match_metrics[metric_name]
        column = meta["column"]
        if column not in player_match_rows.columns:
            continue

        st.markdown(
            f'<div class="pas-section-title">{metric_name}</div>',
            unsafe_allow_html=True,
        )

        distribution_figure = performance_model_distribution_chart(
            player_match_rows,
            metric_name,
            meta,
            highlighted_match_date,
            model_row,
        )

        st.plotly_chart(
            distribution_figure,
            use_container_width=True,
            key=f"performance_model_distribution_{model_player}_{metric_name}",
        )

        performance_boxplot_items.append(
            {
                "title": metric_name,
                "figure_json": distribution_figure.to_json(),
            }
        )

    st.divider()
    st.subheader("Report box plot")

    boxplot_report_metrics = st.multiselect(
        "Parametri da stampare",
        [item["title"] for item in performance_boxplot_items],
        default=[item["title"] for item in performance_boxplot_items],
        key="performance_boxplot_report_metrics",
    )

    selected_boxplot_report_items = [
        item
        for item in performance_boxplot_items
        if item["title"] in boxplot_report_metrics
    ]

    boxplot_report_title = st.text_input(
        "Titolo report box plot",
        value=(
            f"PERFORMANCE MODEL REPORT - "
            f"{model_player.title()}"
        ),
        key=(
            f"performance_boxplot_report_title_"
            f"{model_player}"
        ),
    )

    if st.button(
        "Genera report box plot PDF",
        type="primary",
        use_container_width=True,
        disabled=not selected_boxplot_report_items,
    ):
        st.session_state["performance_boxplot_report_pdf"] = build_pdf_report(
            selected_boxplot_report_items,
            boxplot_report_title,
            [
                f"Giocatore selezionato: {model_player.title()}",
                f"Partita selezionata: {highlighted_match_label}",
                "Sono mostrate tutte le partite, comprese quelle escluse dal modello ±2 SD.",
            ],
        )

    if st.session_state.get("performance_boxplot_report_pdf"):
        st.download_button(
            "Scarica report box plot",
            data=st.session_state["performance_boxplot_report_pdf"],
            file_name=f"Performance_Model_Boxplot_{model_player.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

    st.subheader("Modello completo")

    absolute_model_metrics = {
        "Max Speed (km/h)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
    }

    model_table = performance_model[
        ["Athlete", "Model Status"]
    ].copy()

    for name in model_metrics:
        column = match_metrics[name]["column"]

        if name in absolute_model_metrics:
            if column in performance_model.columns:
                model_table[name] = performance_model[column]
            continue

        per_minute_column = f"{column}__per_min"

        if per_minute_column in performance_model.columns:
            model_table[f"{name} / min"] = (
                performance_model[
                    per_minute_column
                ].round(1)
            )
            model_table[f"{name} / 90'"] = (
                performance_model[
                    per_minute_column
                ] * 90
            ).round(
                int(
                    match_metrics[name].get(
                        "decimals",
                        0,
                    )
                )
            )

    st.dataframe(
        model_table,
        use_container_width=True,
        hide_index=True,
    )
    st.stop()

if page == "⚽ Match Analysis":
    st.title("⚽ Match Analysis")
    st.caption(
        "Analisi della singola partita, confronto tra partite "
        "e report con target del modello prestativo individuale."
    )

    match_labels = (
        match_raw[["Date", "Match Day +/-"]]
        .drop_duplicates()
        .sort_values("Date")
        .copy()
    )
    match_labels["Match"] = (
        match_labels["Date"].dt.strftime("%d/%m/%Y")
        + " · "
        + match_labels["Match Day +/-"].fillna("MATCH").astype(str)
    )
    match_lookup = dict(
        zip(match_labels["Match"], match_labels["Date"])
    )

    st.sidebar.markdown("### ⚽ Match Analysis")
    match_analysis_mode = st.sidebar.radio(
        "Vista",
        ["Singola partita", "Confronto / Totali partite"],
        key="match_analysis_mode",
    )

    if match_analysis_mode == "Singola partita":
        st.sidebar.caption("Selezione singola partita")
        selected_match_label = st.sidebar.selectbox(
            "Partita",
            list(match_lookup.keys()),
            index=max(0, len(match_lookup) - 1),
        )
        selected_match_date = pd.Timestamp(
            match_lookup[selected_match_label]
        )
        selected_match_data = match_player_day[
            match_player_day["Date"].dt.normalize().eq(
                selected_match_date.normalize()
            )
        ].copy()

        selected_match_players = st.sidebar.multiselect(
            "Giocatori",
            sorted(selected_match_data["Athlete"].unique()),
            default=sorted(selected_match_data["Athlete"].unique()),
            key=(
                "match_players_"
                + selected_match_date.strftime("%Y%m%d")
            ),
        )
        selected_match_metrics = st.sidebar.multiselect(
            "Metriche",
            list(match_metrics.keys()),
            default=list(match_metrics.keys()),
            key="match_metrics",
        )
        selected_match_data = selected_match_data[
            selected_match_data["Athlete"].isin(selected_match_players)
        ].copy()

        selected_match_targets = build_projected_targets(
            selected_match_data,
            performance_model,
            match_metrics,
        )

        match_historical_max_speed_references = (
            build_historical_max_speed_references(report_source)
        )
        match_max_speed_percentages = (
            build_max_speed_percentage_data(
                selected_match_data,
                match_historical_max_speed_references,
                team_average_mode=False,
            )
        )

        match_average_metrics = {
            "Max Speed (km/h)",
            "Relative Distance (m/min)",
            "MPE Rec Avg Time (s)",
        }

        match_total_row = {"Athlete": "TOTAL MATCH"}
        for metric_name, meta in match_metrics.items():
            column = meta["column"]

            values = safe_numeric_series(
                selected_match_data,
                column,
            ).dropna()

            if values.empty:
                match_total_row[column] = np.nan
            elif metric_name in match_average_metrics:
                match_total_row[column] = float(values.mean())
            else:
                match_total_row[column] = float(values.sum())

        st.subheader("Totale della partita")
        st.caption(
            "Somma dei valori di tutti i giocatori selezionati. "
            "Per Max Speed, Relative Distance e MPE Rec Avg Time "
            "viene mostrata la media dei giocatori."
        )

        match_total_metrics = list(selected_match_metrics)

        if match_total_metrics:
            total_cols = st.columns(4)
            for idx, metric_name in enumerate(match_total_metrics):
                meta = match_metrics[metric_name]
                with total_cols[idx % 4]:
                    st.metric(
                        metric_name,
                        fmt_metric(
                            match_total_row.get(meta["column"]),
                            metric_name,
                        ),
                    )
        else:
            st.info(
                "Nessuna metrica sommabile selezionata "
                "per il totale della partita."
            )

        st.subheader("Giocatori vs modello individuale")
        for metric_name in selected_match_metrics:
            meta = match_metrics[metric_name]
            if meta["column"] not in selected_match_data.columns:
                continue

            st.markdown(
                f'<div class="pas-section-title">'
                f'{metric_name}</div>',
                unsafe_allow_html=True,
            )

            st.plotly_chart(
                match_value_target_chart(
                    selected_match_data,
                    selected_match_targets,
                    metric_name,
                    meta,
                ),
                use_container_width=True,
                key=f"match_target_{metric_name}",
            )

        if st.button(
            "Genera Match Report PDF",
            type="primary",
            use_container_width=True,
        ):
            st.session_state["match_report_pdf"] = (
                build_session_report_pdf(
                    session_data=selected_match_data,
                    selected_metrics=selected_match_metrics,
                    metric_specs=match_metrics,
                    report_title="MATCH REPORT",
                    session_context={
                        "date": selected_match_date.strftime("%d/%m/%Y"),
                        "match_day": selected_match_label,
                        "cycle": "Match",
                        "drill": "Match",
                        "time_of_day": "",
                    },
                    different_training_data=None,
                    target_data=selected_match_targets,
                    target_label="Individual Performance Model",
                    summary_mode="match_total",
                    summary_label="TOTAL MATCH",
                    summary_average_metrics={
                        "Relative Distance (m/min)",
                        "MPE Rec Avg Time (s)",
                        "Max Speed (km/h)",
                    },
                    percentage_data=(
                        match_max_speed_percentages
                    ),
                    percentage_label="",
                    match_header_label=selected_match_label,
                )
            )

        if st.session_state.get("match_report_pdf"):
            st.download_button(
                "Scarica Match Report",
                data=st.session_state["match_report_pdf"],
                file_name=(
                    f"Match_Report_"
                    f"{selected_match_date.strftime('%Y%m%d')}.pdf"
                ),
                mime="application/pdf",
                use_container_width=True,
            )

    else:
        st.sidebar.caption("Confronto e totali partita")
        comparison_matches = st.sidebar.multiselect(
            "Partite da confrontare",
            list(match_lookup.keys()),
            default=list(match_lookup.keys())[-3:],
            key="comparison_matches",
        )

        comparison_subject = st.sidebar.selectbox(
            "Analisi del confronto",
            [
                "Totale partita",
                *sorted(match_player_day["Athlete"].unique()),
            ],
            key="comparison_subject",
            help=(
                "Totale partita somma i valori di tutti i giocatori "
                "presenti nella stessa partita e permette il confronto "
                "con i totali delle altre partite. Non viene utilizzata "
                "alcuna Team Average. Selezionando un atleta vengono "
                "mostrati i suoi valori individuali."
            ),
        )

        comparison_metrics = st.sidebar.multiselect(
            "Metriche",
            list(match_metrics.keys()),
            default=[
                "Duration (min)",
                "Distance (m)",
                "Acc Events (n°)",
                "Dec Events (n°)",
                "High Intensity Running (m)",
                "Speed Events (n°)",
            ],
            key="comparison_metrics",
        )

        non_summable_match_metrics = {
            "Max Speed (km/h)",
            "Relative Distance (m/min)",
            "MPE Rec Avg Time (s)",
        }

        if comparison_subject == "Totale partita":
            st.info(
                "Modalità Totale partita: per ciascun match vengono "
                "sommati i valori di tutti i giocatori presenti. "
                "Il confronto avviene quindi tra i totali complessivi "
                "delle diverse partite, senza utilizzare il Team Average."
            )

        selected_dates = [
            pd.Timestamp(match_lookup[label]).normalize()
            for label in comparison_matches
        ]

        comparison_data = match_player_day[
            match_player_day["Date"].dt.normalize().isin(
                selected_dates
            )
        ].copy()

        if not comparison_matches:
            st.warning("Seleziona almeno una partita.")
        elif not comparison_metrics:
            st.warning("Seleziona almeno una metrica.")
        else:
            comparison_report_rows: list[dict[str, object]] = []
            comparison_target_rows: list[dict[str, object]] = []

            for match_label in comparison_matches:
                match_date = pd.Timestamp(
                    match_lookup[match_label]
                ).normalize()

                match_rows = comparison_data[
                    comparison_data["Date"].dt.normalize().eq(
                        match_date
                    )
                ].copy()

                report_row: dict[str, object] = {
                    "Athlete": match_label,
                }
                target_row: dict[str, object] = {
                    "Athlete": match_label,
                }

                if comparison_subject == "Totale partita":
                    subject_rows = match_rows
                else:
                    subject_rows = match_rows[
                        match_rows["Athlete"].eq(
                            comparison_subject
                        )
                    ].copy()

                for metric_name in comparison_metrics:
                    meta = match_metrics[metric_name]
                    column = meta["column"]

                    values = safe_numeric_series(
                subject_rows,
                column,
            ).dropna()

                    if values.empty:
                        report_value = np.nan
                    elif comparison_subject == "Totale partita":
                        if metric_name in non_summable_match_metrics:
                            report_value = np.nan
                        else:
                            report_value = float(values.sum())
                    elif metric_name == "Max Speed (km/h)":
                        report_value = float(values.max())
                    else:
                        report_value = float(values.mean())

                    report_row[column] = report_value
                    target_row[column] = np.nan

                if (
                    comparison_subject != "Totale partita"
                    and not subject_rows.empty
                ):
                    projected_targets = build_projected_targets(
                        subject_rows,
                        performance_model,
                        match_metrics,
                    )
                    if not projected_targets.empty:
                        projected = projected_targets.iloc[0]
                        for metric_name in comparison_metrics:
                            column = match_metrics[
                                metric_name
                            ]["column"]
                            target_row[column] = projected.get(
                                column
                            )

                comparison_report_rows.append(report_row)
                comparison_target_rows.append(target_row)

            comparison_report_data = pd.DataFrame(
                comparison_report_rows
            )
            comparison_target_data = pd.DataFrame(
                comparison_target_rows
            )

            for metric_name in comparison_metrics:
                if (
                    comparison_subject == "Totale partita"
                    and metric_name in non_summable_match_metrics
                ):
                    st.info(
                        f"{metric_name} esclusa dal Totale partita "
                        "perché non è una metrica sommabile."
                    )
                    continue

                meta = match_metrics[metric_name]
                column = meta["column"]

                st.markdown(
                    f'<div class="pas-section-title">'
                    f'{metric_name}</div>',
                    unsafe_allow_html=True,
                )

                figure = go.Figure(
                    go.Bar(
                        x=comparison_report_data["Athlete"],
                        y=comparison_report_data[column],
                        text=[
                            fmt_metric(value, metric_name)
                            for value in comparison_report_data[
                                column
                            ]
                        ],
                        textposition="outside",
                        marker_color=meta.get("color"),
                        name=(
                            "Totale partita"
                            if comparison_subject
                            == "Totale partita"
                            else comparison_subject
                        ),
                    )
                )

                if comparison_subject != "Totale partita":
                    target_values = pd.to_numeric(
                        comparison_target_data[column],
                        errors="coerce",
                    )
                    if target_values.notna().any():
                        figure.add_trace(
                            go.Scatter(
                                x=comparison_target_data[
                                    "Athlete"
                                ],
                                y=target_values,
                                mode="lines+markers",
                                name="Modello individuale",
                                line=dict(
                                    color="#D62839",
                                    width=2,
                                    dash="dash",
                                ),
                                marker=dict(size=7),
                            )
                        )

                figure.update_layout(
                    xaxis_title="Partita",
                    yaxis_title=meta.get("unit", ""),
                    showlegend=True,
                    margin=dict(
                        l=20,
                        r=30,
                        t=20,
                        b=70,
                    ),
                )

                st.plotly_chart(
                    figure,
                    use_container_width=True,
                    key=(
                        f"comparison_{comparison_subject}_"
                        f"{metric_name}"
                    ),
                )

            st.divider()
            st.subheader("Match Comparison Report PDF")

            reportable_comparison_metrics = [
                metric_name
                for metric_name in comparison_metrics
                if not (
                    comparison_subject == "Totale partita"
                    and metric_name
                    in non_summable_match_metrics
                )
            ]

            comparison_report_title = st.text_input(
                "Titolo report confronto",
                value=(
                    "MATCH TOTALS COMPARISON REPORT"
                    if comparison_subject == "Totale partita"
                    else (
                        f"MATCH COMPARISON REPORT - "
                        f"{comparison_subject}"
                    )
                ),
                key="comparison_report_title",
            )

            if st.button(
                "Genera Match Comparison Report PDF",
                type="primary",
                use_container_width=True,
                disabled=not reportable_comparison_metrics,
            ):
                report_targets = (
                    comparison_target_data
                    if comparison_subject != "Totale partita"
                    else None
                )

                st.session_state[
                    "match_comparison_report_pdf"
                ] = build_session_report_pdf(
                    session_data=comparison_report_data,
                    selected_metrics=reportable_comparison_metrics,
                    metric_specs=match_metrics,
                    report_title=comparison_report_title,
                    session_context={
                        "date": (
                            f"{len(comparison_matches)} partite"
                        ),
                        "match_day": comparison_subject,
                        "cycle": "Confronto partite",
                        "drill": "Match",
                        "time_of_day": "",
                    },
                    different_training_data=None,
                    target_data=report_targets,
                    target_label=(
                        "Individual Performance Model"
                        if report_targets is not None
                        else "No target"
                    ),
                )

            if st.session_state.get(
                "match_comparison_report_pdf"
            ):
                st.download_button(
                    "Scarica Match Comparison Report",
                    data=st.session_state[
                        "match_comparison_report_pdf"
                    ],
                    file_name=(
                        "Match_Totals_Comparison_Report.pdf"
                        if comparison_subject == "Totale partita"
                        else "Match_Player_Comparison_Report.pdf"
                    ),
                    mime="application/pdf",
                    use_container_width=True,
                )

    st.stop()

if page == "👤 Player Profiles":
    st.title("👤 Player Profiles")
    st.info("Struttura predisposta. Questa sarà la prossima sezione sviluppata dopo la Dashboard.")
    st.stop()

if page == "🏥 Return To Play":
    st.title("🏥 Return To Play")
    st.info("Struttura predisposta. La pagina userà Drill = Return to Play e RTP Week.")
    st.stop()

# -------------------------
# FILTRI
# -------------------------
st.sidebar.header("Filtri Dashboard")

available_dates = sorted(raw["Date"].dt.date.unique())
available_dates_set = set(available_dates)

full_training_dates = sorted(
    raw.loc[raw["Drill"].eq("Full Training"), "Date"].dt.date.unique()
)
default_reference_date = (
    full_training_dates[-1] if full_training_dates else available_dates[-1]
)

# ---------------------------------------------------------
# 1. GIORNO DA ANALIZZARE
# ---------------------------------------------------------
st.sidebar.subheader("Seduta")

reference_date = st.sidebar.date_input(
    "Giorno da analizzare",
    value=st.session_state.get("dashboard_reference_date", default_reference_date),
    key="dashboard_reference_date",
    min_value=available_dates[0],
    max_value=available_dates[-1],
    format="DD/MM/YYYY",
    help="Seleziona il giorno dal calendario.",
)

if reference_date not in available_dates_set:
    st.sidebar.warning(
        "La data selezionata non contiene dati nel database. "
        "Scegli un giorno con dati disponibili."
    )
    st.warning(
        f"Nessun dato disponibile per il {reference_date.strftime('%d/%m/%Y')}."
    )
    st.stop()

st.sidebar.caption(
    "Calendario attivo: sono accettate solo le date con dati disponibili."
)

reference_ts = pd.Timestamp(reference_date)

# ---------------------------------------------------------
# 2. DRILL
# ---------------------------------------------------------
day_drills = sorted(
    raw.loc[
        raw["Date"].dt.normalize().eq(reference_ts.normalize()),
        "Drill",
    ]
    .dropna()
    .unique()
)

if not day_drills:
    st.error("Nessun drill disponibile nella data selezionata.")
    st.stop()

default_drill_index = (
    day_drills.index("Full Training")
    if "Full Training" in day_drills
    else 0
)

selected_drill = st.sidebar.selectbox(
    "Drill",
    day_drills,
    index=default_drill_index,
    key="dashboard_selected_drill",
    help="Sono mostrati solo i drill realmente presenti nella data selezionata.",
)

day_selected_raw = raw[
    raw["Date"].dt.normalize().eq(reference_ts.normalize())
    & raw["Drill"].eq(selected_drill)
].copy()
day_selected_player_day = aggregate_player_day(day_selected_raw)

# ---------------------------------------------------------
# 3. PANORAMICA
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Panoramica")

overview_mode = st.sidebar.radio(
    "Panoramica principale",
    ["Team Overview", "Player Overview"],
    horizontal=False,
    key="dashboard_overview_mode",
)

overview_player = None
if overview_mode == "Player Overview":
    all_players = sorted(raw["Athlete"].dropna().unique())
    overview_player = st.sidebar.selectbox(
        "Giocatore della panoramica",
        all_players,
        key="dashboard_overview_player",
    )

overview_metric_names = st.sidebar.multiselect(
    "Metriche della panoramica",
    list(METRICS.keys()),
    default=list(METRICS.keys()),
    key="dashboard_overview_metrics",
)

# ---------------------------------------------------------
# 4. SESSION REPORT
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Session Report")

session_report_title = st.sidebar.text_input(
    "Titolo Session Report",
    value=f"SESSION REPORT {reference_ts.strftime('%d/%m/%Y')}",
)

session_report_metrics = st.sidebar.multiselect(
    "Metriche nel Professional Session Report",
    list(METRICS.keys()),
    default=list(METRICS.keys()),
    help=(
        "Il report utilizza un unico foglio A4 orizzontale "
        "con Team Average, Full Training e Different Training."
    ),
)

session_report_players_mode = st.sidebar.radio(
    "Giocatori nel Session Report",
    ["Tutti i giocatori del giorno", "Solo giocatori selezionati"],
)

session_day_raw = report_source[
    report_source["Date"].dt.normalize().eq(reference_ts.normalize())
].copy()

session_full_training_raw = session_day_raw[
    session_day_raw["Drill"].eq("Full Training")
].copy()

session_different_training_raw = session_day_raw[
    session_day_raw["Drill"].isin(
        ["Different Training", "Different Traning"]
    )
].copy()

session_report_data = aggregate_player_day(
    session_full_training_raw
)
session_report_different_data = aggregate_player_day(
    session_different_training_raw
)

session_report_available_players = sorted(
    set(
        session_report_data["Athlete"]
        .dropna()
        .astype(str)
        .tolist()
    )
    | set(
        session_report_different_data["Athlete"]
        .dropna()
        .astype(str)
        .tolist()
    )
)

session_report_selected_players = session_report_available_players

session_historical_max_speed_references = (
    build_historical_max_speed_references(report_source)
)

if session_report_players_mode == "Solo giocatori selezionati":
    session_report_selected_players = st.sidebar.multiselect(
        "Giocatori da includere nel report",
        session_report_available_players,
        default=session_report_available_players,
    )

    session_report_data = session_report_data[
        session_report_data["Athlete"].isin(
            session_report_selected_players
        )
    ].copy()

    session_report_different_data = (
        session_report_different_data[
            session_report_different_data["Athlete"].isin(
                session_report_selected_players
            )
        ].copy()
    )

session_report_all_players_data = pd.concat(
    [
        session_report_data,
        session_report_different_data,
    ],
    ignore_index=True,
)
session_report_max_speed_percentages = (
    build_max_speed_percentage_data(
        session_report_all_players_data,
        session_historical_max_speed_references,
        team_average_mode=False,
    )
)

day_raw_for_context = pd.concat(
    [
        session_full_training_raw,
        session_different_training_raw,
    ],
    ignore_index=True,
)

time_of_day_mode = (
    day_raw_for_context["Time of Day"].dropna().mode()
    if "Time of Day" in day_raw_for_context.columns
    else pd.Series(dtype="object")
)
time_of_day_value = (
    str(time_of_day_mode.iloc[0])
    if not time_of_day_mode.empty
    else "N/D"
)

if st.sidebar.button(
    "Genera Session Report PDF",
    type="primary",
    use_container_width=True,
    disabled=(
        not session_report_metrics
        or (
            session_report_data.empty
            and session_report_different_data.empty
        )
    ),
):
    report_context = context_for_date(
        raw,
        reference_ts,
    )

    session_context = {
        "date": reference_ts.strftime("%d/%m/%Y"),
        "match_day": str(
            report_context["relative_day"]
        ),
        "cycle": str(
            report_context["cycle"]
        ),
        "drill": "Full Training + Different Training",
        "time_of_day": time_of_day_value,
    }

    with pas_loader("Creazione Session Report..."):
        st.session_state.generated_session_report_pdf = (
            build_session_report_pdf(
                session_data=session_report_data,
                different_training_data=session_report_different_data,
                selected_metrics=session_report_metrics,
                metric_specs=METRICS,
                report_title=session_report_title,
                session_context=session_context,
                percentage_data=(
                    session_report_max_speed_percentages
                ),
                percentage_label="",
            )
        )

if st.session_state.get("generated_session_report_pdf"):
    st.sidebar.download_button(
        "Scarica / stampa Session Report",
        data=st.session_state.generated_session_report_pdf,
        file_name=(
            f"Session_Report_"
            f"{reference_ts.strftime('%Y%m%d')}.pdf"
        ),
        mime="application/pdf",
        use_container_width=True,
    )

# ---------------------------------------------------------
# 5. ACCUMULO CARICO
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Accumulo carico")

accumulation_mode = st.sidebar.radio(
    "Selezione accumulo",
    ["Intervallo di date", "Uno o più Match Cycle"],
    index=1,
    help=(
        "Di default viene selezionato il Match Cycle "
        "corrispondente alla giornata analizzata."
    ),
)

accumulation_default_start = max(
    pd.Timestamp(min(available_dates)),
    reference_ts - timedelta(days=27),
)

if accumulation_mode == "Intervallo di date":
    accumulation_dates = st.sidebar.date_input(
        "Date accumulo",
        value=(
            accumulation_default_start.date(),
            reference_ts.date(),
        ),
        min_value=available_dates[0],
        max_value=available_dates[-1],
        format="DD/MM/YYYY",
    )

    if isinstance(accumulation_dates, tuple) and len(accumulation_dates) == 2:
        accumulation_start = pd.Timestamp(accumulation_dates[0])
        accumulation_end = pd.Timestamp(accumulation_dates[1])
    else:
        accumulation_start = pd.Timestamp(accumulation_dates)
        accumulation_end = pd.Timestamp(accumulation_dates)

    accumulation_base_raw = raw[
        raw["Date"].dt.normalize().between(
            accumulation_start.normalize(),
            accumulation_end.normalize(),
        )
    ].copy()

    accumulation_description = (
        f"{accumulation_start.strftime('%d/%m/%Y')} → "
        f"{accumulation_end.strftime('%d/%m/%Y')}"
    )

else:
    cycle_order = (
        raw[["Cycle", "Date"]]
        .dropna(subset=["Cycle"])
        .groupby("Cycle", as_index=False)["Date"]
        .min()
        .sort_values("Date")
    )
    available_cycles = cycle_order["Cycle"].astype(str).tolist()

    current_cycle = str(context_for_date(raw, reference_ts)["cycle"])
    default_cycles = (
        [current_cycle]
        if current_cycle in available_cycles
        else available_cycles[-1:]
    )

    selected_accumulation_cycles = st.sidebar.multiselect(
        "Match Cycle",
        available_cycles,
        default=default_cycles,
    )

    accumulation_base_raw = raw[
        raw["Cycle"].astype(str).isin(selected_accumulation_cycles)
    ].copy()

    accumulation_description = (
        ", ".join(selected_accumulation_cycles)
        if selected_accumulation_cycles
        else "Nessun ciclo selezionato"
    )

accumulation_drills = {
    "Full Training",
    "Individual Training",
    "Return to Play",
    "Active Recovery",
    "Different Training",
    "Different Traning",
    "Match",
    "Recovery",
}

team_accumulation_drills = accumulation_drills
player_accumulation_drills = accumulation_drills

team_accumulation_raw = accumulation_base_raw[
    accumulation_base_raw["Drill"].isin(team_accumulation_drills)
].copy()

player_accumulation_raw = accumulation_base_raw[
    accumulation_base_raw["Drill"].isin(player_accumulation_drills)
].copy()

team_accumulation_player_day = aggregate_player_day(
    team_accumulation_raw
)
player_accumulation_player_day = aggregate_player_day(
    player_accumulation_raw
)

st.sidebar.caption(
    "Accumulo Dashboard: Full Training, Individual Training, "
    "Return to Play, Active Recovery, Different Training, "
    "Match e Recovery. Tutte le metriche vengono sommate; "
    "Max Speed riporta il valore più alto. "
    "Il filtro Drill della giornata non modifica l'accumulo."
)

# ---------------------------------------------------------
# 6. CONFRONTO GIOCATORI DEL GIORNO
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Confronto giocatori del giorno")

available_players = sorted(
    day_selected_player_day["Athlete"].dropna().unique()
)

selected_players = st.sidebar.multiselect(
    "Giocatori da confrontare",
    available_players,
    default=[],
    key="dashboard_selected_players",
)

day_players_mode = st.sidebar.radio(
    "Giocatori nelle card",
    ["Tutta la squadra", "Solo giocatori selezionati"],
    key="dashboard_day_players_mode",
)

highlight_overview_player = st.sidebar.checkbox(
    "Evidenzia il giocatore della Player Overview",
    value=True,
)

# ---------------------------------------------------------
# 7. GRAFICI DI DETTAGLIO
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Grafici di dettaglio")

detail_metric_names = st.sidebar.multiselect(
    "Metriche per grafici di dettaglio",
    list(METRICS.keys()),
    default=["Distance (m)"],
    key="dashboard_detail_metrics",
    help=(
        "Seleziona le metriche per Historical Reference "
        "e per i grafici con i giocatori."
    ),
)

# Le sedute omologhe richiedono sempre stesso Match Day relativo
# e stessa Length Cycle. Il criterio non è disattivabile dalla UI.
same_cycle_length = True

# ---------------------------------------------------------
# 8. TREND E PERIODO
# ---------------------------------------------------------
st.sidebar.divider()
st.sidebar.subheader("Trend del periodo")

period_mode = st.sidebar.selectbox(
    "Periodo",
    [
        "Ultimi 7 giorni",
        "Ultimi 14 giorni",
        "Ultimi 28 giorni",
        "Personalizzato",
    ],
    index=2,
)

if period_mode == "Personalizzato":
    default_start = max(
        pd.Timestamp(min(available_dates)),
        reference_ts - timedelta(days=27),
    )
    period_dates = st.sidebar.date_input(
        "Intervallo del trend",
        value=(default_start.date(), reference_ts.date()),
        min_value=min(available_dates),
        max_value=max(available_dates),
        format="DD/MM/YYYY",
    )

    if isinstance(period_dates, tuple) and len(period_dates) == 2:
        start_ts = pd.Timestamp(period_dates[0])
        end_ts = pd.Timestamp(period_dates[1])
    else:
        start_ts = pd.Timestamp(period_dates)
        end_ts = pd.Timestamp(period_dates)
else:
    days = int(period_mode.split()[1])
    start_ts = reference_ts - timedelta(days=days - 1)
    end_ts = reference_ts

trend_entities = [
    "Team Average",
    *sorted(raw["Athlete"].dropna().astype(str).unique()),
]

trend_entity = st.sidebar.selectbox(
    "Giocatore del Trend",
    trend_entities,
    index=0,
    help=(
        "Seleziona Team Average per visualizzare la media giornaliera "
        "oppure un singolo giocatore."
    ),
)

trend_metric_names = st.sidebar.multiselect(
    "Metriche per Trend",
    list(METRICS.keys()),
    default=["Distance (m)"],
    help=(
        "La selezione del trend è indipendente "
        "dai grafici di dettaglio."
    ),
)

period_raw = raw[
    raw["Date"].dt.normalize().between(
        start_ts.normalize(),
        end_ts.normalize(),
    )
    & raw["Drill"].eq(selected_drill)
].copy()

period_player_day = aggregate_player_day(period_raw)

# -------------------------
# CONTESTO
# -------------------------
context = context_for_date(raw, reference_ts)

st.subheader("Contesto della giornata")
ctx1, ctx2, ctx3, ctx4 = st.columns(4)
ctx1.metric("Data", reference_ts.strftime("%d/%m/%Y"))
ctx2.metric("Match Cycle", str(context["cycle"]))
ctx3.metric("Match Day", str(context["relative_day"]))
ctx4.metric(
    "Length Cycle",
    f"{context['length_cycle']} giorni" if context["length_cycle"] else "N/D",
)

m1, m2 = st.columns(2)
m1.info(f"**Partita precedente:** {match_text(context['previous_match'], future=False)}")
m2.info(f"**Prossima partita:** {match_text(context['next_match'], future=True)}")

st.caption(
    f"Drill selezionato: {selected_drill} · "
    f"Periodo trend: {start_ts.strftime('%d/%m/%Y')} → "
    f"{end_ts.strftime('%d/%m/%Y')} · "
    f"Accumulo: {accumulation_description}"
)

# -------------------------
# PANORAMICA MULTI-METRICA
# -------------------------
all_selected_raw = raw.copy()
all_selected_raw = all_selected_raw[all_selected_raw["Drill"].eq(selected_drill)]
all_player_day = aggregate_player_day(all_selected_raw)

current_players = all_player_day[
    all_player_day["Date"].dt.normalize().eq(reference_ts.normalize())
].copy()

historical = historical_similar_days(
    all_player_day,
    reference_ts,
    same_cycle_length=same_cycle_length,
)

metric_reference_rows = []

overview_label = (
    "Team"
    if overview_mode == "Team Overview"
    else overview_player
)

st.markdown(
    f"""
    <div class="pas-dashboard-hero">
        <div>
            <div class="pas-dashboard-hero-title">Panoramica del giorno · {overview_label}</div>
            <div class="pas-dashboard-hero-meta">{reference_ts.strftime('%d/%m/%Y')} · {selected_drill}</div>
        </div>
        <div class="pas-dashboard-hero-meta" title="Baseline: stesso Match Day relativo e stessa Length Cycle">
            Baseline omologa · il rombo indica il giorno selezionato
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

metric_groups = {
    "Internal Load": [
        "RPE",
        "Anaerobic Threshold Zone (mm:ss)",
        "High Intensity Training (mm:ss)",
    ],
    "Volume": [
        "Duration (min)",
        "Distance (m)",
    ],
    "High Speed Running": [
        "Distance 19.8-25.2 km/h (m)",
        "Distance >25.2 km/h (m)",
    ],
    "Mechanical Load": [
        "Acc Events (n°)",
        "Dec Events (n°)",
    ],
    "Speed": [
        "Max Speed (km/h)",
        "Speed Events (n°)",
    ],
}

metric_reference_rows = []

dashboard_historical_max_speed_references = (
    build_historical_max_speed_references(report_source)
)
dashboard_player_max_speed_pct = max_speed_percentage_lookup(
    current_players,
    dashboard_historical_max_speed_references,
    team_average_mode=False,
)

if not overview_metric_names:
    st.info("Seleziona almeno una metrica nella barra laterale.")
else:
    for group_name, group_metrics in metric_groups.items():
        visible_metrics = [
            name for name in group_metrics
            if name in overview_metric_names
        ]
        if not visible_metrics:
            continue

        st.markdown(
            f'<div class="pas-section-title">{group_name}</div>',
            unsafe_allow_html=True,
        )

        columns = st.columns(
            len(visible_metrics),
            gap="medium",
        )

        for column, overview_name in zip(columns, visible_metrics):
            meta = METRICS[overview_name]
            overview_column = meta["column"]
            overview_unit = meta["unit"]
            overview_decimals = int(meta.get("decimals", 0))

            if overview_mode == "Team Overview":
                overview_period_values = period_player_day[overview_column]
                historical_entity_metric = (
                    historical.groupby(
                        ["Date", "Cycle"],
                        as_index=False,
                    )[overview_column].mean()
                    if not historical.empty
                    else pd.DataFrame(
                        columns=["Date", "Cycle", overview_column]
                    )
                )
                current_entity_metric = (
                    current_players[overview_column].mean()
                    if not current_players.empty
                    else np.nan
                )
            else:
                overview_period_values = period_player_day.loc[
                    period_player_day["Athlete"].eq(overview_player),
                    overview_column,
                ]
                historical_entity_metric = (
                    historical.loc[
                        historical["Athlete"].eq(overview_player),
                        ["Date", "Cycle", overview_column],
                    ]
                    .groupby(
                        ["Date", "Cycle"],
                        as_index=False,
                    )[overview_column]
                    .mean()
                    if not historical.empty
                    else pd.DataFrame(
                        columns=["Date", "Cycle", overview_column]
                    )
                )
                current_entity_metric = (
                    current_players.loc[
                        current_players["Athlete"].eq(overview_player),
                        overview_column,
                    ].mean()
                    if not current_players.empty
                    else np.nan
                )

            # Tutte le statistiche mostrate nella card devono usare la stessa
            # baseline dello scostamento: sedute omologhe precedenti con lo
            # stesso Match Day relativo e la stessa Length Cycle.
            homologous_values = historical_entity_metric[overview_column]
            period_stats = descriptive_statistics(homologous_values)

            active_accumulation_player_day = (
                team_accumulation_player_day
                if overview_mode == "Team Overview"
                else player_accumulation_player_day
            )

            if overview_name == "RPE":
                accumulated_metric_value = np.nan
                accumulated_metric_label = ""
            else:
                accumulated_metric_value = calculate_accumulation(
                    active_accumulation_player_day,
                    overview_name,
                    overview_mode,
                    overview_player,
                )
                accumulated_metric_label = accumulation_label(
                    overview_name,
                    overview_mode,
                )

            reference_metric = value_against_reference(
                current_entity_metric,
                historical_entity_metric[overview_column],
            )

            reference_label = (
                "Media team · sedute simili"
                if overview_mode == "Team Overview"
                else f"{overview_player} · sedute simili"
            )

            max_speed_secondary_text = None
            if overview_name == "Max Speed (km/h)":
                if overview_mode == "Team Overview":
                    historical_team_values = pd.to_numeric(
                        dashboard_historical_max_speed_references.get(
                            "Historical Max Speed", pd.Series(dtype=float)
                        ),
                        errors="coerce",
                    ).dropna()
                    historical_team_mean = (
                        float(historical_team_values.mean())
                        if not historical_team_values.empty
                        else np.nan
                    )
                    pct_value = (
                        float(current_entity_metric) / historical_team_mean * 100
                        if pd.notna(current_entity_metric)
                        and pd.notna(historical_team_mean)
                        and historical_team_mean > 0
                        else np.nan
                    )
                else:
                    pct_value = dashboard_player_max_speed_pct.get(
                        str(overview_player)
                    )
                if pct_value is not None and pd.notna(pct_value):
                    max_speed_secondary_text = (
                        f"{float(pct_value):.1f}% del massimo individuale"
                        .replace(".", ",")
                    )

            with column:
                with st.container(border=True):
                    render_metric_card_header(
                        title=overview_name,
                        value=current_entity_metric,
                        metric_name=overview_name,
                        delta_pct=reference_metric["difference_pct"],
                        z_score=reference_metric["z_score"],
                        period_stats=period_stats,
                        accumulation_value=accumulated_metric_value,
                        accumulation_text=accumulated_metric_label,
                        secondary_text=max_speed_secondary_text,
                        reference_count=int(period_stats["count"]),
                        reference_detail=(
                            f"Stesso Match Day: {context['relative_day']} · "
                            f"Stessa Length Cycle: {context['length_cycle']} giorni"
                        ),
                    )

                    historical_card_figure = compact_reference_boxplot(
                        historical_entity_metric,
                        overview_column,
                        current_entity_metric,
                        overview_unit,
                        reference_label,
                        overview_decimals,
                        metric_format(overview_name),
                        show_cycle_legend=False,
                        use_cycle_colors=False,
                        dashboard_style=True,
                    )

                    historical_report_figure = (
                        compact_reference_boxplot(
                            historical_entity_metric,
                            overview_column,
                            current_entity_metric,
                            overview_unit,
                            reference_label,
                            overview_decimals,
                            metric_format(overview_name),
                            show_cycle_legend=True,
                            use_cycle_colors=True,
                        )
                    )

                    render_reportable_chart(
                        historical_card_figure,
                        title=f"{overview_name} - Confronto sedute simili",
                        key=(
                            f"mini_box_{overview_mode}_"
                            f"{overview_player}_{overview_name}"
                        ),
                        config={
                            "displayModeBar": False,
                            "responsive": True,
                        },
                        selection_group=f"overview_{overview_name}",
                        report_figure=historical_report_figure,
                        show_selector=False,
                    )

                    day_metric_players = current_players[
                        ["Athlete", overview_column]
                    ].copy()
                    secondary_label_column = None
                    if overview_name == "Max Speed (km/h)":
                        secondary_label_column = "_max_speed_pct"
                        day_metric_players[secondary_label_column] = (
                            day_metric_players["Athlete"]
                            .astype(str)
                            .map(dashboard_player_max_speed_pct)
                        )

                    if day_players_mode == "Solo giocatori selezionati":
                        comparison_names = list(selected_players)
                        if (
                            overview_mode == "Player Overview"
                            and overview_player
                            and overview_player not in comparison_names
                        ):
                            comparison_names.append(overview_player)

                        day_metric_players = day_metric_players[
                            day_metric_players["Athlete"].isin(
                                comparison_names
                            )
                        ]

                    highlighted_player = (
                        overview_player
                        if (
                            overview_mode == "Player Overview"
                            and highlight_overview_player
                        )
                        else None
                    )

                    with st.expander("Visualizza dettagli giocatori", expanded=False):
                        if day_metric_players.empty:
                            st.info(
                                "Nessun giocatore disponibile per il confronto "
                                "con i filtri selezionati."
                            )
                        else:
                            day_players_figure = compact_player_day_bars(
                                player_values=day_metric_players,
                                metric=overview_column,
                                unit=overview_unit,
                                color=meta.get("color", "#4C78A8"),
                                decimals=overview_decimals,
                                highlighted_player=highlighted_player,
                                secondary_metric=secondary_label_column,
                                secondary_suffix="%",
                                format_type=metric_format(overview_name),
                            )
                            render_reportable_chart(
                                day_players_figure,
                                title=f"{overview_name} - Giocatori del giorno",
                                key=(
                                    f"day_players_{overview_mode}_"
                                    f"{overview_player}_{overview_name}"
                                ),
                                config={"displayModeBar": False, "responsive": True},
                                selection_group=f"overview_{overview_name}",
                                report_enabled=False,
                            )

                    render_compact_report_selector(f"overview_{overview_name}")

            metric_reference_rows.append({
                "Metrica": overview_name,
                "Media periodo": period_stats["mean"],
                "Mediana": period_stats["median"],
                "SD": period_stats["sd"],
                "CV %": period_stats["cv"],
                "Min": period_stats["min"],
                "Max": period_stats["max"],
                "Valore giorno": current_entity_metric,
                "Delta storico %": reference_metric["difference_pct"],
                "Z-score": reference_metric["z_score"],
                "Percentile": reference_metric["percentile"],
            })

statistics_table = pd.DataFrame([
    {
        "Metrica": name,
        "Media": descriptive_statistics(period_player_day[meta["column"]])["mean"],
        "Mediana": descriptive_statistics(period_player_day[meta["column"]])["median"],
        "SD": descriptive_statistics(period_player_day[meta["column"]])["sd"],
        "CV %": descriptive_statistics(period_player_day[meta["column"]])["cv"],
        "Min": descriptive_statistics(period_player_day[meta["column"]])["min"],
        "Max": descriptive_statistics(period_player_day[meta["column"]])["max"],
        "P25": descriptive_statistics(period_player_day[meta["column"]])["p25"],
        "P75": descriptive_statistics(period_player_day[meta["column"]])["p75"],
    }
    for name, meta in METRICS.items()
]).round(2)

with st.expander("Tabella statistica completa", expanded=False):
    statistics_display = statistics_table.astype("object").copy()
    for row_index, row in statistics_display.iterrows():
        decimals = metric_decimals(row["Metrica"])
        for column_name in ["Media", "Mediana", "SD", "Min", "Max", "P25", "P75"]:
            statistics_display.at[row_index, column_name] = fmt_metric(
                row[column_name],
                row["Metrica"],
            )
        statistics_display.at[row_index, "CV %"] = fmt(row["CV %"], 1)
    st.dataframe(statistics_display, use_container_width=True, hide_index=True)

with st.expander("Verifica valori del giorno per atleta", expanded=False):
    verification_columns = ["Athlete"] + [
        METRICS[name]["column"]
        for name in overview_metric_names
        if name in METRICS
    ]
    verification = current_players[verification_columns].copy()
    rename_map = {
        METRICS[name]["column"]: name
        for name in overview_metric_names
        if name in METRICS
    }
    verification = verification.rename(columns=rename_map)
    verification_display = verification.astype("object").copy()
    for display_metric in overview_metric_names:
        if display_metric in verification_display.columns:
            decimals = metric_decimals(display_metric)
            verification_display[display_metric] = verification_display[
                display_metric
            ].map(lambda value: fmt(value, decimals))
    st.dataframe(
        verification_display,
        use_container_width=True,
        hide_index=True,
    )
    st.caption(
        "La panoramica Team è la media delle righe mostrate in questa tabella. "
        "Prima della media, eventuali righe multiple dello stesso atleta nella giornata "
        "vengono sommate per Distance, Z3, Z4, Speed Events, ACC e DEC; "
        "per Max Speed viene mantenuto il valore massimo."
    )

with st.expander("Verifica accumulo selezionato", expanded=False):
    accumulation_rows = []

    active_accumulation_player_day = (
        team_accumulation_player_day
        if overview_mode == "Team Overview"
        else player_accumulation_player_day
    )

    if overview_mode == "Team Overview":
        for athlete, athlete_data in active_accumulation_player_day.groupby("Athlete"):
            row = {"Athlete": athlete}
            for accumulation_metric_name, meta in METRICS.items():
                metric_column = meta["column"]
                method = meta.get("accumulation", "sum")
                values = athlete_data[metric_column].dropna()
                if values.empty:
                    row[accumulation_metric_name] = np.nan
                elif method == "max":
                    row[accumulation_metric_name] = values.max()
                elif method == "mean":
                    row[accumulation_metric_name] = values.mean()
                else:
                    row[accumulation_metric_name] = values.sum()
            accumulation_rows.append(row)
    else:
        athlete_data = active_accumulation_player_day[
            active_accumulation_player_day["Athlete"].eq(overview_player)
        ]
        if not athlete_data.empty:
            row = {"Athlete": overview_player}
            for accumulation_metric_name, meta in METRICS.items():
                metric_column = meta["column"]
                method = meta.get("accumulation", "sum")
                values = athlete_data[metric_column].dropna()
                if values.empty:
                    row[accumulation_metric_name] = np.nan
                elif method == "max":
                    row[accumulation_metric_name] = values.max()
                elif method == "mean":
                    row[accumulation_metric_name] = values.mean()
                else:
                    row[accumulation_metric_name] = values.sum()
            accumulation_rows.append(row)

    accumulation_verification = pd.DataFrame(accumulation_rows)

    if accumulation_verification.empty:
        st.info("Nessun dato disponibile per l'accumulo selezionato.")
    else:
        accumulation_display = accumulation_verification.astype("object").copy()
        for accumulation_metric_name in METRICS:
            if accumulation_metric_name in accumulation_display.columns:
                decimals = metric_decimals(accumulation_metric_name)
                accumulation_display[accumulation_metric_name] = (
                    accumulation_display[accumulation_metric_name]
                    .map(
                        lambda value, name=accumulation_metric_name:
                        fmt_metric(value, name)
                    )
                )

        st.dataframe(
            accumulation_display,
            use_container_width=True,
            hide_index=True,
        )

        if overview_mode == "Team Overview":
            st.caption(
                "La card Team include tutti i drill individuali previsti, "
                "indipendentemente dal filtro Drill. Mostra la somma complessiva "
                "del periodo. Per Max Speed riporta il valore più alto registrato."
            )
        else:
            st.caption(
                "La card Player include Full Training, Individual Training, "
                "Return to Play, Active Recovery, Different Training, Match "
                "e Recovery. Tutte le metriche vengono sommate; per Max Speed "
                "viene riportato il valore massimo del periodo."
            )


    st.markdown("#### Sedute incluse nel calcolo")
    audit_raw = (
        team_accumulation_raw
        if overview_mode == "Team Overview"
        else player_accumulation_raw[
            player_accumulation_raw["Athlete"].eq(overview_player)
        ]
    )
    audit_columns = [
        col for col in ["Date", "Athlete", "Drill", "Cycle"]
        if col in audit_raw.columns
    ]
    if audit_raw.empty:
        st.info("Nessuna seduta inclusa nell'accumulo selezionato.")
    else:
        audit_table = (
            audit_raw[audit_columns]
            .drop_duplicates()
            .sort_values(["Date", "Drill"])
            .copy()
        )
        audit_table["Date"] = pd.to_datetime(
            audit_table["Date"]
        ).dt.strftime("%d/%m/%Y")
        st.dataframe(
            audit_table,
            use_container_width=True,
            hide_index=True,
        )

# -------------------------
# GRAFICI DI DETTAGLIO MULTI-METRICA
# -------------------------
st.subheader("Grafici di dettaglio")

if not detail_metric_names:
    st.info(
        "Seleziona almeno una metrica nella barra laterale "
        "per visualizzare i grafici di dettaglio."
    )
else:
    st.caption(
        "Tutte le metriche selezionate sono mostrate nella stessa sezione, "
        "una sotto l'altra. Ogni metrica mantiene il proprio colore e la propria scala."
    )

    for metric_index, metric_name in enumerate(detail_metric_names):
        metric_meta = METRICS[metric_name]
        metric = metric_meta["column"]
        unit = metric_meta["unit"]
        metric_color = metric_meta.get("color")
        metric_decimal_places = metric_decimals(metric_name)

        if metric_index > 0:
            st.divider()

        st.markdown(
            f'<div class="pas-section-title">{metric_name}</div>',
            unsafe_allow_html=True,
        )

        # ---------------------------------------------
        # Historical Reference
        # ---------------------------------------------
        if overview_mode == "Team Overview":
            historical_focus = (
                historical.groupby(
                    ["Date", "Cycle"],
                    as_index=False,
                )[metric].mean()
                if not historical.empty
                else pd.DataFrame(
                    columns=["Date", "Cycle", metric]
                )
            )
            current_focus_players = current_players.copy()
            current_focus_value = (
                current_players[metric].mean()
                if not current_players.empty
                else np.nan
            )
        else:
            historical_focus = (
                historical.loc[
                    historical["Athlete"].eq(overview_player),
                    ["Date", "Cycle", metric],
                ]
                .groupby(
                    ["Date", "Cycle"],
                    as_index=False,
                )[metric]
                .mean()
                if not historical.empty
                else pd.DataFrame(
                    columns=["Date", "Cycle", metric]
                )
            )
            # Mantieni visibile l’intera distribuzione del giorno anche in Player Overview.
            # Il giocatore scelto viene evidenziato dal grafico tramite selected_players.
            current_focus_players = current_players.copy()
            selected_current = current_players[
                current_players["Athlete"].eq(overview_player)
            ]
            current_focus_value = (
                selected_current[metric].mean()
                if not selected_current.empty
                else np.nan
            )

        reference_result = value_against_reference(
            current_focus_value,
            historical_focus[metric],
        )
        historical_stats = descriptive_statistics(
            historical_focus[metric]
        )

        detail_left, detail_right = st.columns([1.05, 1.55], gap="large")

        with detail_left:
            st.markdown("#### Historical Reference")

            h1, h2 = st.columns(2)
            h1.metric(
                "Valore giorno",
                fmt_metric(current_focus_value, metric_name),
            )
            h2.metric(
                "Scostamento",
                f"{fmt(reference_result['difference_pct'], 1)}%",
            )

            h3, h4 = st.columns(2)
            h3.metric(
                "Z-score",
                fmt(reference_result["z_score"], 2),
            )
            h4.metric(
                "Percentile",
                f"{fmt(reference_result['percentile'], 0)}°",
            )

            if historical_stats["count"] == 0:
                st.warning(
                    "Nessuna giornata storica disponibile."
                )
            else:
                st.caption(
                    f"{historical_stats['count']} giornate · "
                    f"media {fmt_metric(historical_stats['mean'], metric_name)} {unit} · "
                    f"SD {fmt_metric(historical_stats['sd'], metric_name)} {unit} · "
                    f"CV {fmt(historical_stats['cv'], 1)}%"
                )

        with detail_right:
            historical_detail_figure = historical_boxplot(
                    historical_team=historical_focus,
                    current_players=current_focus_players,
                    metric=metric,
                    unit=unit,
                    decimals=metric_decimal_places,
                    color=metric_color,
                    format_type=metric_format(metric_name),
                    selected_players=(
                        [overview_player]
                        if overview_mode == "Player Overview" and overview_player
                        else selected_players
                    ),
                    current_group_value=(
                        current_focus_value
                        if overview_mode == "Team Overview"
                        else None
                    ),
                )
            render_reportable_chart(
                historical_detail_figure,
                title=f"{metric_name} - Historical Reference",
                key=f"historical_detail_{metric_name}",
                report_enabled=False,
            )


    # -----------------------------------------------------
    # GIOCATORI E MEDIA TEAM — TUTTE LE METRICHE
    # -----------------------------------------------------
    st.divider()
    st.subheader("Giocatori selezionati e Media Team")
    st.caption(
        "Ogni metrica è mostrata con la propria scala e unità di misura. "
        "Per ciascun parametro trovi una barra per ogni giocatore selezionato "
        "e una barra aggiuntiva con la Media Team."
    )

    if not selected_players:
        st.info(
            "Seleziona uno o più giocatori nella barra laterale "
            "per visualizzare le loro barre insieme alla Media Team."
        )
    else:
        comparison_metric_columns = st.columns(
            2 if len(detail_metric_names) > 1 else 1,
            gap="large",
        )

        for comparison_index, detail_metric_name in enumerate(
            detail_metric_names
        ):
            detail_meta = METRICS[detail_metric_name]
            detail_column = detail_meta["column"]
            detail_unit = detail_meta["unit"]
            detail_color = detail_meta.get("color")
            detail_decimals = metric_decimals(detail_metric_name)

            comparison_rows = [{
                "Label": "Media Team",
                "Value": period_player_day[detail_column].mean(),
                "Type": "Team",
            }]

            for comparison_player in selected_players:
                player_values = period_player_day.loc[
                    period_player_day["Athlete"].eq(comparison_player),
                    detail_column,
                ]

                comparison_rows.append({
                    "Label": comparison_player,
                    "Value": player_values.mean(),
                    "Type": "Player",
                })

            comparison_dataframe = (
                pd.DataFrame(comparison_rows)
                .dropna(subset=["Value"])
            )

            target_column = comparison_metric_columns[
                comparison_index % len(comparison_metric_columns)
            ]

            with target_column:
                with st.container(border=True):
                    st.markdown(
                        f'<div class="pas-card-title">'
                        f'{detail_metric_name}'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

                    comparison_figure = player_comparison_chart(
                            comparison_dataframe,
                            detail_unit,
                            color=detail_color,
                            decimals=detail_decimals,
                            format_type=metric_format(
                                detail_metric_name
                            ),
                        )
                    render_reportable_chart(
                        comparison_figure,
                        title=(
                            f"{detail_metric_name} - "
                            "Giocatori selezionati e Media Team"
                        ),
                        key=(
                            f"all_players_metric_"
                            f"{detail_metric_name}"
                        ),
                        report_enabled=False,
                    )

                    comparison_display = (
                        comparison_dataframe[
                            ["Label", "Value"]
                        ]
                        .rename(columns={
                            "Label": "Soggetto",
                            "Value": "Valore",
                        })
                    )

                    comparison_display["Valore"] = (
                        comparison_display["Valore"]
                        .map(
                            lambda value: (
                                f"{fmt_metric(value, detail_metric_name)} "
                                f"{detail_unit if metric_format(detail_metric_name) != 'duration' else ''}"
                            )
                        )
                    )

                    with st.expander(
                        "Mostra valori",
                        expanded=False,
                    ):
                        st.dataframe(
                            comparison_display,
                            use_container_width=True,
                            hide_index=True,
                        )

# -------------------------
# TREND DEL PERIODO — SELEZIONE INDIPENDENTE
# -------------------------
st.divider()
st.subheader("Trend del periodo")

if not trend_metric_names:
    st.info(
        "Seleziona almeno una metrica nella barra laterale "
        "alla voce 'Metriche per Trend del periodo'."
    )
else:
    st.caption(
        "Le metriche del trend sono selezionabili in modo indipendente "
        "dai grafici di dettaglio. Ogni metrica mantiene colore, scala "
        "e unità di misura propri."
    )

    trend_columns = st.columns(
        2 if len(trend_metric_names) > 1 else 1,
        gap="large",
    )

    for trend_index, trend_metric_name in enumerate(trend_metric_names):
        trend_meta = METRICS[trend_metric_name]
        trend_metric = trend_meta["column"]
        trend_unit = trend_meta["unit"]
        trend_color = trend_meta.get("color")

        if trend_entity == "Team Average":
            trend_primary_daily = (
                period_player_day.groupby(
                    "Date",
                    as_index=False,
                )[trend_metric].mean()
            )
            trend_primary_label = "Team Average"
        else:
            trend_primary_daily = (
                period_player_day.loc[
                    period_player_day["Athlete"].eq(
                        trend_entity
                    ),
                    ["Date", trend_metric],
                ]
                .groupby(
                    "Date",
                    as_index=False,
                )[trend_metric]
                .mean()
            )
            trend_primary_label = trend_entity

        trend_player_daily = pd.DataFrame(
            columns=[
                "Date",
                "Athlete",
                trend_metric,
            ]
        )

        target_trend_column = trend_columns[
            trend_index % len(trend_columns)
        ]

        with target_trend_column:
            with st.container(border=True):
                st.markdown(
                    f'<div class="pas-card-title">'
                    f'{trend_metric_name}'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                trend_figure = trend_chart(
                        trend_primary_daily,
                        trend_player_daily,
                        trend_metric,
                        trend_unit,
                        primary_label=trend_primary_label,
                        color=trend_color,
                        decimals=metric_decimals(trend_metric_name),
                        format_type=metric_format(trend_metric_name),
                    )
                render_reportable_chart(
                    trend_figure,
                    title=f"{trend_metric_name} - Trend del periodo",
                    key=(
                        f"independent_trend_"
                        f"{trend_entity}_{trend_metric_name}"
                    ),
                    report_enabled=False,
                )


# -------------------------
# REPORT PDF GRAFICI
# -------------------------
st.sidebar.divider()
st.sidebar.subheader("Report grafici")

selected_report_items = []
report_catalog = st.session_state.get("report_catalog", {})
for report_key, report_item in report_catalog.items():
    report_group = report_item.get(
        "selection_group",
        report_key,
    )
    if st.session_state.get(
        f"report_select_group_{report_group}",
        False,
    ):
        selected_report_items.append(report_item)

st.sidebar.caption(
    f"Grafici selezionati: {len(selected_report_items)}"
)

report_title = st.sidebar.text_input(
    "Titolo report grafici",
    value=(
        f"PAS Report - {reference_ts.strftime('%d-%m-%Y')}"
    ),
)

if st.sidebar.button(
    "Genera report PDF",
    disabled=not selected_report_items,
):
    report_context = [
        f"Data: {reference_ts.strftime('%d/%m/%Y')}",
        f"Drill: {selected_drill}",
        f"Panoramica: {overview_label}",
        f"Match Cycle: {context['cycle']}",
        f"Match Day: {context['relative_day']}",
    ]
    with pas_loader("Creazione report PDF..."):
        st.session_state.generated_report_pdf = build_pdf_report(
            selected_report_items,
            report_title,
            report_context,
        )

if st.session_state.get("generated_report_pdf"):
    st.sidebar.download_button(
        "Scarica / stampa PDF",
        data=st.session_state.generated_report_pdf,
        file_name=(
            f"PAS_Report_{reference_ts.strftime('%Y%m%d')}.pdf"
        ),
        mime="application/pdf",
    )

if st.sidebar.button("Svuota selezione report"):
    for report_key, report_item in report_catalog.items():
        report_group = report_item.get(
            "selection_group",
            report_key,
        )
        st.session_state[
            f"report_select_group_{report_group}"
        ] = False
    st.session_state.generated_report_pdf = None
    st.rerun()

# -------------------------
# INSIGHTS ESSENZIALI
# -------------------------
st.subheader("Key Insights")

insight_candidates = []
reference_df = pd.DataFrame(metric_reference_rows)

if not reference_df.empty:
    valid_reference = reference_df.dropna(subset=["Z-score", "Delta storico %"]).copy()
    valid_reference["Relevance"] = valid_reference["Z-score"].abs()

    for _, row in valid_reference.sort_values("Relevance", ascending=False).head(2).iterrows():
        if abs(row["Z-score"]) >= 0.75 or abs(row["Delta storico %"]) >= 8:
            direction = "sopra" if row["Delta storico %"] >= 0 else "sotto"
            insight_candidates.append(
                (
                    float(row["Relevance"]),
                    f"**{row['Metrica']}** oggi è "
                    f"**{abs(row['Delta storico %']):.1f}% {direction}** "
                    f"la media storica delle giornate simili "
                    f"(z-score {row['Z-score']:+.2f})."
                )
            )

if selected_players and not period_player_day.empty:
    player_deviations = []
    for player in selected_players:
        for overview_name in overview_metric_names:
            meta = METRICS[overview_name]
            overview_column = meta["column"]
            team_mean = period_player_day[overview_column].mean()
            player_mean = period_player_day.loc[
                period_player_day["Athlete"].eq(player), overview_column
            ].mean()

            if not pd.isna(player_mean) and not pd.isna(team_mean) and team_mean != 0:
                delta = (player_mean - team_mean) / team_mean * 100
                player_deviations.append(
                    (abs(delta), player, overview_name, delta)
                )

    if player_deviations:
        relevance, player, overview_name, delta = max(player_deviations)
        if relevance >= 10:
            insight_candidates.append(
                (
                    relevance / 10,
                    f"**{player}** presenta lo scostamento individuale più rilevante: "
                    f"**{delta:+.1f}%** dal Team Average in **{overview_name}** nel periodo."
                )
            )

insight_candidates = sorted(insight_candidates, key=lambda item: item[0], reverse=True)[:3]

if insight_candidates:
    for _, insight in insight_candidates:
        st.markdown(f"- {insight}")
else:
    st.success(
        "Nessuno scostamento rilevante: la giornata e i giocatori selezionati "
        "sono complessivamente in linea con i riferimenti disponibili."
    )



st.markdown(
    f"""
    <div style="
        margin-top:3rem;
        padding:1.2rem 0 0.8rem 0;
        border-top:1px solid rgba(185,198,216,0.18);
        text-align:center;
        color:#7F8FA4;
        font-size:0.78rem;
    ">
        PAS · Performance Analysis System · {APP_EDITION} v{APP_BUILD_VERSION} · Marco Fontanelli
    </div>
    """,
    unsafe_allow_html=True,
)
