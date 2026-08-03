"""Configurazione indipendente dall'interfaccia per le sorgenti dati PAS."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping
from urllib.parse import urlparse

from .exceptions import ConfigurationError




def normalize_gpexe_base_url(value: str) -> str:
    """Normalizza l'indirizzo radice delle API senza rimuovere il prefisso /api.

    L'istanza GPExe fornita espone la documentazione e le REST API sotto
    ``https://e15.gpexe.com/ui/v2/``. Sono rimossi soltanto spazi e slash
    finali, così gli endpoint ``/rest/v2/...`` vengono composti correttamente.
    """
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigurationError("GPExe base_url non valido.")
    return normalized

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

    base_url: str = "https://e15.gpexe.com/ui/v2/"
    username: str = ""
    password: str = ""
    token: str = ""
    timeout_seconds: float = 30.0
    verify_tls: bool = True
    max_retries: int = 3
    retry_backoff_seconds: float = 1.0
    max_retry_delay_seconds: float = 30.0
    max_poll_attempts: int = 10
    poll_interval_seconds: float = 1.0

    def validate(self, require_credentials: bool = False) -> None:
        normalize_gpexe_base_url(self.base_url)
        if self.timeout_seconds <= 0:
            raise ConfigurationError("Il timeout GPExe deve essere positivo.")
        if self.max_retries < 0 or self.max_poll_attempts < 1:
            raise ConfigurationError("I limiti retry/polling GPExe non sono validi.")
        if min(self.retry_backoff_seconds, self.max_retry_delay_seconds, self.poll_interval_seconds) < 0:
            raise ConfigurationError("Gli intervalli retry/polling GPExe non possono essere negativi.")
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
