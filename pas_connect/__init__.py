"""Fondamenta del livello di connessione dati del PAS.

Il package mantiene separati provider, persistenza PAS Connect e PAS Core.
L'app continua a usare il caricamento Excel esistente finché la sorgente GPExe
non verrà attivata esplicitamente in una release successiva.
"""

from .config import DataProvider, GPExeConfig, PASConnectConfig
from .client import GPExeClient
from .storage import SnapshotStore
from .database import PASConnectDatabase, ReferenceImportResult, SessionImportResult, SessionDetailImportResult, AthleteSessionImportResult
from .sync import sync_reference_data, sync_team_sessions, sync_team_session_details, sync_athlete_session_details, run_full_sync, FullSyncEvent
from .sync import SyncPlan, build_default_sync_plan

__all__ = [
    "DataProvider",
    "GPExeConfig",
    "PASConnectConfig",
    "GPExeClient",
    "SnapshotStore",
    "PASConnectDatabase",
    "ReferenceImportResult",
    "SessionImportResult",
    "SessionDetailImportResult",
    "AthleteSessionImportResult",
    "sync_reference_data",
    "sync_team_sessions",
    "sync_team_session_details",
    "sync_athlete_session_details",
    "run_full_sync",
    "FullSyncEvent",
    "SyncPlan",
    "build_default_sync_plan",
]
