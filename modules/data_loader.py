from __future__ import annotations

from pathlib import Path
from io import BytesIO
from datetime import time, timedelta
import re
import pandas as pd
import streamlit as st

from modules.config import PLAYERS_HELLAS, SEASON_PHASES_2526, METRICS


def find_database(base_dir: Path) -> Path:
    candidates = sorted(base_dir.glob("*.xlsx"))
    preferred = [p for p in candidates if "database hellas" in p.name.lower()]
    if preferred:
        return preferred[0]
    if candidates:
        return candidates[0]
    raise FileNotFoundError(
        "Nessun file Excel trovato. Inserisci il database .xlsx nella cartella del progetto."
    )



def _duration_to_seconds(value: object) -> float:
    """Converte valori Excel hh:mm:ss, datetime.time o testo in secondi."""
    if pd.isna(value):
        return float("nan")

    if isinstance(value, time):
        return float(value.hour * 3600 + value.minute * 60 + value.second)

    if isinstance(value, timedelta):
        return float(value.total_seconds())

    if isinstance(value, (int, float)):
        # Eventuale durata Excel salvata come frazione di giorno.
        if 0 <= float(value) < 1:
            return float(value) * 86400
        return float(value)

    text = str(value).strip()
    if not text:
        return float("nan")

    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        return float(text)
    except (TypeError, ValueError):
        return float("nan")

def _clean_text(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip()


def _normalize_role(value: object) -> object:
    if pd.isna(value):
        return value
    text = str(value).strip().lower()
    mapping = {
        "midfileder": "Midfielder",
        "midfielder": "Midfielder",
        "central midfielder": "Midfielder",
        "forward": "Forward",
        "foward": "Forward",
        "center back": "Centre Back",
        "centre back": "Centre Back",
        "wing backs": "Wing Back",
        "wing back": "Wing Back",
        "side back": "Side Back",
        "full back": "Side Back",
        "fullback": "Side Back",
        "playmaker": "Play",
        "play": "Play",
        "goalkeeper": "Goalkeeper",
    }
    return mapping.get(text, str(value).strip().title())


@st.cache_data(show_spinner="Caricamento database...")
def load_database(
    database_source,
    source_name: str | None = None,
) -> pd.DataFrame:
    """
    Carica un database Excel da percorso locale oppure da bytes.
    Mantiene tutte le regole di filtro e pulizia del PAS.
    """
    if isinstance(database_source, (str, Path)):
        excel_source = database_source
    elif isinstance(database_source, bytes):
        excel_source = BytesIO(database_source)
    else:
        raise TypeError(
            "Origine database non supportata."
        )

    try:
        excel_file = pd.ExcelFile(excel_source)
    except Exception as exc:
        raise ValueError(
            f"Impossibile aprire il file Excel: {exc}"
        ) from exc

    sheet_name = (
        "Database"
        if "Database" in excel_file.sheet_names
        else excel_file.sheet_names[0]
    )

    try:
        df = pd.read_excel(
            excel_file,
            sheet_name=sheet_name,
        )
    except Exception as exc:
        raise ValueError(
            f"Impossibile leggere il foglio '{sheet_name}': {exc}"
        ) from exc

    df.columns = df.columns.astype(str).str.strip()

    required = [
        "Date",
        "Athlete",
        "Drill",
        "Season Phase",
        "Cycle",
        "Length Cycle",
        "Match Day +/-",
        "MD+",
        "MD-",
        "Role",
    ]
    missing = [
        column
        for column in required
        if column not in df.columns
    ]
    if missing:
        raise ValueError(
            "Colonne mancanti nel database: "
            + ", ".join(missing)
        )

    text_columns = [
        "Athlete",
        "Drill",
        "Season Phase",
        "Cycle",
        "Match Day +/-",
        "MD+",
        "MD-",
        "Type Session",
        "Role",
        "Time of Day",
    ]
    for column in text_columns:
        if column in df.columns:
            df[column] = _clean_text(df[column])

    df["Date"] = pd.to_datetime(
        df["Date"],
        errors="coerce",
    )
    df["Length Cycle"] = pd.to_numeric(
        df["Length Cycle"],
        errors="coerce",
    )
    df["Role Clean"] = df["Role"].map(
        _normalize_role
    )

    # Stagione e rosa configurate nel PAS.
    df = df[
        df["Season Phase"].isin(SEASON_PHASES_2526)
    ].copy()
    df = df[
        df["Athlete"].isin(PLAYERS_HELLAS)
    ].copy()

    # Esclusioni di sicurezza.
    df = df[df["Drill"].ne("Opponent Match")]
    df = df[df["Athlete"].ne("Team Average")]

    # Correzione nota.
    df["Match Day +/-"] = df[
        "Match Day +/-"
    ].replace({
        "ATALANTA (A)": "MD ATALANTA (A)"
    })

    for meta in METRICS.values():
        column = meta["column"]
        if column not in df.columns:
            continue

        if meta.get("format") == "duration":
            df[column] = df[column].map(
                _duration_to_seconds
            )
        else:
            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    df = (
        df.dropna(subset=["Date", "Athlete"])
        .sort_values("Date")
        .reset_index(drop=True)
    )

    df.attrs["source_name"] = (
        source_name
        or getattr(database_source, "name", None)
        or str(database_source)
    )
    df.attrs["sheet_name"] = sheet_name
    return df


def database_summary(
    df: pd.DataFrame,
) -> dict[str, object]:
    """Riepilogo del database caricato."""
    available_metrics = [
        metric_name
        for metric_name, meta in METRICS.items()
        if meta["column"] in df.columns
    ]
    missing_metrics = [
        metric_name
        for metric_name, meta in METRICS.items()
        if meta["column"] not in df.columns
    ]

    return {
        "source_name": df.attrs.get(
            "source_name",
            "Database",
        ),
        "sheet_name": df.attrs.get(
            "sheet_name",
            "Database",
        ),
        "rows": int(len(df)),
        "players": int(df["Athlete"].nunique()),
        "sessions": int(
            df[["Date", "Drill"]]
            .drop_duplicates()
            .shape[0]
        ),
        "first_date": df["Date"].min(),
        "last_date": df["Date"].max(),
        "drills": sorted(
            df["Drill"]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        ),
        "available_metrics": available_metrics,
        "missing_metrics": missing_metrics,
    }


def aggregate_player_day(df: pd.DataFrame) -> pd.DataFrame:
    """Una riga per atleta e data, usando somme per volumi/eventi e massimo per velocità."""
    if df.empty:
        return df.copy()

    aggregations: dict[str, str] = {}
    for meta in METRICS.values():
        column = meta["column"]
        if column in df.columns:
            aggregations[column] = meta["aggregation"]

    context_columns = [
        "Cycle", "Length Cycle", "Match Day +/-", "MD+", "MD-",
        "Season Phase", "Role Clean",
    ]
    for column in context_columns:
        if column in df.columns:
            aggregations[column] = "first"

    grouped = (
        df.groupby(["Date", "Athlete"], as_index=False)
        .agg(aggregations)
        .sort_values(["Date", "Athlete"])
    )
    return grouped
