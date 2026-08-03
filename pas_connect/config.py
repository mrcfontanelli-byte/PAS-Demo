"""Configurazione indipendente dall'interfaccia per le sorgenti dati PAS."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse

from .exceptions import ConfigurationError


class DataProvider(str, Enum):
    """Sorgenti dati previste dal PAS."""

    EXCEL = "excel"
    GPEXE = "gpexe"


@dataclass(frozen=True)
class GPExeConfig:
    """Parametri non sensibili e credenziali runtime del provider GPExe.

    Le credenziali non devono essere committate: in produzione arriveranno da
    ``st.secrets`` o variabili d'ambiente.
    """

    base_url: str = "https://api.gpexe.com"
    username: str = ""
    password: str = ""
    token: str = ""
    timeout_seconds: float = 30.0
    verify_tls: bool = True

    def validate(self, require_credentials: bool = False) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ConfigurationError("GPExe base_url non valido.")
        if self.timeout_seconds <= 0:
            raise ConfigurationError("Il timeout GPExe deve essere positivo.")
        if require_credentials and not self.token and not (self.username and self.password):
            raise ConfigurationError(
                "Servono token oppure username e password per collegarsi a GPExe."
            )


@dataclass(frozen=True)
class PASConnectConfig:
    """Configurazione complessiva del livello dati.

    Il provider predefinito resta Excel, quindi la release non modifica il
    comportamento corrente dell'applicazione.
    """

    provider: DataProvider = DataProvider.EXCEL
    gpexe: GPExeConfig = field(default_factory=GPExeConfig)
    provider_options: Mapping[str, object] = field(default_factory=dict)

    def validate(self) -> None:
        if self.provider is DataProvider.GPEXE:
            self.gpexe.validate(require_credentials=True)
