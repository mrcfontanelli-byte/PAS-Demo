"""Livello unico di accesso ai dati del PAS.

La release 3.8.0 mantiene Excel come sorgente operativa predefinita. Il provider
GPExe è predisposto come contratto architetturale, ma non è ancora collegato a
Dashboard, Drills, Match Analysis, Forecast o Report.
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


@dataclass(frozen=True)
class GPExeProvider(PASDataProvider):
    """Provider GPExe predisposto, intenzionalmente non attivo nella v3.8.0."""

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


DEFAULT_PROVIDER_ID = "excel"


def get_data_provider(provider_id: str = DEFAULT_PROVIDER_ID) -> PASDataProvider:
    """Factory centrale. Nella v3.8.0 il default resta sempre Excel."""
    normalized = str(provider_id).strip().lower()
    if normalized == "excel":
        return ExcelProvider()
    if normalized == "gpexe":
        return GPExeProvider()
    raise DataProviderError(f"Provider dati PAS non riconosciuto: {provider_id!r}")
