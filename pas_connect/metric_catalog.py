"""Catalogo master PAS costruito esclusivamente dalle intestazioni provider."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
import re
import sqlite3
from typing import Any, BinaryIO, TextIO


CONTEXTUAL_FIELDS = frozenset({
    "start date/time", "category", "tags", "notes", "match cycle",
    "last match label", "next match label", "last match", "next match",
    "type", "athlete", "starter", "role",
})

METRIC_TYPES = (
    "direct", "derived", "threshold_distance", "event_count", "duration",
    "speed", "acceleration", "metabolic", "heart_rate", "external_work", "contextual",
)
VALUE_TYPES = ("numeric", "integer", "duration", "boolean", "text")


@dataclass(frozen=True)
class ProviderDefinition:
    provider: str
    acquisition_mode: str
    implemented: bool
    note: str


PROVIDER_REGISTRY = {
    "Excel": ProviderDefinition("Excel", "EXCEL", True, "Provider Excel operativo."),
    "GPExe": ProviderDefinition("GPExe", "GRAPHQL", True, "Provider GPExe operativo."),
    "Firstbeat": ProviderDefinition(
        "Firstbeat", "MANUAL", False, "Previsto senza nuova connessione in questa release."
    ),
    "VALD": ProviderDefinition("VALD", "CSV", False, "Provider CSV futuro; import non implementato."),
}


def has_catalogued_distance(database_path: str | Path) -> bool:
    """Distance deve esistere nel catalogo GPExe e non richiedere profilo."""
    path = Path(database_path)
    if not path.is_file():
        return False
    try:
        with sqlite3.connect(path) as connection:
            row = connection.execute(
                """SELECT requires_profile FROM pas_metric_catalog
                WHERE lower(canonical_metric)='distance' AND provider='GPExe'
                ORDER BY id LIMIT 1"""
            ).fetchone()
        return row is not None and not bool(row[0])
    except sqlite3.Error:
        return False


def _header_line(source: str | Path | BinaryIO | TextIO) -> tuple[str, str]:
    """Legge una sola riga e restituisce testo e nome template."""
    if isinstance(source, (str, Path)):
        path = Path(source)
        with path.open("rb") as stream:
            raw = stream.readline()
        return raw.decode("utf-8-sig"), path.name
    name = Path(str(getattr(source, "name", "template.csv"))).name
    position = source.tell() if hasattr(source, "tell") else None
    if hasattr(source, "seek"):
        source.seek(0)
    raw = source.readline()
    if position is not None and hasattr(source, "seek"):
        source.seek(position)
    if isinstance(raw, bytes):
        return raw.decode("utf-8-sig"), name
    return str(raw).lstrip("\ufeff"), name


def read_csv_headers(source: str | Path | BinaryIO | TextIO) -> tuple[list[str], str]:
    """Estrae soltanto le intestazioni CSV, senza leggere alcuna riga dati."""
    line, source_name = _header_line(source)
    if not line.strip():
        raise ValueError("Template CSV privo di intestazioni.")
    dialect = csv.Sniffer().sniff(line, delimiters=",;\t|")
    headers = next(csv.reader(StringIO(line), dialect))
    cleaned = [str(item).strip() for item in headers]
    if not cleaned or any(not item for item in cleaned):
        raise ValueError("Template CSV con intestazioni vuote.")
    return cleaned, source_name


def split_metric_name_unit(header: str) -> tuple[str, str | None]:
    match = re.match(r"^(.*?)\s*\(([^()]*)\)\s*$", header.strip())
    return (match.group(1).strip(), match.group(2).strip()) if match else (header.strip(), None)


def _canonical_name(base_name: str) -> str:
    mandatory = {
        "distance": "Distance",
        "MPE rec avg time": "MPE Rec Avg Time",
    }
    if base_name in mandatory:
        return mandatory[base_name]
    acronyms = {"mpe": "MPE", "hr": "HR", "mp": "MP", "avg": "Avg", "acc": "Acc", "dec": "Dec"}
    parts = re.split(r"(\W+)", base_name)
    result = []
    for part in parts:
        lowered = part.lower()
        if lowered in acronyms:
            result.append(acronyms[lowered])
        elif re.fullmatch(r"z\d\+?", lowered):
            result.append(lowered.upper())
        elif part.isalpha():
            result.append(part.capitalize())
        else:
            result.append(part)
    return "".join(result)


def classify_header(header: str, *, provider: str = "GPExe", source_template: str = "") -> dict[str, Any]:
    """Propone una classificazione conservativa ricavata dal solo nome colonna."""
    base, unit = split_metric_name_unit(header)
    lowered = base.casefold()
    contextual = lowered in CONTEXTUAL_FIELDS
    has_zone = bool(re.search(r"\bz\d\+?\b", lowered, re.IGNORECASE))

    if contextual:
        category = "Contextual"
    elif lowered.startswith("mpe "):
        category = "MPE"
    elif "met power" in lowered or lowered in {"avg mp", "energy"}:
        category = "Metabolic"
    elif lowered.startswith("high ext work"):
        category = "External Work"
    elif "/hr " in lowered:
        category = "Heart Rate"
    elif "acc" in lowered or "dec" in lowered or lowered in {"bursts", "brakes"}:
        category = "Acceleration"
    else:
        category = "GPS"

    if contextual:
        metric_type = "contextual"
    elif lowered.startswith("distance/") and has_zone:
        metric_type = "threshold_distance"
    elif "events" in lowered or lowered in {"bursts", "brakes"}:
        metric_type = "event_count"
    elif lowered == "duration" or " time" in lowered or lowered.startswith("walk time") or lowered.startswith("run time"):
        metric_type = "duration"
    elif category == "Heart Rate":
        metric_type = "heart_rate"
    elif lowered.startswith("high ext work"):
        metric_type = "external_work"
    elif lowered == "max acc":
        metric_type = "acceleration"
    elif "speed" in lowered and not lowered.startswith("distance/"):
        metric_type = "speed"
    elif category in {"Metabolic", "MPE"}:
        metric_type = "metabolic"
    else:
        metric_type = "direct"

    if contextual:
        value_type = "boolean" if lowered == "starter" else "text"
    elif metric_type == "event_count":
        value_type = "integer"
    elif metric_type == "duration" and unit == "mm:ss":
        value_type = "duration"
    else:
        value_type = "numeric"
    requires_profile = bool(
        not contextual and (has_zone or lowered in {"speed events", "%speed events"})
    )
    acquisition = PROVIDER_REGISTRY.get(provider, ProviderDefinition(provider, "MANUAL", False, "")).acquisition_mode
    return {
        "canonical_metric": _canonical_name(base),
        "display_name": _canonical_name(base),
        "provider": provider,
        "acquisition_mode": acquisition,
        "provider_metric_name": header,
        "category": category,
        "metric_type": metric_type,
        "canonical_unit": unit,
        "provider_unit": unit,
        "value_type": value_type,
        "requires_profile": requires_profile,
        "active": not contextual,
        "description": None,
        "source_template": source_template,
        "is_contextual": contextual,
    }


def catalog_preview_from_csv(source: str | Path | BinaryIO | TextIO, *, provider: str = "GPExe") -> list[dict[str, Any]]:
    headers, source_name = read_csv_headers(source)
    return [classify_header(header, provider=provider, source_template=source_name) for header in headers]


def planned_provider_entries() -> list[dict[str, Any]]:
    """Metriche PAS esistenti previste per Firstbeat, inattive e senza mapping inventato."""
    return [
        {
            "canonical_metric": canonical, "display_name": display,
            "provider": "Firstbeat", "acquisition_mode": "MANUAL",
            "provider_metric_name": "", "category": "Firstbeat",
            "metric_type": "duration", "canonical_unit": "mm:ss", "provider_unit": None,
            "value_type": "duration", "requires_profile": False, "active": False,
            "description": "Metrica già presente nel PAS; mapping Firstbeat non configurato.",
            "source_template": None, "is_contextual": False,
        }
        for canonical, display in (
            ("Anaerobic Threshold Zone", "Anaerobic Threshold Zone"),
            ("High Intensity Training", "High Intensity Training"),
        )
    ]
