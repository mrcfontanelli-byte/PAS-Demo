"""Livello unico di accesso ai dati del PAS.

La release 3.8.8 completa il livello di orchestrazione dei provider. Excel resta
la sorgente operativa predefinita; GPExe è registrato nello stesso catalogo ma
non è ancora operativo. Dashboard, Drills, Match Analysis, Forecast e Report
usano sempre il provider effettivo risolto centralmente.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd



class DataProviderError(RuntimeError):
    """Errore base del livello PAS Data Provider."""


class DataProviderNotReadyError(DataProviderError):
    """Provider presente nell'architettura ma non ancora operativo nel PAS Core."""


@dataclass(frozen=True)
class ProviderDescriptor:
    """Metadati stabili esposti alla UI senza istanziare logiche specifiche."""

    provider_id: str
    display_name: str
    operational: bool
    status_message: str


@dataclass(frozen=True)
class ProviderSelection:
    """Risultato della selezione: provider richiesto, effettivo e fallback."""

    requested: ProviderDescriptor
    effective: ProviderDescriptor
    provider: "PASDataProvider"
    fallback_applied: bool


class PASDataProvider(ABC):
    """Contratto unico per le sorgenti dati consumate dal PAS Core."""

    provider_id: str
    display_name: str

    @abstractmethod
    def resolve_default_source(self, base_dir: Path) -> Any:
        """Restituisce la sorgente predefinita del provider."""

    @abstractmethod
    def load_performance_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
        filter_configured_roster: bool = True,
    ) -> pd.DataFrame:
        """Carica i dati prestativi nello schema già utilizzato dal PAS."""

    @abstractmethod
    def load_named_tables(
        self,
        source: Any,
        table_names: tuple[str, ...],
    ) -> Mapping[str, pd.DataFrame]:
        """Carica tabelle nominate senza applicare trasformazioni funzionali."""

    @abstractmethod
    def load_drills_data(
        self,
        source: Any,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Carica le tabelle operative della sezione Drills."""

    @abstractmethod
    def load_forecast_data(
        self,
        source: Any,
    ) -> pd.DataFrame:
        """Carica la tabella media esercitazioni richiesta dal Forecast."""

    @abstractmethod
    def load_match_analysis_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        """Carica il dataset completo richiesto dalla sezione Match Analysis."""

    @abstractmethod
    def load_report_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        """Carica il dataset prestativo richiesto dalla reportistica PAS."""

    def load_pilot_distance_data(self, source: Any) -> pd.DataFrame:
        """Carica Distance nello schema canonico della sola vista pilota."""
        raise DataProviderNotReadyError(
            f"La vista pilota Distance non è disponibile per {self.display_name}."
        )

    def load_session_distance_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        frame = self.load_pilot_distance_data(source)
        target = pd.Timestamp(selected_date).normalize()
        frame = frame[pd.to_datetime(frame["Date"], errors="coerce").dt.normalize().eq(target)]
        athletes = filters.get("athletes")
        if athletes:
            from modules.session_distance import normalize_athlete_name
            selected = {normalize_athlete_name(value) for value in athletes}
            frame = frame[frame["Athlete"].map(normalize_athlete_name).isin(selected)]
        return frame.reset_index(drop=True)

    def load_session_relative_distance_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        raise DataProviderNotReadyError(
            f"Relative Distance non disponibile per {self.display_name}."
        )

    def load_day_overview_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        raise DataProviderNotReadyError(
            f"Panoramica del giorno non disponibile per {self.display_name}."
        )


@dataclass(frozen=True)
class ExcelProvider(PASDataProvider):
    """Provider operativo che conserva integralmente il caricamento Excel PAS."""

    provider_id: str = "excel"
    display_name: str = "Excel"

    def resolve_default_source(self, base_dir: Path) -> Path:
        candidates = sorted(base_dir.glob("*.xlsx"))
        preferred = [p for p in candidates if "database hellas" in p.name.lower()]
        if preferred:
            return preferred[0]
        if candidates:
            return candidates[0]
        raise FileNotFoundError(
            "Nessun file Excel trovato. Inserisci il database .xlsx nella cartella del progetto."
        )

    def load_performance_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
        filter_configured_roster: bool = True,
    ) -> pd.DataFrame:
        # Import locale: evita dipendenze UI durante la sola selezione del provider.
        from modules.data_loader import load_database

        return load_database(
            source,
            source_name=source_name,
            filter_configured_roster=filter_configured_roster,
        )

    def load_named_tables(
        self,
        source: Any,
        table_names: tuple[str, ...],
    ) -> Mapping[str, pd.DataFrame]:
        try:
            return {
                table_name: pd.read_excel(source, sheet_name=table_name)
                for table_name in table_names
            }
        except Exception as exc:
            raise DataProviderError(
                f"Impossibile leggere le tabelle Excel richieste: {exc}"
            ) from exc

    def load_drills_data(
        self,
        source: Any,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        tables = self.load_named_tables(
            source,
            ("Esercitazioni", "Esercitazioni Avg"),
        )
        return tables["Esercitazioni"], tables["Esercitazioni Avg"]

    def load_forecast_data(
        self,
        source: Any,
    ) -> pd.DataFrame:
        tables = self.load_named_tables(source, ("Esercitazioni Avg",))
        return tables["Esercitazioni Avg"]

    def load_match_analysis_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        return self.load_performance_data(
            source,
            source_name=source_name,
            filter_configured_roster=False,
        )

    def load_report_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        return self.load_performance_data(
            source,
            source_name=source_name,
            filter_configured_roster=True,
        )

    def load_pilot_distance_data(self, source: Any) -> pd.DataFrame:
        frame = source.copy() if isinstance(source, pd.DataFrame) else self.load_performance_data(source)
        required = {"Date", "Athlete", "distance (m)"}
        missing = sorted(required.difference(frame.columns))
        if missing:
            raise DataProviderError(
                "La sorgente Excel non contiene le colonne Distance richieste: "
                + ", ".join(missing)
            )
        result = frame.loc[:, ["Date", "Athlete", "distance (m)"]].copy()
        result["Date"] = pd.to_datetime(result["Date"], errors="coerce")
        result["Athlete"] = result["Athlete"].astype("string").str.strip()
        result["Distance (m)"] = pd.to_numeric(result.pop("distance (m)"), errors="coerce")
        result["TeamSession ID"] = pd.NA
        result["AthleteSession ID"] = pd.NA
        result["Source"] = "Excel"
        return result.dropna(subset=["Date", "Athlete", "Distance (m)"]).reset_index(drop=True)

    def load_session_relative_distance_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        frame = source.copy() if isinstance(source, pd.DataFrame) else self.load_performance_data(source)
        from modules.session_relative_distance import load_excel_operational_relative_distance
        return load_excel_operational_relative_distance(
            frame, selected_date, athletes=filters.get("athletes")
        )

    def load_day_overview_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        frame = source.copy() if isinstance(source, pd.DataFrame) else self.load_performance_data(source)
        target = pd.Timestamp(selected_date).normalize()
        result = frame[pd.to_datetime(frame["Date"], errors="coerce").dt.normalize().eq(target)].copy()
        athletes = filters.get("athletes")
        if athletes:
            selected = {" ".join(str(value).upper().split()) for value in athletes}
            result = result[result["Athlete"].map(lambda value: " ".join(str(value).upper().split())).isin(selected)]
        return result.reset_index(drop=True)


@dataclass(frozen=True)
class GPExeProvider(PASDataProvider):
    """Provider GPExe per export oppure database API sincronizzato da PAS Connect."""

    provider_id: str = "gpexe"
    display_name: str = "GPExe"

    def resolve_default_source(self, base_dir: Path) -> Any:
        api_database = base_dir / ".pas_data" / "pas_connect.sqlite3"
        if api_database.is_file():
            return api_database
        raise DataProviderError(
            "Sincronizza GPExe tramite PAS Connect oppure carica un export GPExe."
        )

    def load_performance_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
        filter_configured_roster: bool = True,
    ) -> pd.DataFrame:
        from modules.gpexe_import import import_gpexe_file

        api_session_ids = None
        api_source = source
        if isinstance(source, Mapping) and source.get("kind") == "gpexe_api":
            api_source = source.get("database_path")
            api_session_ids = source.get("session_ids")
        source_path = Path(api_source) if isinstance(api_source, (str, Path)) else None
        if source_path is not None and source_path.suffix.lower() in {".sqlite", ".sqlite3", ".db"}:
            from pas_connect.pas_bridge import load_pas_performance_frame
            frame = load_pas_performance_frame(source_path, session_ids=api_session_ids)
            role_mapping = {
                "midfileder": "Midfielder", "midfielder": "Midfielder",
                "central midfielder": "Midfielder", "forward": "Forward",
                "foward": "Forward", "center back": "Centre Back",
                "centre back": "Centre Back", "wing backs": "Wing Back",
                "wing back": "Wing Back", "side back": "Side Back",
                "full back": "Side Back", "fullback": "Side Back",
                "playmaker": "Play", "play": "Play", "goalkeeper": "Goalkeeper",
            }
            frame["Role Clean"] = frame["Role"].map(
                lambda value: role_mapping.get(str(value).strip().lower(), str(value).strip().title())
            )
            # Il database PAS Connect è già delimitato da TeamSession/provider ID.
            # Il roster configurato appartiene esclusivamente al contesto Excel
            # e non può filtrare un Team GPExe diverso.
            return frame.reset_index(drop=True)

        role_mapping = {
            "midfileder": "Midfielder", "midfielder": "Midfielder",
            "central midfielder": "Midfielder", "forward": "Forward",
            "foward": "Forward", "center back": "Centre Back",
            "centre back": "Centre Back", "wing backs": "Wing Back",
            "wing back": "Wing Back", "side back": "Side Back",
            "full back": "Side Back", "fullback": "Side Back",
            "playmaker": "Play", "play": "Play", "goalkeeper": "Goalkeeper",
        }
        result = import_gpexe_file(source, source_name=source_name, require_core=True)
        frame = result.data.copy()
        frame["Role Clean"] = frame["Role"].map(
            lambda value: role_mapping.get(str(value).strip().lower(), str(value).strip().title())
        )
        frame.attrs.update(result.data.attrs)
        frame.attrs["gpexe_rows_read"] = result.rows_read
        frame.attrs["gpexe_rows_rejected"] = result.rows_rejected
        frame.attrs["gpexe_warnings"] = result.warnings
        return frame.reset_index(drop=True)

    def load_named_tables(
        self,
        source: Any,
        table_names: tuple[str, ...],
    ) -> Mapping[str, pd.DataFrame]:
        raise DataProviderError(
            "Gli export GPExe non contengono le tabelle Esercitazioni del database PAS."
        )

    def load_drills_data(self, source: Any) -> tuple[pd.DataFrame, pd.DataFrame]:
        raise DataProviderNotReadyError("Le tabelle Drills restano disponibili dal database Excel PAS.")

    def load_forecast_data(self, source: Any) -> pd.DataFrame:
        raise DataProviderNotReadyError("La tabella Forecast resta disponibile dal database Excel PAS.")

    def load_match_analysis_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        return self.load_performance_data(source, source_name=source_name, filter_configured_roster=False)

    def load_report_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        return self.load_performance_data(source, source_name=source_name, filter_configured_roster=True)

    def load_pilot_distance_data(self, source: Any) -> pd.DataFrame:
        source_path = Path(source)
        if source_path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise DataProviderError(
                "La vista pilota GPExe legge esclusivamente il database PAS Connect locale."
            )
        from pas_connect.pas_bridge import load_pilot_distance_frame

        return load_pilot_distance_frame(source_path)

    def load_session_distance_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        source_path = Path(source)
        if source_path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise DataProviderError(
                "La Distance operativa GPExe legge esclusivamente il database PAS Connect locale."
            )
        from modules.session_distance import load_gpexe_operational_distance
        return load_gpexe_operational_distance(
            source_path, selected_date,
            drill=filters.get("drill", "Totale sessione"),
            team_id=filters.get("team_id"), session_ids=filters.get("session_ids"),
            athlete_ids=filters.get("athlete_ids"), athletes=filters.get("athletes"),
        )

    def load_session_relative_distance_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        source_path = Path(source)
        if source_path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise DataProviderError(
                "La Relative Distance GPExe legge esclusivamente il database PAS Connect locale."
            )
        from modules.session_relative_distance import load_gpexe_operational_relative_distance
        return load_gpexe_operational_relative_distance(
            source_path, selected_date,
            drill=filters.get("drill", "Totale sessione"),
            team_id=filters.get("team_id"), session_ids=filters.get("session_ids"),
            athlete_ids=filters.get("athlete_ids"), athletes=filters.get("athletes"),
        )

    def load_day_overview_data(
        self, source: Any, selected_date: object, **filters: Any,
    ) -> pd.DataFrame:
        source_path = Path(source)
        if source_path.suffix.lower() not in {".sqlite", ".sqlite3", ".db"}:
            raise DataProviderError(
                "La Panoramica GPExe legge esclusivamente il database PAS Connect locale."
            )
        from modules.day_overview_provider import load_gpexe_day_overview
        return load_gpexe_day_overview(
            source_path, selected_date, drill=filters.get("drill", "Totale sessione"),
            team_id=filters.get("team_id"), session_ids=filters.get("session_ids"),
            athlete_ids=filters.get("athlete_ids"), athletes=filters.get("athletes"),
        )


DEFAULT_PROVIDER_ID = "excel"

_PROVIDER_TYPES: dict[str, type[PASDataProvider]] = {
    "excel": ExcelProvider,
    "gpexe": GPExeProvider,
}

_PROVIDER_DESCRIPTORS: dict[str, ProviderDescriptor] = {
    "excel": ProviderDescriptor(
        provider_id="excel",
        display_name="Excel",
        operational=True,
        status_message="Sorgente operativa: Excel",
    ),
    "gpexe": ProviderDescriptor(
        provider_id="gpexe",
        display_name="GPExe",
        operational=True,
        status_message="Sorgente operativa: GPExe API / export",
    ),
}


def normalize_provider_id(provider_id: str | None) -> str:
    """Normalizza ID o nome visualizzato senza dipendere dalla UI Streamlit."""
    normalized = str(provider_id or DEFAULT_PROVIDER_ID).strip().lower()
    aliases = {descriptor.display_name.lower(): key for key, descriptor in _PROVIDER_DESCRIPTORS.items()}
    return aliases.get(normalized, normalized)


def get_available_data_providers() -> tuple[ProviderDescriptor, ...]:
    """Catalogo ordinato delle sorgenti disponibili nel PAS Connect."""
    return tuple(_PROVIDER_DESCRIPTORS[key] for key in _PROVIDER_TYPES)


def get_provider_descriptor(provider_id: str = DEFAULT_PROVIDER_ID) -> ProviderDescriptor:
    normalized = normalize_provider_id(provider_id)
    try:
        return _PROVIDER_DESCRIPTORS[normalized]
    except KeyError as exc:
        raise DataProviderError(f"Provider dati PAS non riconosciuto: {provider_id!r}") from exc


def get_data_provider(provider_id: str = DEFAULT_PROVIDER_ID) -> PASDataProvider:
    """Factory centrale per istanziare un provider registrato."""
    normalized = normalize_provider_id(provider_id)
    try:
        return _PROVIDER_TYPES[normalized]()
    except KeyError as exc:
        raise DataProviderError(f"Provider dati PAS non riconosciuto: {provider_id!r}") from exc


def resolve_data_provider(provider_id: str = DEFAULT_PROVIDER_ID) -> ProviderSelection:
    """Risolve la scelta richiesta applicando un fallback esplicito e testabile.

    Restituisce il provider richiesto. Il fallback a Excel viene gestito dalla UI
    solo quando non è stato ancora caricato un export GPExe valido.
    """
    requested = get_provider_descriptor(provider_id)
    effective = requested if requested.operational else get_provider_descriptor(DEFAULT_PROVIDER_ID)
    return ProviderSelection(
        requested=requested,
        effective=effective,
        provider=get_data_provider(effective.provider_id),
        fallback_applied=requested.provider_id != effective.provider_id,
    )
