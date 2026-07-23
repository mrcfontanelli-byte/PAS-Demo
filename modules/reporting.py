from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

import pandas as pd

import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas



def _brand_logo_path() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "brand"
        / "hellas_verona_logo.png"
    )


def _draw_brand_logo(
    pdf,
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    logo_path = _brand_logo_path()
    if not logo_path.exists():
        return

    try:
        pdf.drawImage(
            ImageReader(str(logo_path)),
            x,
            y,
            width=width,
            height=height,
            preserveAspectRatio=True,
            anchor="c",
            mask="auto",
        )
    except Exception:
        pass



def build_pdf_report(
    report_items: list[dict[str, Any]],
    report_title: str,
    context_lines: list[str],
) -> bytes:
    """Tutti i grafici selezionati adattati in una sola pagina A4."""
    import math

    output = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(width, height))
    pdf.setTitle(report_title)

    pdf.setFillColor(colors.HexColor("#071426"))
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    _draw_brand_logo(
        pdf,
        22,
        height - 55,
        34,
        34,
    )
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(64, height - 30, report_title)

    pdf.setFillColor(colors.HexColor("#B9C6D8"))
    pdf.setFont("Helvetica", 7.5)
    context_y = height - 46
    for line in context_lines[:4]:
        pdf.drawString(64, context_y, line)
        context_y -= 9

    if not report_items:
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(28, height - 90, "Nessun grafico selezionato.")
        pdf.showPage()
        pdf.save()
        output.seek(0)
        return output.getvalue()

    count = len(report_items)
    columns = 1 if count == 1 else 2 if count <= 4 else 3 if count <= 9 else 4
    rows = math.ceil(count / columns)

    left, right, bottom = 24, 24, 22
    top = context_y - 8
    gap_x = gap_y = 10
    cell_w = (width - left - right - gap_x * (columns - 1)) / columns
    cell_h = (top - bottom - gap_y * (rows - 1)) / rows

    for idx, item in enumerate(report_items):
        row = idx // columns
        col = idx % columns
        x = left + col * (cell_w + gap_x)
        y = top - (row + 1) * cell_h - row * gap_y

        pdf.setFillColor(colors.HexColor("#13263D"))
        pdf.roundRect(x, y, cell_w, cell_h, 6, stroke=0, fill=1)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 8.5 if count <= 6 else 7.2)
        pdf.drawString(x + 8, y + cell_h - 15, str(item["title"])[:48])

        try:
            fig = pio.from_json(item["figure_json"])
            fig.update_layout(
                paper_bgcolor="#FFFFFF",
                plot_bgcolor="#FFFFFF",
                font=dict(color="#071426"),
                margin=dict(l=35, r=20, t=20, b=30),
                showlegend=(count <= 6),
            )
            image_bytes = pio.to_image(
                fig,
                format="png",
                width=max(500, int(cell_w * 2.1)),
                height=max(340, int((cell_h - 20) * 2.1)),
                scale=1,
                engine="kaleido",
            )
            pdf.drawImage(
                ImageReader(BytesIO(image_bytes)),
                x + 5,
                y + 5,
                width=cell_w - 10,
                height=cell_h - 24,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
        except Exception as exc:
            pdf.setFillColor(colors.HexColor("#FF8A8A"))
            pdf.setFont("Helvetica-Bold", 8)
            pdf.drawString(x + 8, y + cell_h / 2, "Grafico non disponibile")
            pdf.setFont("Helvetica", 6)
            pdf.drawString(
                x + 8,
                y + cell_h / 2 - 10,
                str(exc).replace("\n", " ")[:80],
            )

    pdf.setFillColor(colors.HexColor("#B9C6D8"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(
        24,
        10,
        "Performance Analysis System | Hellas Verona FC",
    )
    pdf.drawRightString(
        width - 24,
        10,
        f"{count} grafici · A4 orizzontale",
    )
    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()



def _format_session_value(
    value: float,
    decimals: int,
    format_type: str,
) -> str:
    if value is None:
        return "N/D"

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return "N/D"

    if numeric != numeric:
        return "N/D"

    if format_type == "duration":
        total_seconds = max(0, int(round(numeric)))
        minutes, seconds = divmod(total_seconds, 60)
        return f"{minutes:02d}:{seconds:02d}"

    return f"{numeric:.{decimals}f}"



def build_session_report_pdf(
    session_data,
    selected_metrics: list[str],
    metric_specs: dict[str, dict[str, Any]],
    report_title: str,
    session_context: dict[str, str],
    different_training_data=None,
    target_data=None,
    target_label: str = "Target",
    summary_mode: str = "team_average",
    summary_label: str | None = None,
    summary_average_metrics: set[str] | None = None,
    percentage_data=None,
    percentage_label: str = "Match",
    percentage_labels: dict[str, str] | None = None,
    fit_rows_to_page: bool = False,
    entity_label: str = "PLAYER",
) -> bytes:
    """Professional Session Report in una sola pagina A4 orizzontale."""
    from reportlab.lib.pagesizes import A4

    output = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(page_width, page_height))
    pdf.setTitle(report_title)

    data = session_data.copy()
    different_data = (
        different_training_data.copy()
        if different_training_data is not None
        else pd.DataFrame()
    )

    if "Athlete" not in data.columns and not data.empty:
        raise ValueError("Colonna Athlete non presente.")

    if not data.empty:
        data = data.sort_values("Athlete").reset_index(drop=True)
    if not different_data.empty:
        if "Athlete" not in different_data.columns:
            raise ValueError("Different Training senza colonna Athlete.")
        different_data = (
            different_data.sort_values("Athlete")
            .reset_index(drop=True)
        )

    preferred_order = [
        "Duration (min)",
        "Distance (m)",
        "Relative Distance (m/min)",
        "MPE Rec Avg Time (s)",
        "Acc Events (n°)",
        "Dec Events (n°)",
        "Distance 19.8-25.2 km/h (m)",
        "Distance >25.2 km/h (m)",
        "High Intensity Running (m)",
        "Speed Events (n°)",
        "Max Speed (km/h)",
        "Anaerobic Threshold Zone (mm:ss)",
        "High Intensity Training (mm:ss)",
        "RPE",
    ]
    selected_set = set(selected_metrics)
    selected_metrics = [
        name for name in preferred_order
        if name in selected_set
        and name in metric_specs
        and (
            metric_specs[name]["column"] in data.columns
            or metric_specs[name]["column"] in different_data.columns
        )
    ]
    if not selected_metrics:
        raise ValueError("Nessuna metrica disponibile.")

    compact_metrics = {
        "Duration (min)",
        "RPE",
    }
    weights = {
        "Duration (min)": 0.58,
        "Distance (m)": 1.00,
        "Relative Distance (m/min)": 1.00,
        "MPE Rec Avg Time (s)": 1.00,
        "High Intensity Running (m)": 1.00,
        "Anaerobic Threshold Zone (mm:ss)": 1.00,
        "High Intensity Training (mm:ss)": 1.00,
        "Acc Events (n°)": 1.00,
        "Dec Events (n°)": 1.00,
        "Distance 19.8-25.2 km/h (m)": 1.00,
        "Distance >25.2 km/h (m)": 1.00,
        "Speed Events (n°)": 1.00,
        "Max Speed (km/h)": 1.00,
        "RPE": 0.58,
    }
    labels = {
        "Duration (min)": ("DURATION", "min"),
        "Distance (m)": ("DISTANCE", "m"),
        "Relative Distance (m/min)": (
            "RELATIVE DISTANCE",
            "m/min",
        ),
        "MPE Rec Avg Time (s)": (
            "MPE REC AVG TIME",
            "s",
        ),
        "High Intensity Running (m)": (
            "HIGH INTENSITY RUNNING",
            "m",
        ),
        "Anaerobic Threshold Zone (mm:ss)": (
            "ANAEROBIC THRESHOLD",
            "mm:ss",
        ),
        "High Intensity Training (mm:ss)": (
            "HIGH INTENSITY TRAINING",
            "mm:ss",
        ),
        "Acc Events (n°)": ("ACC EVENTS", "n"),
        "Dec Events (n°)": ("DEC EVENTS", "n"),
        "Distance 19.8-25.2 km/h (m)": (
            "DISTANCE 19.8-25.2",
            "m",
        ),
        "Distance >25.2 km/h (m)": (
            "DISTANCE >25.2",
            "m",
        ),
        "Speed Events (n°)": ("SPEED EVENTS", "n"),
        "Max Speed (km/h)": ("MAX SPEED", "km/h"),
        "RPE": ("RPE", ""),
    }

    # Background and compact header.
    pdf.setFillColor(colors.white)
    pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)

    band_h = 48
    pdf.setFillColor(colors.HexColor("#071426"))
    pdf.rect(0, page_height - band_h, page_width, band_h, stroke=0, fill=1)

    _draw_brand_logo(
        pdf,
        10,
        page_height - 44,
        34,
        34,
    )

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14.5)
    pdf.drawString(50, page_height - 31, report_title)

    context = " | ".join([
        session_context.get("date", "N/D"),
        session_context.get("match_day", "N/D"),
        session_context.get("cycle", "N/D"),
        session_context.get("drill", "N/D"),
        session_context.get("time_of_day", "N/D"),
    ])
    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#D7E0EC"))
    pdf.drawRightString(page_width - 16, page_height - 29, context)

    # Layout.
    left = 12
    right = 12
    bottom = 16
    top_y = page_height - band_h - 5
    player_w = 93
    header_h = 27
    metric_total_w = page_width - left - right - player_w
    total_weight = sum(weights[m] for m in selected_metrics)
    widths = {
        m: metric_total_w * weights[m] / total_weight
        for m in selected_metrics
    }

    team_average_rows = 1.35
    team_separator_rows = 0.45
    different_separator_rows = 0.55 if not different_data.empty else 0
    extra_rows = len(different_data) + 1 if not different_data.empty else 0
    total_rows = (
        len(data)
        + team_average_rows
        + team_separator_rows
        + different_separator_rows
        + extra_rows
    )
    available_table_height = top_y - bottom - header_h
    calculated_row_h = (
        available_table_height
        / max(1, total_rows)
    )

    # Il Forecast usa tutta l'altezza disponibile anche con pochi drill.
    # Gli altri report mantengono un limite più compatto.
    max_row_height = (
        62.0
        if fit_rows_to_page and entity_label == "DRILL"
        else 31.0
    )
    row_h = max(
        12.0,
        min(max_row_height, calculated_row_h),
    )

    player_font = (
        6.2 if row_h < 15
        else 7.2 if row_h < 22
        else 8.2 if row_h < 34
        else 9.2
    )
    value_font = (
        5.8 if row_h < 15
        else 6.8 if row_h < 22
        else 7.7 if row_h < 34
        else 8.7
    )

    means, maxima, summary_values = {}, {}, {}
    average_metrics = summary_average_metrics or set()

    for metric in selected_metrics:
        col = metric_specs[metric]["column"]
        main_vals = (
            pd.to_numeric(data[col], errors="coerce").dropna()
            if col in data.columns
            else pd.Series(dtype="float64")
        )
        diff_vals = (
            pd.to_numeric(different_data[col], errors="coerce").dropna()
            if col in different_data.columns
            else pd.Series(dtype="float64")
        )

        means[metric] = (
            float(main_vals.mean())
            if not main_vals.empty
            else float("nan")
        )

        if main_vals.empty:
            summary_values[metric] = float("nan")
        elif (
            summary_mode == "match_total"
            and metric not in average_metrics
        ):
            summary_values[metric] = float(main_vals.sum())
        else:
            summary_values[metric] = float(main_vals.mean())

        all_vals = pd.concat(
            [main_vals, diff_vals],
            ignore_index=True,
        )
        maxima[metric] = (
            float(all_vals.max())
            if not all_vals.empty
            else 0.0
        )

    percentage_lookup = pd.DataFrame()
    if percentage_data is not None:
        percentage_lookup = percentage_data.copy()
        if (
            not percentage_lookup.empty
            and "Athlete" in percentage_lookup.columns
        ):
            percentage_lookup = percentage_lookup.set_index(
                "Athlete"
            )

    # Column headers.
    y = top_y
    pdf.setFillColor(colors.HexColor("#13263D"))
    pdf.rect(left, y - header_h, player_w, header_h, stroke=0, fill=1)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 7)
    pdf.drawString(left + 4, y - 16, entity_label)

    x_positions = {}
    x = left + player_w
    for metric in selected_metrics:
        w = widths[metric]
        x_positions[metric] = x
        if metric in compact_metrics:
            color = "#263B52"
        elif metric == "Distance (m)":
            color = metric_specs["Acc Events (n°)"].get(
                "color",
                "#54A24B",
            )
        elif metric == "Acc Events (n°)":
            color = metric_specs["Distance (m)"].get(
                "color",
                "#4C78A8",
            )
        else:
            color = metric_specs[metric].get(
                "color",
                "#4C78A8",
            )

        pdf.setFillColor(colors.HexColor(color))
        pdf.rect(x, y - header_h, w, header_h, stroke=0, fill=1)

        short, unit = labels[metric]

        # Wrapping compatto dei nomi completi.
        label_lines = {
            "DURATION": ["DURATION"],
            "DISTANCE": ["DISTANCE"],
            "RELATIVE DISTANCE": ["RELATIVE", "DISTANCE"],
            "MPE REC AVG TIME": ["MPE REC", "AVG TIME"],
            "HIGH INTENSITY RUNNING": ["HIGH INTENSITY", "RUNNING"],
            "ANAEROBIC THRESHOLD": ["ANAEROBIC", "THRESHOLD"],
            "HIGH INTENSITY TRAINING": ["HIGH INTENSITY", "TRAINING"],
            "ACC EVENTS": ["ACC EVENTS"],
            "DEC EVENTS": ["DEC EVENTS"],
            "DISTANCE 19.8-25.2": ["DISTANCE", "19.8-25.2"],
            "DISTANCE >25.2": ["DISTANCE", ">25.2"],
            "SPEED EVENTS": ["SPEED EVENTS"],
            "MAX SPEED": ["MAX SPEED"],
            "RPE": ["RPE"],
        }.get(short, [short])

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 5.7)

        if len(label_lines) == 1:
            pdf.drawCentredString(
                x + w / 2,
                y - 11,
                label_lines[0],
            )
            unit_y = y - 20
        else:
            pdf.drawCentredString(
                x + w / 2,
                y - 8,
                label_lines[0],
            )
            pdf.drawCentredString(
                x + w / 2,
                y - 15,
                label_lines[1],
            )
            unit_y = y - 23

        if unit:
            pdf.setFillColor(colors.HexColor("#E1E7EE"))
            pdf.setFont("Helvetica", 4.9)
            pdf.drawCentredString(
                x + w / 2,
                unit_y,
                unit,
            )

        x += w

    def draw_metric_cell(
        metric,
        value,
        current_y,
        team=False,
        cell_row_h=None,
        show_mean_line=True,
        target_value=None,
        percentage_value=None,
    ):
        x = x_positions[metric]
        w = widths[metric]
        spec = metric_specs[metric]
        active_row_h = cell_row_h or row_h

        report_color = spec.get("color", "#4C78A8")
        if metric == "Distance (m)":
            report_color = metric_specs["Acc Events (n°)"].get(
                "color",
                "#54A24B",
            )
        elif metric == "Acc Events (n°)":
            report_color = metric_specs["Distance (m)"].get(
                "color",
                "#4C78A8",
            )
        formatted = _format_session_value(
            value,
            int(spec.get("decimals", 0)),
            str(spec.get("format", "number")),
        )
        if metric == "RPE" and formatted.endswith(".0"):
            formatted = formatted[:-2]

        if metric not in compact_metrics:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = float("nan")

            max_v = maxima[metric]
            mean_v = means[metric]
            cell_l, cell_r = x + 1.5, x + w - 1.5
            cell_w = max(1, cell_r - cell_l)
            bar_y = current_y - active_row_h + 2.0
            bar_h = max(3.0, active_row_h - 4.0)

            if numeric == numeric and max_v > 0:
                bw = cell_w * max(
                    0.0,
                    min(1.0, numeric / max_v),
                )
                hex_color = report_color
                rgb = [
                    int(hex_color[i:i + 2], 16) / 255
                    for i in (1, 3, 5)
                ]

                # La Team Average usa una barra leggermente più intensa.
                bar_alpha = 0.52 if team else 0.34
                pdf.setFillColor(
                    colors.Color(*rgb, alpha=bar_alpha)
                )
                pdf.rect(
                    cell_l,
                    bar_y,
                    bw,
                    bar_h,
                    stroke=0,
                    fill=1,
                )

            # La linea rossa rappresenta la Team Average:
            # non serve dentro la riga Team Average stessa.
            if (
                show_mean_line
                and not team
                and mean_v == mean_v
                and max_v > 0
            ):
                mean_x = cell_l + cell_w * max(
                    0.0,
                    min(1.0, mean_v / max_v),
                )
                pdf.setStrokeColor(colors.HexColor("#D62839"))
                pdf.setLineWidth(0.7)
                pdf.line(
                    mean_x,
                    bar_y,
                    mean_x,
                    bar_y + bar_h,
                )

            if (
                target_value is not None
                and pd.notna(target_value)
                and max_v > 0
            ):
                target_x = cell_l + cell_w * max(
                    0.0,
                    min(1.0, float(target_value) / max_v),
                )
                pdf.setStrokeColor(colors.HexColor("#D62839"))
                pdf.setLineWidth(1.1)
                pdf.line(
                    target_x,
                    bar_y,
                    target_x,
                    bar_y + bar_h,
                )

        pdf.setFillColor(colors.HexColor("#071426"))
        pdf.setFont(
            "Helvetica-Bold" if team else "Helvetica",
            8.0 if team else value_font,
        )

        has_percentage = (
            percentage_value is not None
            and pd.notna(percentage_value)
        )

        value_y = (
            current_y - active_row_h
            + active_row_h * (0.54 if has_percentage else 0.35)
        )
        pdf.drawCentredString(
            x + w / 2,
            value_y,
            formatted,
        )

        if has_percentage:
            metric_percentage_label = (
                (percentage_labels or {}).get(
                    metric,
                    percentage_label,
                )
            )

            pdf.setFillColor(colors.HexColor("#53657A"))
            pdf.setFont(
                "Helvetica-Bold" if team else "Helvetica",
                6.5 if team else max(5.4, value_font - 1.0),
            )
            pdf.drawCentredString(
                x + w / 2,
                current_y - active_row_h + active_row_h * 0.20,
                (
                    f"{float(percentage_value):.0f}%"
                    + (
                        f" {metric_percentage_label}"
                        if metric_percentage_label
                        else ""
                    )
                ),
            )
        pdf.setStrokeColor(colors.HexColor("#D4DCE5"))
        pdf.setLineWidth(0.25)
        pdf.rect(
            x,
            current_y - active_row_h,
            w,
            active_row_h,
            stroke=1,
            fill=0,
        )

    # Summary row.
    current_y = y - header_h
    team_row_h = row_h * 1.20

    # Sfondo bianco per tutta la riga.
    pdf.setFillColor(colors.white)
    pdf.rect(
        left,
        current_y - team_row_h,
        page_width - left - right,
        team_row_h,
        stroke=0,
        fill=1,
    )

    # Solo la prima cella resta gialla.
    pdf.setFillColor(colors.HexColor("#F4C430"))
    pdf.rect(
        left,
        current_y - team_row_h,
        player_w,
        team_row_h,
        stroke=0,
        fill=1,
    )

    pdf.setFillColor(colors.HexColor("#071426"))
    pdf.setFont("Helvetica-Bold", 8.4)
    pdf.drawString(
        left + 4,
        current_y - team_row_h + team_row_h * 0.37,
        (
            summary_label
            or (
                "MATCH TOTAL"
                if summary_mode == "match_total"
                else "TEAM AVERAGE"
            )
        ),
    )

    pdf.setStrokeColor(colors.HexColor("#D4DCE5"))
    pdf.setLineWidth(0.25)
    pdf.rect(
        left,
        current_y - team_row_h,
        player_w,
        team_row_h,
        stroke=1,
        fill=0,
    )

    for metric in selected_metrics:
        summary_pct = None
        if not percentage_lookup.empty:
            summary_name = (
                summary_label
                or (
                    "MATCH TOTAL"
                    if summary_mode == "match_total"
                    else "TEAM AVERAGE"
                )
            )
            lookup_name = (
                "TEAM AVERAGE"
                if summary_name == "TEAM AVERAGE"
                else summary_name
            )
            pct_column = (
                f"{metric_specs[metric]['column']}__match_pct"
            )
            if (
                lookup_name in percentage_lookup.index
                and pct_column in percentage_lookup.columns
            ):
                summary_pct = percentage_lookup.loc[
                    lookup_name,
                    pct_column,
                ]

        draw_metric_cell(
            metric,
            summary_values[metric],
            current_y,
            team=True,
            cell_row_h=team_row_h,
            show_mean_line=False,
            percentage_value=summary_pct,
        )

    current_y -= team_row_h

    # Piccolo spazio bianco tra Team Average e giocatori.
    team_gap = row_h * 0.25
    pdf.setFillColor(colors.white)
    pdf.rect(
        left,
        current_y - team_gap,
        page_width - left - right,
        team_gap,
        stroke=0,
        fill=1,
    )
    current_y -= team_gap

    # Players.
    for idx, (_, row) in enumerate(data.iterrows()):
        fill = "#FFFFFF" if idx % 2 == 0 else "#EFF3F7"
        pdf.setFillColor(colors.HexColor(fill))
        pdf.rect(left, current_y - row_h, page_width - left - right, row_h, stroke=0, fill=1)

        pdf.setFillColor(colors.HexColor("#071426"))
        pdf.setFont("Helvetica-Bold", player_font)
        pdf.drawString(
            left + 4,
            current_y - row_h + row_h * 0.34,
            str(row.get("Athlete", "N/D"))[:21],
        )
        pdf.setStrokeColor(colors.HexColor("#D4DCE5"))
        pdf.setLineWidth(0.25)
        pdf.rect(left, current_y - row_h, player_w, row_h, stroke=1, fill=0)

        athlete_name = str(row.get("Athlete", ""))
        target_row = pd.DataFrame()
        if target_data is not None and not target_data.empty:
            target_row = target_data[
                target_data["Athlete"].astype(str).eq(athlete_name)
            ]

        for metric in selected_metrics:
            metric_column = metric_specs[metric]["column"]
            target_value = (
                target_row.iloc[0].get(metric_column)
                if not target_row.empty
                else None
            )
            percentage_value = None
            if (
                not percentage_lookup.empty
                and athlete_name in percentage_lookup.index
            ):
                pct_column = f"{metric_column}__match_pct"
                if pct_column in percentage_lookup.columns:
                    percentage_value = percentage_lookup.loc[
                        athlete_name,
                        pct_column,
                    ]

            draw_metric_cell(
                metric,
                row.get(metric_column),
                current_y,
                show_mean_line=(target_data is None),
                target_value=target_value,
                percentage_value=percentage_value,
            )
        current_y -= row_h

    # Different Training: excluded from Team Average.
    if not different_data.empty:
        different_gap = row_h * 0.55
        pdf.setFillColor(colors.white)
        pdf.rect(
            left,
            current_y - different_gap,
            page_width - left - right,
            different_gap,
            stroke=0,
            fill=1,
        )
        current_y -= different_gap

        pdf.setFillColor(colors.HexColor("#263B52"))
        pdf.rect(
            left,
            current_y - row_h,
            page_width - left - right,
            row_h,
            stroke=0,
            fill=1,
        )
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 6.5)
        pdf.drawString(
            left + 4,
            current_y - row_h + row_h * 0.34,
            "DIFFERENT TRAINING - EXCLUDED FROM TEAM AVERAGE",
        )
        current_y -= row_h

        for idx, (_, row) in enumerate(different_data.iterrows()):
            fill = "#FFF8DB" if idx % 2 == 0 else "#F8EDC1"
            pdf.setFillColor(colors.HexColor(fill))
            pdf.rect(
                left,
                current_y - row_h,
                page_width - left - right,
                row_h,
                stroke=0,
                fill=1,
            )
            pdf.setFillColor(colors.HexColor("#071426"))
            pdf.setFont("Helvetica-Bold", player_font)
            pdf.drawString(
                left + 4,
                current_y - row_h + row_h * 0.34,
                str(row.get("Athlete", "N/D"))[:21],
            )
            pdf.setStrokeColor(colors.HexColor("#D4DCE5"))
            pdf.setLineWidth(0.25)
            pdf.rect(
                left,
                current_y - row_h,
                player_w,
                row_h,
                stroke=1,
                fill=0,
            )
            for metric in selected_metrics:
                col = metric_specs[metric]["column"]
                value = row.get(col) if col in different_data.columns else float("nan")
                draw_metric_cell(
                    metric,
                    value,
                    current_y,
                    show_mean_line=False,
                )
            current_y -= row_h

    # Footer.
    pdf.setFillColor(colors.HexColor("#5C6874"))
    pdf.setFont("Helvetica", 5.5)
    pdf.drawString(
        left,
        6,
        (
            f"Colored bar = individual value | Red line = {target_label}"
            if target_data is not None
            else "Colored bar = individual value | Red line = Team Average"
        ),
    )
    pdf.drawRightString(
        page_width - right,
        6,
        (
            f"{len(data)} drills - A4 landscape"
            if entity_label == "DRILL"
            else f"{len(data)} players - A4 landscape"
        ),
    )

    # Firma sulla stessa pagina: nessuna pagina finale vuota.
    pdf.setFillColor(colors.HexColor("#8A98A8"))
    pdf.setFont("Helvetica", 5.8)
    pdf.drawCentredString(
        page_width / 2,
        6,
        "Performance Analysis System | Hellas Verona FC",
    )

    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()



def build_forecast_report_pdf(
    forecast_data,
    report_title: str,
    role: str,
    report_date: str,
    metric_specs: dict[str, dict[str, Any]],
) -> bytes:
    """
    Forecast Report con la stessa struttura, grafica e logica
    del Session Report. I drill sostituiscono gli atleti.
    """
    data = forecast_data.copy()

    if data.empty:
        raise ValueError("Nessun drill disponibile nel Forecast.")

    report_data = data.rename(
        columns={"Drill": "Athlete"}
    ).copy()

    session_metric_specs = {
        "Duration (min)": {
            "column": "Duration (min)",
            "color": "#263B52",
            "unit": "min",
            "decimals": 0,
            "format": "number",
        },
    }

    for metric_name, meta in metric_specs.items():
        session_metric_specs[metric_name] = {
            "column": metric_name,
            "color": meta.get("color", "#4C78A8"),
            "unit": meta.get("unit", ""),
            "decimals": int(meta.get("decimals", 0)),
            "format": "number",
        }

    selected_metrics = [
        "Duration (min)",
        *list(metric_specs.keys()),
    ]

    return build_session_report_pdf(
        session_data=report_data,
        selected_metrics=selected_metrics,
        metric_specs=session_metric_specs,
        report_title=report_title,
        session_context={
            "date": report_date,
            "match_day": f"ROLE: {role}",
            "cycle": "",
            "drill": "FORECAST",
            "time_of_day": "",
        },
        different_training_data=None,
        summary_mode="match_total",
        summary_label="TOTAL",
        summary_average_metrics=set(),
        fit_rows_to_page=True,
        entity_label="DRILL",
    )

