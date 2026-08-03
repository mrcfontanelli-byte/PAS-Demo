"""Importazione e normalizzazione degli export GPExe nel modello dati PAS."""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
import json
from pathlib import Path
from typing import Any, BinaryIO, Mapping
import pandas as pd
from modules.data_mapping import MappingValidationError, map_gpexe_metrics

class GPExeImportError(RuntimeError):
    """Errore controllato del motore di importazione GPExe."""

@dataclass(frozen=True)
class GPExeImportResult:
    data: pd.DataFrame
    source_name: str
    source_format: str
    rows_read: int
    rows_imported: int
    rows_rejected: int
    warnings: tuple[str, ...] = ()


def _source_payload(source: Any, source_name: str | None) -> tuple[Any, str, str]:
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.is_file():
            raise GPExeImportError(f"File GPExe non trovato: {path}")
        return path, source_name or path.name, path.suffix.lower().lstrip('.')
    if isinstance(source, bytes):
        name = source_name or "gpexe_export.csv"
        return BytesIO(source), name, Path(name).suffix.lower().lstrip('.')
    if hasattr(source, "read"):
        name = source_name or getattr(source, "name", "gpexe_export.csv")
        return source, name, Path(name).suffix.lower().lstrip('.')
    raise GPExeImportError("Origine GPExe non supportata.")


def _records(source: Any, source_name: str | None = None) -> tuple[list[Mapping[str, Any]], str, str]:
    payload, name, fmt = _source_payload(source, source_name)
    try:
        if fmt == "json":
            if isinstance(payload, Path):
                raw = payload.read_text(encoding="utf-8-sig")
            else:
                raw_bytes = payload.read()
                raw = raw_bytes.decode("utf-8-sig") if isinstance(raw_bytes, bytes) else str(raw_bytes)
            document = json.loads(raw)
            if isinstance(document, list):
                items = document
            elif isinstance(document, Mapping):
                items = next((document[k] for k in ("records", "data", "rows", "sessions", "athlete_sessions") if isinstance(document.get(k), list)), [document])
            else:
                raise GPExeImportError("JSON GPExe non valido.")
        elif fmt == "csv":
            # Gli export GPExe europei usano ';'. Evitiamo lo sniffer Python,
            # che può interpretare lo spazio in intestazioni singole come separatore.
            if isinstance(payload, Path):
                first_line = payload.open("r", encoding="utf-8-sig", errors="replace").readline()
            else:
                position = payload.tell() if hasattr(payload, "tell") else None
                raw_head = payload.read(4096)
                if position is not None:
                    payload.seek(position)
                first_line = raw_head.decode("utf-8-sig", errors="replace").splitlines()[0] if isinstance(raw_head, bytes) else str(raw_head).splitlines()[0]
            separator = ";" if first_line.count(";") > first_line.count(",") else ","
            items = pd.read_csv(payload, sep=separator).to_dict("records")
        elif fmt in {"xlsx", "xls"}:
            items = pd.read_excel(payload).to_dict("records")
        else:
            raise GPExeImportError("Formato GPExe non supportato. Usare JSON, CSV, XLS o XLSX.")
    except GPExeImportError:
        raise
    except Exception as exc:
        raise GPExeImportError(f"Impossibile leggere {name}: {exc}") from exc
    if not all(isinstance(item, Mapping) for item in items):
        raise GPExeImportError("Record GPExe non validi.")
    return list(items), fmt, name


def _first(row: Mapping[str, Any], *aliases: str) -> Any:
    normalized = {str(k).strip().lower(): v for k, v in row.items()}
    for alias in aliases:
        value = normalized.get(alias.lower())
        if value is not None and not (isinstance(value, float) and pd.isna(value)) and str(value).strip():
            return value
    return None


def _duration_seconds(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return float("nan")
    parts = str(value).strip().split(":")
    try:
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        if len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _pas_record(row: Mapping[str, Any], mapped: Mapping[str, Any]) -> dict[str, Any]:
    start = pd.to_datetime(_first(row, "start date/time", "date", "session date", "data"), errors="coerce")
    last_match = pd.to_numeric(_first(row, "last match"), errors="coerce")
    next_match = pd.to_numeric(_first(row, "next match"), errors="coerce")
    length_cycle = last_match + next_match if pd.notna(last_match) and pd.notna(next_match) else pd.NA
    match_day = f"MD-{int(next_match)}" if pd.notna(next_match) else (f"MD+{int(last_match)}" if pd.notna(last_match) else "")
    starter = _first(row, "starter")
    starter_bool = str(starter).strip().lower() in {"true", "1", "yes", "s", "starter"}
    duration_seconds = _duration_seconds(_first(row, "duration (mm:ss)", "duration"))
    category = str(_first(row, "category", "drill", "exercise", "session name") or "GPExe Session").strip().title()
    record = {
        "Date": start.normalize() if pd.notna(start) else pd.NaT,
        "Athlete": str(_first(row, "athlete", "player", "athlete name") or "").strip().rstrip("*").strip().upper(),
        "Drill": category,
        "Season Phase": "In Season",
        "Cycle": str(_first(row, "match cycle", "cycle") or "").strip(),
        "Length Cycle": length_cycle,
        "Match Day +/-": match_day,
        "MD+": f"MD+{int(last_match)}" if pd.notna(last_match) else "",
        "MD-": f"MD-{int(next_match)}" if pd.notna(next_match) else "",
        "Role": str(_first(row, "role") or "").strip(),
        "Time of Day": start.strftime("%H:%M") if pd.notna(start) else "",
        "Type Session": str(_first(row, "type") or "").strip(),
        "Starters / No Starters": "S" if starter_bool else "NS",
        "Duration (dec)": duration_seconds / 60 if pd.notna(duration_seconds) else float("nan"),
        "Anaerobic threshold zone (hh:mm:ss)": _duration_seconds(_first(row, "time/hr z3 (mm:ss)")),
        "High intensity training (hh:mm:ss)": _duration_seconds(_first(row, "time/hr z2 (mm:ss)")),
        "RPE (CR10)": pd.NA,
    }
    record.update(mapped)
    return record


def import_gpexe_file(source: Any, *, source_name: str | None = None, require_core: bool = True) -> GPExeImportResult:
    rows, fmt, name = _records(source, source_name)
    output: list[dict[str, Any]] = []
    warnings: list[str] = []
    for idx, row in enumerate(rows, 1):
        try:
            metrics = row.get("metrics", row)
            units = row.get("units", {})
            if not isinstance(metrics, Mapping) or not isinstance(units, Mapping):
                raise MappingValidationError("metrics/units non validi")
            mapped = map_gpexe_metrics(metrics, units=units, require_core=require_core)
            record = _pas_record(row, mapped)
            output.append(record)
        except (MappingValidationError, ValueError, TypeError) as exc:
            warnings.append(f"Riga {idx} scartata: {exc}")
    if rows and not output:
        raise GPExeImportError("Nessun record GPExe valido; applicare il fallback Excel.")
    frame = pd.DataFrame(output).sort_values(["Date", "Athlete"]).reset_index(drop=True)
    frame.attrs["source_name"] = name
    frame.attrs["sheet_name"] = "GPExe Export"
    return GPExeImportResult(frame, name, fmt, len(rows), len(output), len(warnings), tuple(warnings))
