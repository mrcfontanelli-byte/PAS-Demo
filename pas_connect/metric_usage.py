"""Registry e censimento read-only degli utilizzi metrici nel PAS."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping


MODULES = (
    "Dashboard", "Drills", "Match", "Match Report", "Session Report",
    "Bridge Validation", "PAS Connect", "Player Profile", "Forecast", "Planner",
)
USAGE_TYPES = (
    "display", "filter", "calculation", "comparison", "export", "report", "internal",
)
USAGE_STATUSES = ("VERIFIED", "PROBABLE", "AMBIGUOUS", "MANUAL")
CONFIDENCE_LEVELS = ("verificata", "probabile", "ambigua")
_CONFIDENCE_STATUS = {
    "verificata": "VERIFIED", "probabile": "PROBABLE", "ambigua": "AMBIGUOUS",
}


def _source_location(path: Path, needle: str) -> tuple[int | None, str]:
    if not path.is_file():
        return None, ""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number, line.strip()
    return None, ""


def _proposal(
    metric: str,
    module: str,
    view_name: str,
    usage_type: str,
    path: Path,
    needle: str,
    confidence: str,
    notes: str,
) -> dict[str, object] | None:
    line, evidence = _source_location(path, needle)
    if line is None:
        return None
    return {
        "canonical_metric": metric,
        "module": module,
        "view_name": view_name,
        "usage_type": usage_type,
        "enabled": True,
        "required": False,
        "display_order": 0,
        "notes": notes,
        "confidence": confidence,
        "status": _CONFIDENCE_STATUS[confidence],
        "source_file": path.name if path.name != "reporting.py" else "modules/reporting.py",
        "source_line": line,
        "evidence": evidence,
    }


def scan_metric_usage(
    code_root: str | Path,
    catalog_rows: Iterable[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Propone utilizzi con evidenza; non scrive file né database."""
    root = Path(code_root)
    catalog_rows = list(catalog_rows)
    app = root / "app.py"
    reporting = root / "modules" / "reporting.py"
    developer_tools = root / "modules" / "developer_tools.py"
    canonical = {
        str(row.get("canonical_metric") or "").strip().casefold():
        str(row.get("canonical_metric") or "").strip()
        for row in catalog_rows if str(row.get("canonical_metric") or "").strip()
    }
    aliases: dict[str, set[str]] = {}
    for row in catalog_rows:
        metric = str(row.get("canonical_metric") or "").strip()
        if not metric:
            continue
        aliases.setdefault(metric, set()).update(
            str(row.get(field) or "").strip()
            for field in ("canonical_metric", "display_name", "provider_metric_name")
            if str(row.get(field) or "").strip()
        )

    def name(preferred: str) -> str:
        return canonical.get(preferred.casefold(), preferred)

    specs = [
        (name("Distance"), "Dashboard", "Panoramica del giorno", "display", app,
         "dashboard_uses_gpexe_distance", "verificata", "Card Distance giornaliera."),
        (name("Distance"), "Bridge Validation", "Bridge Validation", "comparison", app,
         'if page == "🧪 Bridge Validation"', "verificata", "Confronto Distance Excel/GPExe."),
        (name("Distance"), "PAS Connect", "Distance Pilot", "display", app,
         'if page == "📏 Distance Pilot"', "verificata", "Vista pilota Distance esistente."),
        (name("Relative Distance"), "Bridge Validation", "Bridge Validation", "comparison", developer_tools,
         "compare_relative_distance_sources", "verificata", "Confronto Relative Distance Excel/GPExe."),
        (name("MPE Rec Avg Time"), "Match", "Match Analysis", "display", app,
         '"MPE Rec Avg Time (s)": {', "verificata", "Metrica inclusa in match_metrics."),
        (name("MPE Rec Avg Time"), "Match", "Performance Model", "calculation", app,
         "MPE Rec Avg Time restano assoluti", "verificata", "Calcolo del modello Match."),
        (name("MPE Rec Avg Time"), "Match Report", "Match Report", "report", reporting,
         '"MPE Rec Avg Time (s)",', "verificata", "Metrica prevista dal renderer report."),
        (name("MPE Rec Avg Time"), "Drills", "Drills Analysis", "display", app,
         "DRILL_ANALYSIS_METRICS = {", "ambigua",
         "Requisito operativo dichiarato, ma la metrica non compare nel dizionario Drills: validare."),
        (name("MPE Rec Avg Time"), "Drills", "Drills Analysis", "calculation", app,
         "DRILL_ANALYSIS_METRICS = {", "ambigua",
         "Disponibilità richiesta nei Drills senza evidenza diretta nel dizionario metriche."),
        (name("High Intensity Training"), "Dashboard", "Panoramica del giorno", "display", app,
         '"High Intensity Training (mm:ss)",', "verificata", "Metrica Firstbeat già visibile."),
        (name("High Intensity Training"), "Session Report", "Professional Session Report", "report", reporting,
         '"High Intensity Training (mm:ss)",', "verificata", "Metrica Firstbeat già nel report."),
        (name("Anaerobic Threshold Zone"), "Dashboard", "Panoramica del giorno", "display", app,
         '"Anaerobic Threshold Zone (mm:ss)",', "verificata", "Metrica Firstbeat già visibile."),
        (name("Anaerobic Threshold Zone"), "Session Report", "Professional Session Report", "report", reporting,
         '"Anaerobic Threshold Zone (mm:ss)",', "verificata", "Metrica Firstbeat già nel report."),
    ]
    proposals = [
        item for item in (_proposal(*spec) for spec in specs) if item is not None
    ]

    def scan_structured_block(
        path: Path,
        start_marker: str,
        end_marker: str,
        module: str,
        view_name: str,
        usage_types: tuple[str, ...],
    ) -> None:
        lines = path.read_text(encoding="utf-8").splitlines()
        start = next((index for index, line in enumerate(lines) if start_marker in line), None)
        if start is None:
            return
        end = next(
            (index for index in range(start + 1, len(lines)) if end_marker in lines[index]),
            len(lines),
        )
        for metric, metric_aliases in aliases.items():
            evidence = None
            line_number = None
            for index in range(start, end):
                folded = lines[index].casefold()
                if any(f'"{alias.casefold()}' in folded for alias in metric_aliases if len(alias) >= 4):
                    evidence = lines[index].strip()
                    line_number = index + 1
                    break
            if line_number is None:
                continue
            for usage_type in usage_types:
                proposals.append({
                    "canonical_metric": metric, "module": module, "view_name": view_name,
                    "usage_type": usage_type, "enabled": True, "required": False,
                    "display_order": 0, "notes": f"Riferimento nel registro {start_marker}.",
                    "confidence": "verificata", "status": "VERIFIED", "source_file": (
                        path.name if path.name != "reporting.py" else "modules/reporting.py"
                    ), "source_line": line_number, "evidence": evidence,
                })

    scan_structured_block(
        root / "modules" / "config.py", "METRICS = {", "DEFAULT_DRILLS =",
        "Dashboard", "Panoramica del giorno", ("display", "calculation"),
    )
    scan_structured_block(
        app, "DRILL_ANALYSIS_METRICS = {", "def safe_numeric_series",
        "Drills", "Drills Analysis", ("display", "calculation"),
    )
    scan_structured_block(
        app, "match_metrics = {", "match_raw =", "Match", "Match Analysis", ("display",),
    )
    scan_structured_block(
        reporting, "preferred_order = [", "selected_set =", "Session Report",
        "Professional Session Report", ("report",),
    )
    seen: set[tuple[str, str, str, str]] = set()
    unique: list[dict[str, object]] = []
    for item in proposals:
        key = tuple(str(item[field]).casefold() for field in (
            "canonical_metric", "module", "view_name", "usage_type",
        ))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def usage_record(proposal: Mapping[str, object]) -> dict[str, object]:
    """Rimuove dalla preview la provenienza, conservandola nelle note."""
    row = {key: proposal.get(key) for key in (
        "canonical_metric", "module", "view_name", "usage_type", "enabled",
        "status", "required", "display_order", "notes",
    )}
    provenance = f"{proposal.get('source_file')}:{proposal.get('source_line')} · {proposal.get('status')}"
    row["notes"] = f"{row.get('notes') or ''} [{provenance}]".strip()
    return row
