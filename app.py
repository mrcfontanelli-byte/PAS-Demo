from __future__ import annotations

from pathlib import Path
from contextlib import contextmanager
import base64
from datetime import timedelta
from io import BytesIO
import re
import unicodedata

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from modules.config import APP_NAME, APP_SUBTITLE, METRICS, DEFAULT_DRILLS
from modules.security import DEMO_PASSWORD
from modules.version import APP_BUILD_VERSION, APP_EDITION
from modules.data_loader import (
    find_database,
    load_database,
    aggregate_player_day,
    database_summary,
)
from modules.statistics_engine import descriptive_statistics, value_against_reference
from modules.context_engine import context_for_date, historical_similar_days
from modules.reporting import (
    build_pdf_report,
    build_session_report_pdf,
    build_forecast_report_pdf,
)
from modules.charts import (
    trend_chart,
    player_comparison_chart,
    historical_boxplot,
    compact_reference_boxplot,
    compact_player_day_bars,
)


st.set_page_config(
    page_title=f"{APP_NAME} · {APP_EDITION} v{APP_BUILD_VERSION}",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
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

    .pas-card-title {
        font-size: 1.42rem;
        font-weight: 850;
        line-height: 1.18;
        margin-bottom: 0.35rem;
        color: #F5F7FA;
    }

    .pas-card-value {
        font-size: 2.65rem;
        font-weight: 850;
        line-height: 1;
        margin: 0.15rem 0 0.35rem 0;
        color: #FFFFFF;
    }

    .pas-card-delta {
        display: inline-block;
        font-size: 0.88rem;
        font-weight: 750;
        padding: 0.22rem 0.48rem;
        border-radius: 0.45rem;
        margin-bottom: 0.45rem;
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
        font-size: 0.83rem;
        line-height: 1.45;
        color: #B9C6D8;
        margin-top: 0.15rem;
    }

    .pas-card-accumulation {
        margin-top: 0.55rem;
        padding: 0.48rem 0.58rem;
        border-radius: 0.55rem;
        background: rgba(244, 196, 48, 0.08);
        border: 1px solid rgba(244, 196, 48, 0.22);
    }

    .pas-card-accumulation-label {
        font-size: 0.78rem;
        font-weight: 750;
        color: #D8E1EE;
        margin-bottom: 0.08rem;
    }

    .pas-card-accumulation-value {
        font-size: 1.34rem;
        font-weight: 850;
        color: #F4C430;
        line-height: 1.1;
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

    if report_group not in _report_selector_groups_rendered:
        _report_selector_groups_rendered.add(report_group)
        st.checkbox(
            "Aggiungi box plot al report PDF",
            key=f"report_select_group_{report_group}",
            help=(
                "Se il parametro contiene più grafici, "
                "verranno inseriti tutti con una sola selezione."
            ),
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

    if metric_name == "RPE":
        html = f"""
<div class="pas-card-title">{title}</div>
<div class="pas-card-value">{display_value}</div>
<div class="pas-card-delta {status_class}">{delta_text}</div>
<div class="pas-card-stats">
    Media {display_mean}
    &nbsp;·&nbsp; Mediana {display_median}
    &nbsp;·&nbsp; SD {display_sd}
    &nbsp;·&nbsp; CV {fmt(period_stats['cv'], 1)}%
</div>
"""
    else:
        display_accumulation = fmt_metric(
            accumulation_value,
            metric_name,
        )

        html = f"""
<div class="pas-card-title">{title}</div>
<div class="pas-card-value">{display_value}</div>
<div class="pas-card-delta {status_class}">{delta_text}</div>
<div class="pas-card-stats">
    Media {display_mean}
    &nbsp;·&nbsp; Mediana {display_median}
    &nbsp;·&nbsp; SD {display_sd}
    &nbsp;·&nbsp; CV {fmt(period_stats['cv'], 1)}%
</div>
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
        "color": "#577590",
    },
    "Acc Events (n°/min)": {
        "column": "acc events/min",
        "unit": "n°/min",
        "color": "#54A24B",
    },
    "Dec Events (n°/min)": {
        "column": "dec events /min",
        "unit": "n°/min",
        "color": "#F58518",
    },
    "19.8-25.2 km/h (m/min)": {
        "column": "distance/speed Z3 (m) /min",
        "unit": "m/min",
        "color": "#F2CF5B",
    },
    ">25.2 km/h (m/min)": {
        "column": "distance/speed Z4 (m)/min",
        "unit": "m/min",
        "color": "#E45756",
    },
    "Speed Events (n°/min)": {
        "column": "Speed Events/min",
        "unit": "n°/min",
        "color": "#72B7B2",
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
def load_exercise_sheets(excel_source):
    """
    Carica i fogli Esercitazioni ed Esercitazioni Avg.
    """
    exercises = pd.read_excel(
        excel_source,
        sheet_name="Esercitazioni",
    )
    averages = pd.read_excel(
        excel_source,
        sheet_name="Esercitazioni Avg",
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



def drills_boxplot(
    source: pd.DataFrame,
    selected_drills: list[str],
    metric_name: str,
    for_report: bool = False,
):
    """
    Box plot per drill con tutti i punti e AVG per ciascun drill.
    Nel PDF l'AVG è nero e in grassetto.
    """
    meta = DRILL_ANALYSIS_METRICS[metric_name]
    column = meta["column"]
    palette = [
        "#4C78A8",
        "#F58518",
        "#54A24B",
        "#E45756",
        "#72B7B2",
        "#B279A2",
        "#D45087",
        "#F2CF5B",
    ]

    figure = go.Figure()

    for index, drill_name in enumerate(selected_drills):
        drill_data = source[
            source["Drill"].eq(drill_name)
        ].copy()

        values = safe_numeric_series(
            drill_data,
            column,
        )
        valid = drill_data.loc[
            values.notna()
        ].copy()
        valid["Metric Value"] = values.loc[
            values.notna()
        ]

        if valid.empty:
            continue

        match_reference = (
            valid["Drill"].astype(str)
            + " · "
            + valid["Date"].dt.strftime("%d/%m/%Y")
            + " · "
            + valid["Athlete"].astype(str)
        )

        drill_color = palette[index % len(palette)]
        average_value = float(
            valid["Metric Value"].mean()
        )

        figure.add_trace(
            go.Box(
                y=valid["Metric Value"],
                name=drill_name,
                boxpoints="all",
                jitter=0.38,
                pointpos=0,
                marker=dict(
                    size=7,
                    color=drill_color,
                    opacity=0.72,
                ),
                line=dict(
                    color=drill_color,
                    width=1.6,
                ),
                customdata=match_reference,
                hovertemplate=(
                    "<b>%{customdata}</b><br>"
                    "Valore: %{y:.2f} "
                    + meta["unit"]
                    + "<extra></extra>"
                ),
            )
        )

        figure.add_shape(
            type="line",
            xref="x",
            yref="y",
            x0=index - 0.30,
            x1=index + 0.30,
            y0=average_value,
            y1=average_value,
            line=dict(
                color=(
                    "#000000"
                    if for_report
                    else "#D62839"
                ),
                width=2.4,
                dash="dash",
            ),
        )

        figure.add_annotation(
            x=index,
            y=average_value,
            text=(
                f"<b>AVG {average_value:.1f}</b>"
            ),
            showarrow=False,
            yshift=13,
            font=dict(
                size=11,
                color=(
                    "#000000"
                    if for_report
                    else "#F4C430"
                ),
                family=(
                    "Arial Black"
                    if for_report
                    else "Arial"
                ),
            ),
        )

    figure.update_layout(
        height=480,
        margin=dict(l=30, r=20, t=42, b=80),
        yaxis_title=meta["unit"],
        xaxis_title="Drill",
        showlegend=False,
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
        width=92,
    )
st.sidebar.markdown(
    "**Performance Analysis System**"
)
st.sidebar.caption("Hellas Verona FC")

with st.sidebar.expander(
    "Database",
    expanded=False,
):
    uploaded_database = st.file_uploader(
        "Carica database Excel",
        type=["xlsx", "xls"],
        help=(
            "Se carichi un file, il PAS lo usa per questa sessione. "
            "Altrimenti utilizza il database presente nella cartella."
        ),
    )

    try:
        if uploaded_database is not None:
            database_path = None
            database_excel_source = (
                uploaded_database.getvalue()
            )
            raw = load_database(
                database_excel_source,
                source_name=uploaded_database.name,
            )
            database_source_label = "File caricato"
        else:
            database_path = find_database(base_dir)
            database_excel_source = str(database_path)
            raw = load_database(
                database_excel_source,
                source_name=database_path.name,
            )
            database_source_label = "File nella cartella PAS"

        (
            exercises_raw,
            exercises_avg,
        ) = load_exercise_sheets(
            database_excel_source
        )
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

st.sidebar.caption(
    f"Database: {database_info['source_name']} · "
    f"ultimo dato "
    f"{pd.Timestamp(database_info['last_date']).strftime('%d/%m/%Y')}"
)
st.sidebar.divider()

st.sidebar.caption(f"PAS · {APP_EDITION} v{APP_BUILD_VERSION}")
if st.sidebar.button(
    "Esci dalla Demo",
    use_container_width=True,
):
    st.session_state["pas_demo_authenticated"] = False
    st.rerun()

page = st.sidebar.radio(
    "Navigazione",
    [
        "🏠 Dashboard",
        "📊 Period Load",
        "🔮 Forecast",
        "🧩 Drills",
        "⚽ Match Analysis",
        "🎯 Performance Model",
        "🏥 Return To Play",
        "👤 Player Profiles",
    ],
)

render_pas_brand_header(base_dir)

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

    available_period_players = sorted(
        period_totals_raw["Athlete"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

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
        build_historical_max_speed_references(raw)
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
            metric_name != "Duration (min)"
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
                    if metric_name == "Duration (min)":
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



if page == "🔮 Forecast":
    st.title("🔮 Forecast")
    st.caption(
        "Build a forecast session by selecting the role, "
        "the drills and their expected duration."
    )

    forecast_roles = sorted(
        exercises_avg["Role"]
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
        exercises_avg.loc[
            exercises_avg["Role"].eq(forecast_role),
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
        exercises_avg,
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

    selected_drill_role = st.sidebar.selectbox(
        "Role",
        drill_roles,
        key="drills_role",
    )

    if selected_drill_role == "Team Average":
        drill_source = exercises_raw.copy()
    else:
        drill_source = exercises_raw[
            exercises_raw["Role"].eq(
                selected_drill_role
            )
        ].copy()

    available_drills = sorted(
        drill_source["Drill"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    default_drills = available_drills[:3]

    selected_drills = st.sidebar.multiselect(
        "Drills",
        available_drills,
        default=default_drills,
        key="drills_selected",
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

    filtered_drill_source = drill_source[
        drill_source["Drill"].isin(
            selected_drills
        )
    ].copy()

    st.subheader("Drill Distributions")
    st.caption(
        "Each point represents one player exposure. "
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

        figure = drills_boxplot(
            filtered_drill_source,
            selected_drills,
            metric_name,
            for_report=False,
        )
        st.plotly_chart(
            figure,
            use_container_width=True,
            key=f"drill_box_{metric_name}",
        )

        report_figure = drills_boxplot(
            filtered_drill_source,
            selected_drills,
            metric_name,
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

    for drill_name in selected_drills:
        drill_rows = filtered_drill_source[
            filtered_drill_source["Drill"].eq(
                drill_name
            )
        ]
        for metric_name in selected_drill_metrics:
            column = DRILL_ANALYSIS_METRICS[
                metric_name
            ]["column"]

            if column not in drill_rows.columns:
                continue

            values = safe_numeric_series(
                drill_rows,
                column,
            ).dropna()

            if values.empty:
                continue

            summary_rows.append(
                {
                    "Drill": drill_name,
                    "Metric": metric_name,
                    "N": int(len(values)),
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
            f"DRILLS ANALYSIS REPORT - "
            f"{selected_drill_role}"
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
                    f"Role: {selected_drill_role}",
                    (
                        "Drills: "
                        + ", ".join(selected_drills)
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

    match_raw = raw[
        raw["Drill"].astype(str).str.strip().eq("Match")
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

    match_tab, comparison_tab = st.tabs(
        ["Singola partita", "Confronto / Totali partite"]
    )

    with match_tab:
        selected_match_label = st.selectbox(
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

        selected_match_players = st.multiselect(
            "Giocatori",
            sorted(selected_match_data["Athlete"].unique()),
            default=sorted(selected_match_data["Athlete"].unique()),
            key="match_players",
        )
        selected_match_metrics = st.multiselect(
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

        match_average_metrics = {
            "Max Speed (km/h)",
            "Relative Distance (m/min)",
            "MPE Rec Avg Time (s)",
        }

        match_total_row = {"Athlete": "MATCH TOTAL"}
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
                    summary_label="MATCH TOTAL",
                    summary_average_metrics={
                        "Relative Distance (m/min)",
                        "MPE Rec Avg Time (s)",
                        "Max Speed (km/h)",
                    },
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

    with comparison_tab:
        comparison_matches = st.multiselect(
            "Partite da confrontare",
            list(match_lookup.keys()),
            default=list(match_lookup.keys())[-3:],
            key="comparison_matches",
        )

        comparison_subject = st.selectbox(
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

        comparison_metrics = st.multiselect(
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

st.title(APP_SUBTITLE)
st.caption(
    f"Database: {database_info['source_name']} · "
    f"Ultimo dato: "
    f"{pd.Timestamp(database_info['last_date']).strftime('%d/%m/%Y')}"
)

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
    value=default_reference_date,
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
)

overview_player = None
if overview_mode == "Player Overview":
    all_players = sorted(raw["Athlete"].dropna().unique())
    overview_player = st.sidebar.selectbox(
        "Giocatore della panoramica",
        all_players,
    )

overview_metric_names = st.sidebar.multiselect(
    "Metriche della panoramica",
    list(METRICS.keys()),
    default=list(METRICS.keys()),
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

session_day_raw = raw[
    raw["Date"].dt.normalize().eq(reference_ts.normalize())
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
    build_historical_max_speed_references(raw)
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
)

day_players_mode = st.sidebar.radio(
    "Giocatori nelle card",
    ["Tutta la squadra", "Solo giocatori selezionati"],
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
    help=(
        "Seleziona le metriche per Historical Reference "
        "e per i grafici con i giocatori."
    ),
)

same_cycle_length = st.sidebar.checkbox(
    "Storico: stessa Length Cycle",
    value=True,
)

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

st.subheader(
    f"Panoramica del giorno · {overview_label} · "
    f"{reference_ts.strftime('%d/%m/%Y')} · {selected_drill}"
)
st.caption(
    "Il valore grande rappresenta il giorno selezionato. "
    "Il box plot utilizza le sedute simili precedenti: media Team in Team Overview, "
    "storico dello stesso atleta in Player Overview. Il rombo indica il giorno selezionato."
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

            period_stats = descriptive_statistics(
                overview_period_values
            )

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
                    )

                    st.markdown(
                        "<div class='pas-card-stats' style='font-weight:800; "
                        "margin-top:0.35rem;'>Confronto giocatori del giorno</div>",
                        unsafe_allow_html=True,
                    )

                    day_metric_players = current_players[
                        ["Athlete", overview_column]
                    ].copy()

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
                                format_type=metric_format(overview_name),
                            )
                        render_reportable_chart(
                            day_players_figure,
                            title=f"{overview_name} - Giocatori del giorno",
                            key=(
                                f"day_players_{overview_mode}_"
                                f"{overview_player}_{overview_name}"
                            ),
                            config={
                                "displayModeBar": False,
                                "responsive": True,
                            },
                            selection_group=f"overview_{overview_name}",
                            report_enabled=False,
                        )

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
            current_focus_players = current_players[
                current_players["Athlete"].eq(overview_player)
            ].copy()
            current_focus_value = (
                current_focus_players[metric].mean()
                if not current_focus_players.empty
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
