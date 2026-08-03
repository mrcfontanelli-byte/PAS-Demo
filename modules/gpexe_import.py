"""Importazione controllata di export GPExe in memoria."""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Mapping
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


def _records(path: Path) -> tuple[list[Mapping[str, Any]], str]:
    suffix = path.suffix.lower()
    try:
        if suffix == '.json':
            payload = json.loads(path.read_text(encoding='utf-8-sig'))
            if isinstance(payload, list): items = payload
            elif isinstance(payload, Mapping):
                items = next((payload[k] for k in ('records','data','rows','sessions','athlete_sessions') if isinstance(payload.get(k), list)), [payload])
            else: raise GPExeImportError('JSON GPExe non valido.')
        elif suffix == '.csv':
            items = pd.read_csv(path).to_dict('records')
        elif suffix in {'.xlsx', '.xls'}:
            items = pd.read_excel(path).to_dict('records')
        else:
            raise GPExeImportError('Formato GPExe non supportato. Usare JSON, CSV o XLSX.')
    except GPExeImportError: raise
    except Exception as exc: raise GPExeImportError(f'Impossibile leggere {path.name}: {exc}') from exc
    if not all(isinstance(x, Mapping) for x in items): raise GPExeImportError('Record GPExe non validi.')
    return list(items), suffix.lstrip('.')


def import_gpexe_file(source: str | Path, *, require_core: bool = True) -> GPExeImportResult:
    path = Path(source)
    if not path.is_file(): raise GPExeImportError(f'File GPExe non trovato: {path}')
    rows, fmt = _records(path)
    output, warnings = [], []
    metadata_aliases = {'date':('date','session date','data'), 'player':('player','athlete','athlete name'), 'drill':('drill','exercise','session name')}
    for idx, row in enumerate(rows, 1):
        try:
            metrics = row.get('metrics', row)
            units = row.get('units', {})
            if not isinstance(metrics, Mapping) or not isinstance(units, Mapping): raise MappingValidationError('metrics/units non validi')
            mapped = map_gpexe_metrics(metrics, units=units, require_core=require_core)
            norm = {''.join(c for c in str(k).lower() if c.isalnum()): v for k,v in row.items()}
            record = {}
            for target, aliases in metadata_aliases.items():
                for alias in aliases:
                    key=''.join(c for c in alias.lower() if c.isalnum())
                    if key in norm and norm[key] not in (None,''):
                        record[target]=norm[key]; break
            record.update(mapped); output.append(record)
        except (MappingValidationError, ValueError, TypeError) as exc:
            warnings.append(f'Riga {idx} scartata: {exc}')
    if rows and not output: raise GPExeImportError('Nessun record GPExe valido; applicare il fallback Excel.')
    frame=pd.DataFrame(output)
    if 'date' in frame: frame['date']=pd.to_datetime(frame['date'], errors='coerce')
    return GPExeImportResult(frame, path.name, fmt, len(rows), len(output), len(warnings), tuple(warnings))
