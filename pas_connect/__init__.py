"""Fondamenta del livello di connessione dati del PAS.

Il package mantiene separati provider, persistenza PAS Connect e PAS Core.
L'app continua a usare il caricamento Excel esistente finché la sorgente GPExe
non verrà attivata esplicitamente in una release successiva.
"""

from .config import DataProvider, GPExeConfig, PASConnectConfig
from .client import GPExeClient, GPExeGraphQLClient
from .rest_client import GPExeRESTClient, RESTProcessingResponse
from .rest_mapper import map_rest_team_session, map_rest_athlete_session_list, map_rest_athlete_session, map_rest_athlete_reference, map_rest_athlete_identity, index_rest_athlete_identities, map_rest_track_reference, map_rest_scalar_kpis, map_rest_zones
from .rest_service import GPExeRESTService, RESTBundleResult
from .rest_persistence import GPExeRESTIdentityPersistence, RESTIdentityPersistenceResult, GPExeRESTPersistenceGate, RESTPersistenceResult
from .speed_zone_metrics import (
    SpeedZoneDistanceDescriptor, aggregate_speed_zone_values, descriptor_from_snapshot,
)
from .services import GPExeServices
from .provider import GPExeAPIDataProvider, invalidate_team_filter_state, invalidate_athlete_filter_state, invalidate_athlete_session_state, invalidate_athlete_context_state, resolve_team_club_id, store_athlete_fetch_result, athletes_from_team_session_results, team_session_error_diagnostic, normalize_team_session_error_diagnostics, TEAM_SESSION_DIAGNOSTIC_COLUMNS
from .storage import SnapshotStore
from .database import PASConnectDatabase, ReferenceImportResult, SessionImportResult, SessionDetailImportResult, AthleteSessionImportResult
from .metric_profiles import MetricProfileComparison, compare_metric_profiles, format_metric_threshold, normalize_metric_profile
from .metric_catalog import PROVIDER_REGISTRY, catalog_preview_from_csv, planned_provider_entries, read_csv_headers, split_metric_name_unit
from .metric_usage import MODULES, USAGE_STATUSES, USAGE_TYPES, scan_metric_usage, usage_record
from .sync import sync_reference_data, sync_team_sessions, sync_team_session_details, sync_athlete_session_details, sync_tracks, run_full_sync, run_graphql_sync, run_rest_identity_sync, run_rest_sync, retry_sync_session, retry_sync_errors, FullSyncEvent, SyncRequest, SyncRunResult, RESTIdentitySyncResult, SessionSyncResult, SyncProgressEvent
from .sync import SyncPlan, build_default_sync_plan

__all__ = [
    "DataProvider",
    "GPExeConfig",
    "PASConnectConfig",
    "GPExeClient",
    "GPExeGraphQLClient",
    "GPExeRESTClient",
    "RESTProcessingResponse",
    "map_rest_team_session",
    "map_rest_athlete_session_list",
    "map_rest_athlete_session",
    "map_rest_athlete_reference",
    "map_rest_athlete_identity",
    "index_rest_athlete_identities",
    "map_rest_track_reference",
    "map_rest_scalar_kpis",
    "map_rest_zones",
    "GPExeRESTService",
    "RESTBundleResult",
    "GPExeRESTPersistenceGate",
    "RESTPersistenceResult",
    "GPExeRESTIdentityPersistence",
    "RESTIdentityPersistenceResult",
    "SpeedZoneDistanceDescriptor",
    "aggregate_speed_zone_values",
    "descriptor_from_snapshot",
    "GPExeServices",
    "GPExeAPIDataProvider",
    "invalidate_team_filter_state",
    "invalidate_athlete_filter_state",
    "invalidate_athlete_session_state",
    "invalidate_athlete_context_state",
    "resolve_team_club_id",
    "store_athlete_fetch_result",
    "athletes_from_team_session_results",
    "team_session_error_diagnostic",
    "normalize_team_session_error_diagnostics",
    "TEAM_SESSION_DIAGNOSTIC_COLUMNS",
    "SnapshotStore",
    "PASConnectDatabase",
    "ReferenceImportResult",
    "SessionImportResult",
    "SessionDetailImportResult",
    "AthleteSessionImportResult",
    "MetricProfileComparison",
    "compare_metric_profiles",
    "format_metric_threshold",
    "normalize_metric_profile",
    "PROVIDER_REGISTRY",
    "catalog_preview_from_csv",
    "planned_provider_entries",
    "read_csv_headers",
    "split_metric_name_unit",
    "MODULES",
    "USAGE_TYPES",
    "USAGE_STATUSES",
    "scan_metric_usage",
    "usage_record",
    "sync_reference_data",
    "sync_team_sessions",
    "sync_team_session_details",
    "sync_athlete_session_details",
    "sync_tracks",
    "run_full_sync",
    "run_rest_identity_sync",
    "RESTIdentitySyncResult",
    "run_graphql_sync",
    "run_rest_sync",
    "retry_sync_session",
    "retry_sync_errors",
    "SyncRequest",
    "SyncRunResult",
    "SessionSyncResult",
    "SyncProgressEvent",
    "FullSyncEvent",
    "SyncPlan",
    "build_default_sync_plan",
]
