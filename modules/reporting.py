from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any
import re

import pandas as pd

import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth


# Opacità dedicate ai report tabellari: stessa palette PAS, ma colori
# più pieni e leggibili in PDF/stampa rispetto alla visualizzazione web.
REPORT_PLAYER_BAR_ALPHA = 0.72
REPORT_SUMMARY_BAR_ALPHA = 0.88



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




def _teams_logo_dir() -> Path:
    return (
        Path(__file__).resolve().parent.parent
        / "assets"
        / "teams"
    )


def _normalize_team_name(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip()).upper()
    aliases = {
        "INTER": "INTERNAZIONALE",
        "INTER MILAN": "INTERNAZIONALE",
        "FC INTERNAZIONALE": "INTERNAZIONALE",
        "AC MILAN": "MILAN",
        "AS ROMA": "ROMA",
        "SS LAZIO": "LAZIO",
        "HELLAS VERONA": "HELLAS VERONA",
        "VERONA": "HELLAS VERONA",
    }
    return aliases.get(text, text)


def _team_logo_path(team_name: str) -> Path | None:
    normalized = _normalize_team_name(team_name)
    if normalized == "HELLAS VERONA":
        path = _brand_logo_path()
        return path if path.exists() else None

    files = {
        path.stem.upper(): path
        for path in _teams_logo_dir().glob("*.png")
    }
    path = files.get(normalized)
    return path if path and path.exists() else None


def _resolve_match_header(match_label: str) -> dict[str, Any] | None:
    """Resolve opponent, venue and visual team order from a PAS match label."""
    label = str(match_label or "").strip()
    # La Match Analysis antepone normalmente la data: prendiamo l'ultimo
    # segmento dopo il separatore e supportiamo anche il prefisso storico MD.
    match_part = re.split(r"\s*[·|]\s*", label)[-1].strip()
    match = re.search(
        r"(?:MD\s+)?(.+?)\s*\(([HA])\)\s*$",
        match_part,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    opponent = re.sub(r"\s+", " ", match.group(1)).strip()
    venue = match.group(2).upper()
    hellas = {
        "name": "HELLAS VERONA",
        "logo": _team_logo_path("HELLAS VERONA"),
    }
    rival = {
        "name": opponent.upper(),
        "logo": _team_logo_path(opponent),
    }
    teams = [hellas, rival] if venue == "H" else [rival, hellas]
    return {
        "opponent": opponent.upper(),
        "venue": venue,
        "teams": teams,
    }


def _draw_team_logo_or_name(
    pdf,
    team: dict[str, Any],
    x: float,
    y: float,
    width: float,
    height: float,
) -> None:
    path = team.get("logo")
    if path:
        try:
            # Badge chiaro dietro lo stemma: rende visibili anche loghi
            # neri/scuri (es. Juventus) sull'header blu notte del report.
            pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.96))
            pdf.setStrokeColor(colors.HexColor("#D7E0EC"))
            pdf.setLineWidth(0.45)
            pdf.roundRect(
                x - 1.5,
                y - 1.5,
                width + 3.0,
                height + 3.0,
                3.2,
                stroke=1,
                fill=1,
            )
            pdf.drawImage(
                ImageReader(str(path)),
                x + 1.2,
                y + 1.2,
                width=width - 2.4,
                height=height - 2.4,
                preserveAspectRatio=True,
                anchor="c",
                mask="auto",
            )
            return
        except Exception:
            pass

    name = str(team.get("name", "TEAM"))
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 5.5)
    pdf.drawCentredString(x + width / 2, y + height / 2 - 2, name[:18])


def _draw_match_report_header(
    pdf,
    page_width: float,
    page_height: float,
    report_title: str,
    match_label: str,
    context: str,
) -> bool:
    resolved = _resolve_match_header(match_label)
    if not resolved:
        return False

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 14.5)
    pdf.drawString(16, page_height - 31, report_title)

    left_team, right_team = resolved["teams"]
    logo_size = 31
    left_x = 154
    right_x = 226
    logo_y = page_height - 41
    _draw_team_logo_or_name(
        pdf, left_team, left_x, logo_y, logo_size, logo_size
    )
    _draw_team_logo_or_name(
        pdf, right_team, right_x, logo_y, logo_size, logo_size
    )

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 11)
    pdf.drawCentredString(205, page_height - 30, "VS")

    pdf.setFont("Helvetica", 7)
    pdf.setFillColor(colors.HexColor("#D7E0EC"))
    pdf.drawRightString(page_width - 16, page_height - 29, context)
    return True

def build_pdf_report(
    report_items: list[dict[str, Any]],
    report_title: str,
    context_lines: list[str],
    charts_per_page: int = 4,
) -> bytes:
    """Create a printable landscape A4 PDF with at most four charts per page."""
    import math

    charts_per_page = max(1, min(int(charts_per_page), 4))
    output = BytesIO()
    width, height = landscape(A4)
    pdf = canvas.Canvas(output, pagesize=(width, height))
    pdf.setTitle(report_title)

    if not report_items:
        _draw_chart_report_page_header(
            pdf, width, height, report_title, context_lines, 1, 1
        )
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(28, height - 90, "Nessun grafico selezionato.")
        _draw_chart_report_footer(pdf, width, 0, 1, 1)
        pdf.showPage()
        pdf.save()
        output.seek(0)
        return output.getvalue()

    pages = [
        report_items[index:index + charts_per_page]
        for index in range(0, len(report_items), charts_per_page)
    ]
    total_pages = len(pages)

    for page_number, page_items in enumerate(pages, start=1):
        context_y = _draw_chart_report_page_header(
            pdf,
            width,
            height,
            report_title,
            context_lines,
            page_number,
            total_pages,
        )
        count = len(page_items)
        columns = 1 if count == 1 else 2
        rows = math.ceil(count / columns)

        left, right, bottom = 24, 24, 24
        top = context_y - 8
        gap_x = gap_y = 12
        cell_w = (width - left - right - gap_x * (columns - 1)) / columns
        cell_h = (top - bottom - gap_y * (rows - 1)) / rows

        for idx, item in enumerate(page_items):
            row = idx // columns
            col = idx % columns
            x = left + col * (cell_w + gap_x)
            y = top - (row + 1) * cell_h - row * gap_y

            pdf.setFillColor(colors.HexColor("#13263D"))
            pdf.roundRect(x, y, cell_w, cell_h, 6, stroke=0, fill=1)
            pdf.setFillColor(colors.white)
            pdf.setFont("Helvetica-Bold", 9 if count <= 2 else 8.2)
            pdf.drawString(x + 8, y + cell_h - 15, str(item["title"])[:62])

            try:
                fig = pio.from_json(item["figure_json"])
                fig.update_layout(
                    paper_bgcolor="#FFFFFF",
                    plot_bgcolor="#FFFFFF",
                    font=dict(color="#071426"),
                    margin=dict(l=45, r=24, t=28, b=42),
                    showlegend=True,
                )
                image_bytes = pio.to_image(
                    fig,
                    format="png",
                    width=max(760, int(cell_w * 2.4)),
                    height=max(460, int((cell_h - 24) * 2.4)),
                    scale=1,
                    engine="kaleido",
                )
                pdf.drawImage(
                    ImageReader(BytesIO(image_bytes)),
                    x + 5,
                    y + 5,
                    width=cell_w - 10,
                    height=cell_h - 25,
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
                    str(exc).replace("\n", " ")[:90],
                )

        _draw_chart_report_footer(
            pdf, width, len(report_items), page_number, total_pages
        )
        pdf.showPage()

    pdf.save()
    output.seek(0)
    return output.getvalue()


def _draw_chart_report_page_header(
    pdf,
    width: float,
    height: float,
    report_title: str,
    context_lines: list[str],
    page_number: int,
    total_pages: int,
) -> float:
    pdf.setFillColor(colors.HexColor("#071426"))
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    _draw_brand_logo(pdf, 22, height - 55, 34, 34)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(64, height - 30, report_title)
    pdf.setFont("Helvetica", 7.5)
    pdf.setFillColor(colors.HexColor("#B9C6D8"))
    pdf.drawRightString(
        width - 24, height - 30, f"Pagina {page_number}/{total_pages}"
    )
    context_y = height - 46
    for line in context_lines[:4]:
        pdf.drawString(64, context_y, str(line)[:150])
        context_y -= 9
    return context_y


def _draw_chart_report_footer(
    pdf,
    width: float,
    chart_count: int,
    page_number: int,
    total_pages: int,
) -> None:
    pdf.setFillColor(colors.HexColor("#B9C6D8"))
    pdf.setFont("Helvetica", 7)
    pdf.drawString(24, 10, "Performance Analysis System | Hellas Verona FC")
    pdf.drawRightString(
        width - 24,
        10,
        f"{chart_count} grafici | max 4 per pagina | {page_number}/{total_pages}",
    )



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



def _report_metric_scale_max(
    main_values,
    different_values=None,
    target_values=None,
    headroom: float = 1.10,
) -> float:
    """Return a common zero-based report scale including values and targets."""
    series = []
    for values in (main_values, different_values, target_values):
        if values is None:
            continue
        numeric = pd.to_numeric(values, errors="coerce").dropna()
        if not numeric.empty:
            series.append(numeric)
    if not series:
        return 0.0
    maximum = float(pd.concat(series, ignore_index=True).max())
    if maximum <= 0:
        return 0.0
    return maximum * max(1.0, float(headroom))


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
    match_header_label: str | None = None,
    fit_rows_to_page: bool = False,
    entity_label: str = "PLAYER",
    group_column: str | None = None,
    group_order: list[str] | None = None,
    show_group_prefix: bool = False,
    show_group_separator: bool = False,
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
        if group_column and group_column in data.columns:
            normalized_group = data[group_column].astype(str).str.upper()
            order = [str(value).upper() for value in (group_order or [])]
            rank = {value: index for index, value in enumerate(order)}
            data = data.assign(
                _report_group=normalized_group,
                _report_group_rank=normalized_group.map(rank).fillna(len(rank)),
            ).sort_values(["_report_group_rank", "Athlete"]).reset_index(drop=True)
        else:
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

    context = " | ".join([
        session_context.get("date", "N/D"),
        session_context.get("match_day", "N/D"),
        session_context.get("cycle", "N/D"),
        session_context.get("drill", "N/D"),
        session_context.get("time_of_day", "N/D"),
    ])

    match_header_drawn = False
    if match_header_label:
        match_header_drawn = _draw_match_report_header(
            pdf,
            page_width,
            page_height,
            report_title,
            match_header_label,
            context,
        )

    if not match_header_drawn:
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
        pdf.setFont("Helvetica", 7)
        pdf.setFillColor(colors.HexColor("#D7E0EC"))
        pdf.drawRightString(page_width - 16, page_height - 29, context)

    # Layout.
    left = 12
    right = 12
    bottom = 16
    top_y = page_height - band_h - 5
    player_w = 108
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

    means, minima, maxima, summary_values = {}, {}, {}, {}
    average_metrics = summary_average_metrics or set()
    metric_scale_minima = {
        "Relative Distance (m/min)": 80.0,
        "MPE Rec Avg Time (s)": 5.0,
    }

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

        target_vals = pd.Series(dtype="float64")
        if (
            target_data is not None
            and not target_data.empty
            and col in target_data.columns
        ):
            target_vals = pd.to_numeric(
                target_data[col],
                errors="coerce",
            ).dropna()

        # Unica scala zero-based per metrica: include sia i valori reali
        # sia i target individuali, con un piccolo margine finale.
        # In questo modo la distanza valore-target resta proporzionale
        # anche quando il target è maggiore del valore osservato.
        minima[metric] = float(metric_scale_minima.get(metric, 0.0))
        highest_value = _report_metric_scale_max(
            main_vals,
            diff_vals,
            target_vals,
            headroom=1.0,
        )
        # Il limite superiore resta vicino al maggiore tra valore osservato
        # e target. Il margine è il 5% dell'intervallo utile sopra il minimo
        # specifico della metrica, con almeno una unità di respiro.
        useful_span = max(0.0, highest_value - minima[metric])
        scale_padding = max(1.0, useful_span * 0.05)
        maxima[metric] = max(
            highest_value + scale_padding,
            minima[metric] + 1.0,
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
        report_decimals = (
            0
            if metric in {
                "Relative Distance (m/min)",
                "MPE Rec Avg Time (s)",
            }
            else int(spec.get("decimals", 0))
        )
        formatted = _format_session_value(
            value,
            report_decimals,
            str(spec.get("format", "number")),
        )
        if metric == "RPE" and formatted.endswith(".0"):
            formatted = formatted[:-2]

        numeric = float("nan")
        max_v = 0.0
        bw = 0.0
        cell_l = x + 1.5

        if metric not in compact_metrics:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                numeric = float("nan")

            min_v = minima[metric]
            max_v = maxima[metric]
            scale_span = max(1e-9, max_v - min_v)
            mean_v = means[metric]
            cell_l, cell_r = x + 1.5, x + w - 1.5
            cell_w = max(1, cell_r - cell_l)
            bar_y = current_y - active_row_h + 2.0
            bar_h = max(3.0, active_row_h - 4.0)

            if numeric == numeric and max_v > min_v:
                if team and summary_mode == "match_total":
                    # TOTAL MATCH è una sintesi numerica: barra piena,
                    # senza confronto su una scala metrica.
                    bw = cell_w
                else:
                    bw = cell_w * max(
                        0.0,
                        min(1.0, (numeric - min_v) / scale_span),
                    )
                hex_color = report_color
                rgb = [
                    int(hex_color[i:i + 2], 16) / 255
                    for i in (1, 3, 5)
                ]

                # Nei report PDF le barre mantengono i colori PAS,
                # ma con opacità più elevata per risultare nitide in stampa.
                bar_alpha = (
                    REPORT_SUMMARY_BAR_ALPHA
                    if team
                    else REPORT_PLAYER_BAR_ALPHA
                )
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
                and max_v > min_v
            ):
                mean_x = cell_l + cell_w * max(
                    0.0,
                    min(1.0, (mean_v - min_v) / scale_span),
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
                and max_v > min_v
            ):
                target_x = cell_l + cell_w * max(
                    0.0,
                    min(
                        1.0,
                        (float(target_value) - min_v) / scale_span,
                    ),
                )
                pdf.setStrokeColor(colors.HexColor("#D62839"))
                pdf.setLineWidth(1.1)
                pdf.line(
                    target_x,
                    bar_y,
                    target_x,
                    bar_y + bar_h,
                )

                # Etichetta compatta del target alla base della linea,
                # posizionata verso sinistra come riferimento visivo.
                target_formatted = _format_session_value(
                    target_value,
                    report_decimals,
                    str(spec.get("format", "number")),
                )
                if metric == "RPE" and target_formatted.endswith(".0"):
                    target_formatted = target_formatted[:-2]
                target_font = 4.2
                target_pad = 1.2
                target_text_w = stringWidth(
                    target_formatted,
                    "Helvetica-Bold",
                    target_font,
                )
                target_label_w = target_text_w + target_pad * 2
                target_label_h = 5.4
                target_label_right = min(
                    cell_r - 0.5,
                    max(cell_l + target_label_w, target_x - 0.8),
                )
                target_label_left = max(
                    cell_l + 0.5,
                    target_label_right - target_label_w,
                )
                target_label_y = bar_y + 0.45
                pdf.setFillColor(colors.Color(1, 1, 1, alpha=0.92))
                pdf.setStrokeColor(colors.HexColor("#D62839"))
                pdf.setLineWidth(0.35)
                pdf.roundRect(
                    target_label_left,
                    target_label_y,
                    max(1.0, target_label_right - target_label_left),
                    target_label_h,
                    1.0,
                    stroke=1,
                    fill=1,
                )
                pdf.setFillColor(colors.HexColor("#A3162B"))
                pdf.setFont("Helvetica-Bold", target_font)
                pdf.drawCentredString(
                    (target_label_left + target_label_right) / 2,
                    target_label_y + 1.25,
                    target_formatted,
                )

        pdf.setFillColor(colors.HexColor("#071426"))
        # TEAM AVERAGE e TOTAL MATCH condividono la stessa gerarchia
        # tipografica: TOTAL MATCH resta il riferimento visivo.
        value_font_size = 10.2 if team else value_font
        value_font_name = "Helvetica-Bold" if team else "Helvetica"

        # Il valore della metrica è centrato nella barra colorata;
        # se la barra è corta il carattere resta invariato e il testo può
        # oltrepassarne i bordi, preservando la leggibilità fra metriche.
        value_center_x = x + w / 2
        if metric not in compact_metrics and numeric == numeric and max_v > min_v:
            value_center_x = cell_l + max(0.0, bw) / 2

        pdf.setFont(value_font_name, value_font_size)

        has_percentage = (
            percentage_value is not None
            and pd.notna(percentage_value)
        )

        value_y = (
            current_y - active_row_h
            + active_row_h * (0.54 if has_percentage else 0.35)
        )
        value_text_width = stringWidth(
            formatted,
            value_font_name,
            value_font_size,
        )
        value_left_bound = cell_l if metric not in compact_metrics else x + 1.5
        value_right_bound = (
            x + w - 1.5 if metric in compact_metrics else cell_r
        )
        value_would_exit_column = (
            value_center_x - value_text_width / 2 < value_left_bound
            or value_center_x + value_text_width / 2 > value_right_bound
        )
        if value_would_exit_column:
            # Solo quando il testo centrato uscirebbe dalla colonna,
            # parte dall'inizio della barra/cella mantenendo il font uniforme.
            pdf.drawString(value_left_bound, value_y, formatted)
        else:
            pdf.drawCentredString(value_center_x, value_y, formatted)

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
            percentage_text = (
                f"{float(percentage_value):.0f}%"
                + (
                    f" {metric_percentage_label}"
                    if metric_percentage_label
                    else ""
                )
            )
            percentage_font_name = "Helvetica-Bold" if team else "Helvetica"
            percentage_font_size = 6.5 if team else max(5.4, value_font - 1.0)
            percentage_text_width = stringWidth(
                percentage_text,
                percentage_font_name,
                percentage_font_size,
            )
            percentage_would_exit_column = (
                value_center_x - percentage_text_width / 2 < value_left_bound
                or value_center_x + percentage_text_width / 2 > value_right_bound
            )
            if percentage_would_exit_column:
                pdf.drawString(
                    value_left_bound,
                    current_y - active_row_h + active_row_h * 0.20,
                    percentage_text,
                )
            else:
                pdf.drawCentredString(
                    value_center_x,
                    current_y - active_row_h + active_row_h * 0.20,
                    percentage_text,
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
                "TOTAL MATCH"
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
                    "TOTAL MATCH"
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
    previous_group = None
    group_label_w = 16 if show_group_prefix and group_column else 0
    group_counts = (
        data["_report_group"].astype(str).str.upper().value_counts().to_dict()
        if group_label_w and "_report_group" in data.columns
        else {}
    )
    group_starts: set[str] = set()
    for idx, (_, row) in enumerate(data.iterrows()):
        current_group = (
            str(row.get("_report_group", row.get(group_column, ""))).upper()
            if group_column
            else ""
        )
        if (
            show_group_separator
            and previous_group is not None
            and current_group != previous_group
        ):
            pdf.setStrokeColor(colors.HexColor("#7E8996"))
            pdf.setLineWidth(2.4)
            pdf.line(left, current_y, page_width - right, current_y)
        fill = "#FFFFFF" if idx % 2 == 0 else "#EFF3F7"
        pdf.setFillColor(colors.HexColor(fill))
        # Non ridisegnare sopra la cella unificata S/NS: l’etichetta di gruppo
        # deve restare visibile e centrata per tutta l’altezza del gruppo.
        row_fill_left = left + group_label_w if group_label_w else left
        pdf.rect(
            row_fill_left,
            current_y - row_h,
            page_width - row_fill_left - right,
            row_h,
            stroke=0,
            fill=1,
        )

        if group_label_w and current_group in {"S", "NS"} and current_group not in group_starts:
            group_height = row_h * int(group_counts.get(current_group, 1))
            group_mid_y = current_y - group_height / 2
            group_font = max(player_font, 8)
            pdf.setFillColor(colors.HexColor("#071426"))
            pdf.setFont("Helvetica-Bold", group_font)
            pdf.drawCentredString(
                left + group_label_w / 2,
                group_mid_y - group_font * 0.34,
                current_group,
            )
            pdf.setStrokeColor(colors.HexColor("#C7CED7"))
            pdf.setLineWidth(0.5)
            pdf.rect(left, current_y - group_height, group_label_w, group_height, stroke=1, fill=0)
            group_starts.add(current_group)

        pdf.setFillColor(colors.HexColor("#071426"))
        athlete_label = str(row.get("Athlete", "N/D"))
        player_left = left + group_label_w
        available_name_width = max(20.0, player_w - group_label_w - 8.0)
        fitted_player_font = player_font
        while (
            fitted_player_font > 5.2
            and stringWidth(athlete_label, "Helvetica-Bold", fitted_player_font)
            > available_name_width
        ):
            fitted_player_font -= 0.2
        pdf.setFont("Helvetica-Bold", fitted_player_font)
        pdf.drawString(
            player_left + 4,
            current_y - row_h + row_h * 0.34,
            athlete_label,
        )
        pdf.setStrokeColor(colors.HexColor("#D4DCE5"))
        pdf.setLineWidth(0.25)
        pdf.rect(player_left, current_y - row_h, player_w - group_label_w, row_h, stroke=1, fill=0)

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
        previous_group = current_group

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



def build_daily_planner_report_pdf(
    planner_date: str,
    day_payload: dict,
    activity_colors: dict[str, str],
) -> bytes:
    """Planner Report su A4 orizzontale."""
    output = BytesIO()
    page_width, page_height = landscape(A4)
    pdf = canvas.Canvas(
        output,
        pagesize=(page_width, page_height),
    )
    pdf.setTitle(f"PLANNER - {planner_date}")

    pdf.setFillColor(colors.HexColor("#071426"))
    pdf.rect(
        0,
        0,
        page_width,
        page_height,
        stroke=0,
        fill=1,
    )

    _draw_brand_logo(
        pdf,
        12,
        page_height - 50,
        36,
        36,
    )

    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(
        56,
        page_height - 25,
        "PLANNER",
    )

    pdf.setFillColor(colors.HexColor("#F4C430"))
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(
        56,
        page_height - 40,
        planner_date,
    )

    participants = day_payload.get("participants", [])
    player_statuses = day_payload.get("player_statuses", {})
    player_notes = day_payload.get("player_notes", {})
    absence_notes = str(
        day_payload.get("absence_notes", "")
    )
    activities = day_payload.get("activities", [])

    pdf.setFillColor(colors.HexColor("#B9C6D8"))
    pdf.setFont("Helvetica", 7)
    pdf.drawRightString(
        page_width - 16,
        page_height - 25,
        f"{len(participants)} partecipanti",
    )

    status_summary = {}
    for status_value in player_statuses.values():
        status_summary[status_value] = (
            status_summary.get(status_value, 0) + 1
        )
    status_text = " · ".join(
        f"{status}: {count}"
        for status, count in status_summary.items()
        if status != "Full Training"
    )
    if status_text:
        pdf.setFillColor(colors.HexColor("#B9C6D8"))
        pdf.setFont("Helvetica", 6.2)
        pdf.drawRightString(
            page_width - 16,
            page_height - 39,
            status_text[:110],
        )

    top = page_height - 60
    bottom = 25
    left = 14
    right = page_width - 14
    available_height = top - bottom

    activity_count = max(1, len(activities))
    gap = 7
    card_height = (
        available_height - gap * (activity_count - 1)
    ) / activity_count
    card_height = max(55, min(125, card_height))

    current_y = top

    if not activities:
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica", 11)
        pdf.drawString(
            left,
            current_y - 30,
            "Nessuna attività inserita.",
        )

    for activity_index, activity in enumerate(activities):
        activity_type = str(
            activity.get("type", "Other")
        )
        activity_color = activity_colors.get(
            activity_type,
            "#8A98A8",
        )
        title = str(activity.get("title", ""))
        start_time = str(
            activity.get("start_time", "")
        )
        activity_participants = activity.get(
            "participants",
            [],
        )
        notes = str(activity.get("notes", ""))
        drills = activity.get("drills", [])

        card_y = current_y - card_height

        pdf.setFillColor(colors.white)
        pdf.roundRect(
            left,
            card_y,
            right - left,
            card_height,
            5,
            stroke=0,
            fill=1,
        )

        pdf.setFillColor(colors.HexColor(activity_color))
        pdf.roundRect(
            left,
            card_y,
            120,
            card_height,
            5,
            stroke=0,
            fill=1,
        )

        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(
            left + 8,
            current_y - 19,
            activity_type[:22],
        )

        pdf.setFont("Helvetica", 7)
        if start_time:
            pdf.drawString(
                left + 8,
                current_y - 32,
                f"Orario: {start_time}",
            )
        pdf.drawString(
            left + 8,
            current_y - 44,
            f"Partecipanti: {len(activity_participants)}",
        )

        content_x = left + 130
        pdf.setFillColor(colors.HexColor("#071426"))
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawString(
            content_x,
            current_y - 18,
            (title or activity_type)[:65],
        )

        content_y = current_y - 34
        if drills:
            total_minutes = sum(
                int(drill.get("duration", 0) or 0)
                for drill in drills
            )
            pdf.setFont("Helvetica-Bold", 7)
            pdf.drawRightString(
                right - 8,
                current_y - 18,
                f"Totale campo: {total_minutes} min",
            )

            drill_columns = 2
            drill_width = (
                right - content_x - 10
            ) / drill_columns

            for drill_index, drill in enumerate(drills[:10]):
                column_index = drill_index % drill_columns
                row_index = drill_index // drill_columns
                x = content_x + column_index * drill_width
                y = content_y - row_index * 17

                pdf.setFont("Helvetica-Bold", 7.2)
                pdf.drawString(
                    x,
                    y,
                    str(drill.get("name", ""))[:32],
                )
                pdf.setFont("Helvetica", 6.7)
                pdf.drawRightString(
                    x + drill_width - 8,
                    y,
                    (
                        f"{int(drill.get('duration', 0) or 0)} min"
                        f" · {len(drill.get('participants', []))} player"
                    ),
                )
        elif notes:
            pdf.setFont("Helvetica", 7.2)
            pdf.drawString(
                content_x,
                content_y,
                notes.replace("\n", " ")[:110],
            )

        current_y = card_y - gap

    if absence_notes:
        pdf.setFillColor(colors.HexColor("#D7E0EC"))
        pdf.setFont("Helvetica", 6.4)
        pdf.drawString(
            left,
            14,
            f"Assenze / programmi differenti: {absence_notes[:150]}",
        )

    pdf.setFillColor(colors.HexColor("#8A98A8"))
    pdf.setFont("Helvetica", 5.8)
    pdf.drawRightString(
        right,
        6,
        "Performance Analysis System | Hellas Verona FC",
    )

    pdf.showPage()
    pdf.save()
    output.seek(0)
    return output.getvalue()
