"""Livello unico di accesso ai dati del PAS.

La release 3.8.7 completa il livello di orchestrazione dei provider. Excel resta
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


@dataclass(frozen=True)
class GPExeProvider(PASDataProvider):
    """Provider GPExe registrato, intenzionalmente non attivo nella v3.8.7."""

    provider_id: str = "gpexe"
    display_name: str = "GPExe"

    @staticmethod
    def _not_ready() -> DataProviderNotReadyError:
        return DataProviderNotReadyError(
            "GPExeProvider è predisposto ma non ancora collegato ai moduli PAS. "
            "Excel resta la sorgente dati operativa predefinita."
        )

    def resolve_default_source(self, base_dir: Path) -> Any:
        raise self._not_ready()

    def load_performance_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
        filter_configured_roster: bool = True,
    ) -> pd.DataFrame:
        raise self._not_ready()

    def load_named_tables(
        self,
        source: Any,
        table_names: tuple[str, ...],
    ) -> Mapping[str, pd.DataFrame]:
        raise self._not_ready()

    def load_drills_data(
        self,
        source: Any,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        raise self._not_ready()

    def load_forecast_data(
        self,
        source: Any,
    ) -> pd.DataFrame:
        raise self._not_ready()

    def load_match_analysis_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        raise self._not_ready()

    def load_report_data(
        self,
        source: Any,
        *,
        source_name: str | None = None,
    ) -> pd.DataFrame:
        raise self._not_ready()


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
        operational=False,
        status_message=(
            "GPExe non è ancora operativo come sorgente dati. "
            "Il PAS continua a utilizzare Excel."
        ),
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

    Finché GPExe non è operativo, una sua selezione resta registrata come richiesta
    ma il provider effettivo consegnato al PAS Core è sempre Excel.
    """
    requested = get_provider_descriptor(provider_id)
    effective = requested if requested.operational else get_provider_descriptor(DEFAULT_PROVIDER_ID)
    return ProviderSelection(
        requested=requested,
        effective=effective,
        provider=get_data_provider(effective.provider_id),
        fallback_applied=requested.provider_id != effective.provider_id,
    )
