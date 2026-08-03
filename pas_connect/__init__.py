"""Fondamenta del livello di connessione dati del PAS.

La release 3.7.36 introduce soltanto contratti e componenti isolati: l'app
continua a usare il caricamento Excel esistente finché un provider non viene
attivato esplicitamente in una release successiva.
"""

from .config import DataProvider, GPExeConfig, PASConnectConfig
from .client import GPExeClient
from .sync import SyncPlan, build_default_sync_plan

__all__ = [
    "DataProvider",
    "GPExeConfig",
    "PASConnectConfig",
    "GPExeClient",
    "SyncPlan",
    "build_default_sync_plan",
]
