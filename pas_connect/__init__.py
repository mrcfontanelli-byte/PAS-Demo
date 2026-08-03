"""Fondamenta del livello di connessione dati del PAS.

Il package mantiene separati provider, persistenza PAS Connect e PAS Core.
L'app continua a usare il caricamento Excel esistente finché la sorgente GPExe
non verrà attivata esplicitamente in una release successiva.
"""

from .config import DataProvider, GPExeConfig, PASConnectConfig
from .client import GPExeClient
from .storage import SnapshotStore
from .database import PASConnectDatabase, ReferenceImportResult
from .sync import sync_reference_data
from .sync import SyncPlan, build_default_sync_plan

__all__ = [
    "DataProvider",
    "GPExeConfig",
    "PASConnectConfig",
    "GPExeClient",
    "SnapshotStore",
    "PASConnectDatabase",
    "ReferenceImportResult",
    "sync_reference_data",
    "SyncPlan",
    "build_default_sync_plan",
]
