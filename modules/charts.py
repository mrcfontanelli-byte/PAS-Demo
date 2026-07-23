from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

CHARTS_MODULE_VERSION = "2.5.11"


def _display_value(value: float, decimals: int, format_type: str) -> str:
    if pd.isna(value):
        return "N/D"
    if format_type == "duration":
        total_seconds = max(0, int(round(float(value))))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"
    return f"{float(value):.{decimals}f}"


def _display_series(
    values: pd.Series,
    decimals: int,
    format_type: str,
) -> list[str]:
    return [
        _display_value(value, decimals, format_type)
        for value in values
    ]


def _hover_value_template(decimals: int, unit: str) -> str:
    number_format = ".1f" if decimals == 1 else ".0f"
    return f"%{{y:{number_format}}} {unit}"


def trend_chart(
    team_daily: pd.DataFrame,
    player_daily: pd.DataFrame,
    metric: str,
    unit: str,
    primary_label: str = "Team Average",
    color: str | None = None,
    decimals: int = 0,
    format_type: str = "number",
):
    fig = go.Figure()

    if not team_daily.empty:
        primary_text = _display_series(
            team_daily[metric], decimals, format_type
        )
        fig.add_trace(go.Scatter(
            x=team_daily["Date"], y=team_daily[metric],
            mode="lines+markers", name=primary_label,
            line=dict(width=3, color=color),
            customdata=primary_text,
            hovertemplate=(
                "%{x|%d/%m/%Y}<br>"
                + primary_label
                + ": %{customdata}"
                + "<extra></extra>"
            ),
        ))

    if not player_daily.empty:
        for player, group in player_daily.groupby("Athlete"):
            player_text = _display_series(
                group[metric], decimals, format_type
            )
            fig.add_trace(go.Scatter(
                x=group["Date"], y=group[metric],
                mode="lines+markers", name=player,
                customdata=player_text,
                hovertemplate=(
                    "%{x|%d/%m/%Y}<br>"
                    + player
                    + ": %{customdata}"
                    + "<extra></extra>"
                ),
            ))

    fig.update_layout(
        height=430,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis_title="Data",
        yaxis_title=unit,
        legend_title="Serie",
        hovermode="x unified",
    )
    return fig


def player_comparison_chart(
    comparison: pd.DataFrame,
    unit: str,
    color: str | None = None,
    decimals: int = 0,
    format_type: str = "number",
):
    text_format = ".1f" if decimals == 1 else ".0f"

    plot_data = comparison.copy()
    plot_data["DisplayValue"] = _display_series(
        plot_data["Value"], decimals, format_type
    )
    if "DisplayLabel" in plot_data.columns:
        plot_data["DisplayValue"] = plot_data["DisplayLabel"]

    fig = px.bar(
        plot_data,
        x="Value",
        y="Label",
        orientation="h",
        text="DisplayValue",
        custom_data=["DisplayValue", "Type"],
    )
    fig.update_traces(
        textposition="outside",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Valore: %{customdata[0]}"
            "<extra></extra>"
        ),
    )

    if color:
        fig.update_traces(marker_color=color)
    fig.update_layout(
        height=max(320, 55 * len(comparison)),
        xaxis_title=unit,
        yaxis_title="",
        margin=dict(l=20, r=20, t=30, b=20),
        showlegend=False,
    )
    return fig



def historical_boxplot(
    historical_team: pd.DataFrame,
    current_players: pd.DataFrame,
    metric: str,
    unit: str,
    decimals: int = 0,
    color: str | None = None,
    format_type: str = "number",
):
    fig = go.Figure()

    if not historical_team.empty:
        historical_plot = historical_team.copy()
        if "Cycle" not in historical_plot.columns:
            historical_plot["Cycle"] = "N/D"
        if "Date" not in historical_plot.columns:
            historical_plot["Date"] = pd.NaT

        fig.add_trace(
            go.Box(
                y=historical_plot[metric],
                name="Storico",
                boxpoints=False,
                line=dict(width=1.5),
                fillcolor=color if color else "rgba(150,150,150,0.18)",
                hoverinfo="skip",
            )
        )

        fig.add_trace(
            go.Scatter(
                x=["Storico"] * len(historical_plot),
                y=historical_plot[metric],
                mode="markers",
                name="Sedute storiche",
                marker=dict(size=9, color=color),
                customdata=list(zip(
                    historical_plot["Cycle"],
                    historical_plot["Date"],
                    _display_series(
                        historical_plot[metric], decimals, format_type
                    ),
                )),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Data: %{customdata[1]|%d/%m/%Y}<br>"
                    "Valore: %{customdata[2]}"
                    "<extra></extra>"
                ),
            )
        )

    if not current_players.empty:
        current_plot = current_players.copy()
        if "Cycle" not in current_plot.columns:
            current_plot["Cycle"] = "N/D"
        if "Date" not in current_plot.columns:
            current_plot["Date"] = pd.NaT

        fig.add_trace(
            go.Scatter(
                x=["Giorno selezionato"] * len(current_plot),
                y=current_plot[metric],
                mode="markers",
                text=current_plot["Athlete"],
                customdata=list(zip(
                    current_plot["Cycle"],
                    current_plot["Date"],
                    _display_series(
                        current_plot[metric], decimals, format_type
                    ),
                )),
                name="Giocatori del giorno",
                marker=dict(size=10, symbol="diamond", color=color),
                hovertemplate=(
                    "<b>%{text}</b><br>"
                    "Match Cycle: %{customdata[0]}<br>"
                    "Data: %{customdata[1]|%d/%m/%Y}<br>"
                    "Valore: %{customdata[2]}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=470,
        yaxis_title=unit,
        xaxis_title="",
        margin=dict(l=20, r=20, t=30, b=20),
    )
    return fig


def compact_reference_boxplot(
    historical_data: pd.DataFrame,
    metric: str,
    current_value: float,
    unit: str,
    reference_label: str,
    decimals: int = 0,
    format_type: str = "number",
    show_cycle_legend: bool = True,
    use_cycle_colors: bool = True,
):
    """Box plot con colori per ciclo e rombo sul giorno selezionato."""
    historical_plot = historical_data.copy()

    if metric not in historical_plot.columns:
        historical_plot[metric] = pd.Series(dtype=float)
    if "Cycle" not in historical_plot.columns:
        historical_plot["Cycle"] = "N/D"
    if "Date" not in historical_plot.columns:
        historical_plot["Date"] = pd.NaT

    historical_plot[metric] = pd.to_numeric(
        historical_plot[metric], errors="coerce"
    )
    historical_plot["Cycle"] = (
        historical_plot["Cycle"].fillna("N/D").astype(str)
    )
    historical_plot = historical_plot.dropna(subset=[metric])

    fig = go.Figure()

    if not historical_plot.empty:
        fig.add_trace(
            go.Box(
                y=historical_plot[metric],
                name=reference_label,
                boxpoints=False,
                line=dict(width=1.5),
                fillcolor="rgba(150,150,150,0.16)",
                hoverinfo="skip",
                showlegend=False,
            )
        )

        palette = [
            "#4C78A8", "#F58518", "#54A24B", "#E45756",
            "#72B7B2", "#B279A2", "#FF9DA6", "#9D755D",
            "#BAB0AC", "#D45087", "#2A9D8F", "#F2CF5B",
        ]

        for index, cycle_name in enumerate(
            historical_plot["Cycle"].drop_duplicates().tolist()
        ):
            cycle_data = historical_plot[
                historical_plot["Cycle"].eq(cycle_name)
            ]
            fig.add_trace(
                go.Scatter(
                    x=[reference_label] * len(cycle_data),
                    y=cycle_data[metric],
                    mode="markers",
                    name=cycle_name,
                    marker=dict(
                        size=8,
                        color=(
                            palette[index % len(palette)]
                            if use_cycle_colors
                            else "#8A98A8"
                        ),
                        opacity=0.8,
                        line=dict(width=0.7, color="#FFFFFF"),
                    ),
                    customdata=list(zip(
                        cycle_data["Date"],
                        _display_series(
                            cycle_data[metric],
                            decimals,
                            format_type,
                        ),
                    )),
                    hovertemplate=(
                        "<b>%{fullData.name}</b><br>"
                        "Data: %{customdata[0]|%d/%m/%Y}<br>"
                        "Valore: %{customdata[1]}"
                        "<extra></extra>"
                    ),
                )
            )

    if current_value is not None and not pd.isna(current_value):
        fig.add_trace(
            go.Scatter(
                x=[reference_label],
                y=[current_value],
                mode="markers",
                name="Giorno selezionato",
                marker=dict(
                    size=16,
                    symbol="diamond",
                    color="#F4C430",
                    line=dict(width=2, color="#071426"),
                ),
                customdata=[
                    _display_value(
                        current_value, decimals, format_type
                    )
                ],
                hovertemplate=(
                    "<b>Giorno selezionato</b><br>"
                    "Valore: %{customdata}"
                    "<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        height=235,
        margin=dict(l=5, r=5, t=42, b=5),
        showlegend=show_cycle_legend,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0,
            font=dict(size=8),
            title_text="Match Cycle",
        ),
        xaxis=dict(
            showticklabels=False,
            title="",
            fixedrange=True,
        ),
        yaxis=dict(
            title="",
            zeroline=False,
            fixedrange=True,
        ),
        hovermode="closest",
    )
    return fig



def multi_metric_comparison_chart(
    comparison_long: pd.DataFrame,
    metric_colors: dict[str, str],
):
    """
    Confronto multi-metrica normalizzato sul Team Average = 100.

    comparison_long columns:
    - Label
    - Metric
    - RelativeValue
    - RawValue
    - Unit
    """
    fig = go.Figure()

    if comparison_long.empty:
        return fig

    label_order = comparison_long["Label"].drop_duplicates().tolist()

    for metric_name in comparison_long["Metric"].drop_duplicates():
        metric_data = comparison_long[
            comparison_long["Metric"].eq(metric_name)
        ].copy()

        fig.add_trace(
            go.Bar(
                y=metric_data["Label"],
                x=metric_data["RelativeValue"],
                name=metric_name,
                orientation="h",
                marker_color=metric_colors.get(metric_name),
                customdata=metric_data[["RawValue", "Unit"]].to_numpy(),
                hovertemplate=(
                    "<b>%{y}</b><br>"
                    + metric_name
                    + "<br>"
                    + "Valore: %{customdata[0]} %{customdata[1]}<br>"
                    + "Team Average: %{x:.1f}%"
                    + "<extra></extra>"
                ),
            )
        )

    fig.add_vline(
        x=100,
        line_dash="dash",
        line_width=1.5,
        annotation_text="Team Average",
        annotation_position="top",
    )

    fig.update_layout(
        barmode="group",
        height=max(420, 90 * len(label_order)),
        margin=dict(l=20, r=20, t=55, b=20),
        xaxis_title="% del Team Average",
        yaxis_title="",
        legend_title="Metriche",
        yaxis=dict(
            categoryorder="array",
            categoryarray=label_order[::-1],
        ),
        hovermode="closest",
    )

    return fig



def compact_player_day_bars(
    player_values: pd.DataFrame,
    metric: str,
    unit: str,
    color: str,
    decimals: int,
    highlighted_player: str | None = None,
    format_type: str = "number",
):
    """
    Barre orizzontali compatte per confrontare i giocatori della giornata.

    player_values deve contenere:
    - Athlete
    - metric
    """
    plot_data = player_values[["Athlete", metric]].copy()
    plot_data[metric] = pd.to_numeric(plot_data[metric], errors="coerce")
    plot_data = plot_data.dropna(subset=[metric])

    if plot_data.empty:
        return go.Figure()

    plot_data = plot_data.sort_values(metric, ascending=True)
    team_mean = float(plot_data[metric].mean())

    bar_colors = []
    for athlete in plot_data["Athlete"]:
        if highlighted_player and athlete == highlighted_player:
            bar_colors.append("#F4C430")
        else:
            bar_colors.append(color)

    text_format = ".1f" if decimals == 1 else ".0f"
    text_values = _display_series(
        plot_data[metric], decimals, format_type
    )

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=plot_data[metric],
            y=plot_data["Athlete"],
            orientation="h",
            marker_color=bar_colors,
            text=text_values,
            textposition="outside",
            customdata=list(zip(plot_data["Athlete"], text_values)),
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Valore: %{customdata[1]}"
                + "<extra></extra>"
            ),
        )
    )

    fig.add_vline(
        x=team_mean,
        line_dash="dash",
        line_width=1.5,
        line_color="#FF6B6B",
        annotation_text=f"Media Team {_display_value(team_mean, decimals, format_type)}",
        annotation_position="top",
    )

    fig.update_layout(
        height=max(260, 28 * len(plot_data) + 80),
        margin=dict(l=8, r=55, t=35, b=8),
        xaxis_title="",
        yaxis_title="",
        showlegend=False,
        bargap=0.22,
    )

    return fig
