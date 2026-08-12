"""Database locale isolato per le anagrafiche sincronizzate da PAS Connect.

Il file SQLite non sostituisce il database Excel operativo del PAS. Su
Streamlit Community Cloud il filesystem locale è effimero: la persistenza
oltre reboot/deploy richiederà in futuro un database esterno.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Mapping


SCHEMA_VERSION = 12


@dataclass(frozen=True)
class ReferenceImportResult:
    database_path: Path
    synced_at: str
    counts: dict[str, int]
    sync_run_id: int


@dataclass(frozen=True)
class SessionImportResult:
    database_path: Path
    synced_at: str
    received: int
    inserted: int
    updated: int
    sync_run_id: int


@dataclass(frozen=True)
class SessionDetailImportResult:
    database_path: Path
    synced_at: str
    received: int
    inserted: int
    updated: int
    athlete_rows: int
    metric_headers: int
    failed: int
    sync_run_id: int


@dataclass(frozen=True)
class AthleteSessionImportResult:
    database_path: Path
    synced_at: str
    received: int
    inserted: int
    updated: int
    failed: int
    sync_run_id: int


@dataclass(frozen=True)
class PASConnectDatabase:
    path: Path

    @classmethod
    def default(cls, root: Path | None = None) -> "PASConnectDatabase":
        base = root or Path.cwd()
        return cls(base / ".pas_data" / "pas_connect.sqlite3")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pas_connect_meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_teams (
                    provider_team_id INTEGER PRIMARY KEY,
                    team_name TEXT NOT NULL,
                    club_id INTEGER,
                    season TEXT,
                    sport TEXT,
                    start_date TEXT,
                    end_date TEXT,
                    locked INTEGER NOT NULL DEFAULT 0,
                    provider_updated_at TEXT,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_categories (
                    provider_category_id INTEGER PRIMARY KEY,
                    category_name TEXT NOT NULL,
                    team_id INTEGER,
                    provider_color TEXT,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_tags (
                    provider_tag_id INTEGER PRIMARY KEY,
                    tag_name TEXT NOT NULL,
                    team_id INTEGER,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_athletes (
                    provider_player_id INTEGER PRIMARY KEY,
                    external_player_id TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    player_name TEXT NOT NULL,
                    short_name TEXT,
                    birth_date TEXT,
                    club_id INTEGER,
                    photo_url TEXT,
                    v0 REAL,
                    a0 REAL,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_athlete_team_memberships (
                    provider_player_id INTEGER NOT NULL,
                    team_id INTEGER NOT NULL,
                    season TEXT NOT NULL DEFAULT '',
                    jersey_number TEXT,
                    is_active INTEGER,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL DEFAULT '{}',
                    PRIMARY KEY(provider_player_id, team_id, season),
                    FOREIGN KEY(provider_player_id)
                        REFERENCES gpexe_athletes(provider_player_id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_gpexe_athlete_memberships_context
                ON gpexe_athlete_team_memberships(team_id, season, provider_player_id);

                CREATE TABLE IF NOT EXISTS gpexe_team_sessions (
                    provider_session_id INTEGER PRIMARY KEY,
                    team_id INTEGER,
                    category_id INTEGER,
                    session_name TEXT NOT NULL,
                    notes TEXT,
                    start_timestamp TEXT,
                    end_timestamp TEXT,
                    total_time TEXT,
                    is_stats_valid INTEGER NOT NULL DEFAULT 0,
                    drill_enabled INTEGER NOT NULL DEFAULT 0,
                    state TEXT,
                    submitted_by TEXT,
                    provider_created_at TEXT,
                    provider_updated_at TEXT,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_team_session_details (
                    provider_session_id INTEGER PRIMARY KEY,
                    provider_general_id INTEGER,
                    team_id INTEGER,
                    nature TEXT,
                    start_timestamp TEXT,
                    category_id INTEGER,
                    category_name TEXT,
                    athlete_count INTEGER,
                    total_time TEXT,
                    notes TEXT,
                    provider_updated_at TEXT,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    FOREIGN KEY(provider_session_id) REFERENCES gpexe_team_sessions(provider_session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gpexe_session_metric_headers (
                    provider_session_id INTEGER NOT NULL,
                    position INTEGER NOT NULL,
                    metric_label TEXT NOT NULL,
                    metric_unit TEXT,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY(provider_session_id, position),
                    FOREIGN KEY(provider_session_id) REFERENCES gpexe_team_sessions(provider_session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gpexe_session_athlete_rows (
                    provider_session_id INTEGER NOT NULL,
                    provider_athlete_session_id INTEGER NOT NULL,
                    athlete_first_name TEXT,
                    athlete_last_name TEXT,
                    athlete_role TEXT,
                    state TEXT,
                    metrics_json TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    PRIMARY KEY(provider_session_id, provider_athlete_session_id),
                    FOREIGN KEY(provider_session_id) REFERENCES gpexe_team_sessions(provider_session_id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS gpexe_athlete_session_details (
                    provider_athlete_session_id INTEGER PRIMARY KEY,
                    provider_session_id INTEGER,
                    provider_player_id INTEGER,
                    drill_id INTEGER,
                    track_id INTEGER,
                    start_timestamp TEXT,
                    end_timestamp TEXT,
                    duration TEXT,
                    state TEXT,
                    starter INTEGER,
                    is_stats_valid INTEGER,
                    need_reprocess INTEGER,
                    provider_updated_at TEXT,
                    metrics_json TEXT NOT NULL,
                    zones_json TEXT NOT NULL,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    FOREIGN KEY(provider_session_id) REFERENCES gpexe_team_sessions(provider_session_id) ON DELETE CASCADE
                );


                CREATE TABLE IF NOT EXISTS gpexe_tracks (
                    provider_track_id TEXT PRIMARY KEY,
                    team_id INTEGER,
                    track_name TEXT,
                    synced_at TEXT NOT NULL,
                    raw_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS gpexe_sync_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    resource_group TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    status TEXT NOT NULL,
                    teams_count INTEGER NOT NULL DEFAULT 0,
                    categories_count INTEGER NOT NULL DEFAULT 0,
                    tags_count INTEGER NOT NULL DEFAULT 0,
                    athletes_count INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT
                );

                CREATE TABLE IF NOT EXISTS gpexe_session_sync_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sync_run_id INTEGER NOT NULL,
                    provider_session_id INTEGER NOT NULL,
                    team_id INTEGER,
                    status TEXT NOT NULL
                        CHECK(status IN ('SUCCESS','PARTIAL','FAILED','SKIPPED')),
                    readiness TEXT NOT NULL
                        CHECK(readiness IN ('READY','INCOMPLETE')),
                    athlete_sessions_count INTEGER NOT NULL DEFAULT 0,
                    tracks_count INTEGER NOT NULL DEFAULT 0,
                    kpis_count INTEGER NOT NULL DEFAULT 0,
                    operation_name TEXT,
                    variables_json TEXT,
                    diagnostics_json TEXT,
                    error_message TEXT,
                    started_at TEXT NOT NULL,
                    completed_at TEXT,
                    UNIQUE(sync_run_id, provider_session_id),
                    FOREIGN KEY(sync_run_id) REFERENCES gpexe_sync_runs(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_sync_results_session
                ON gpexe_session_sync_results(provider_session_id, completed_at);

                CREATE INDEX IF NOT EXISTS idx_sync_results_run
                ON gpexe_session_sync_results(sync_run_id, status);

                CREATE TABLE IF NOT EXISTS gpexe_athlete_session_kpis (
                    provider_athlete_session_id INTEGER NOT NULL,
                    source TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    value TEXT,
                    kpi_group TEXT,
                    uom TEXT,
                    unit TEXT,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY(provider_athlete_session_id, source, position),
                    FOREIGN KEY(provider_athlete_session_id)
                    REFERENCES gpexe_athlete_session_details(provider_athlete_session_id)
                    ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS pas_metric_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    team_id TEXT NOT NULL,
                    team_name TEXT NOT NULL,
                    season TEXT NOT NULL,
                    canonical_metric TEXT NOT NULL,
                    provider_metric_name TEXT NOT NULL,
                    threshold_min REAL,
                    threshold_max REAL,
                    threshold_min_inclusive INTEGER NOT NULL DEFAULT 0,
                    threshold_max_inclusive INTEGER NOT NULL DEFAULT 0,
                    threshold_unit TEXT NOT NULL,
                    source TEXT NOT NULL,
                    valid_from TEXT,
                    valid_to TEXT,
                    verified INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_pas_metric_profiles_team_season
                ON pas_metric_profiles(team_id, season);

                CREATE TABLE IF NOT EXISTS pas_metric_catalog (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_metric TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    acquisition_mode TEXT NOT NULL,
                    provider_metric_name TEXT NOT NULL DEFAULT '',
                    category TEXT NOT NULL,
                    metric_type TEXT NOT NULL,
                    canonical_unit TEXT,
                    provider_unit TEXT,
                    value_type TEXT NOT NULL,
                    requires_profile INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL DEFAULT 0,
                    is_contextual INTEGER NOT NULL DEFAULT 0,
                    description TEXT,
                    source_template TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(canonical_metric, provider, provider_metric_name)
                );

                CREATE INDEX IF NOT EXISTS idx_pas_metric_catalog_provider_category
                ON pas_metric_catalog(provider, category);

                CREATE TABLE IF NOT EXISTS pas_metric_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    canonical_metric TEXT NOT NULL,
                    module TEXT NOT NULL,
                    view_name TEXT NOT NULL,
                    usage_type TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'MANUAL'
                        CHECK(status IN ('VERIFIED','PROBABLE','AMBIGUOUS','MANUAL')),
                    enabled INTEGER NOT NULL DEFAULT 1,
                    required INTEGER NOT NULL DEFAULT 0,
                    display_order INTEGER NOT NULL DEFAULT 0,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(canonical_metric, module, view_name, usage_type)
                );

                CREATE INDEX IF NOT EXISTS idx_pas_metric_usage_module_view
                ON pas_metric_usage(module, view_name, usage_type);
                """
            )
            usage_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(pas_metric_usage)")
            }
            if "status" not in usage_columns:
                connection.execute(
                    """ALTER TABLE pas_metric_usage ADD COLUMN status TEXT NOT NULL
                    DEFAULT 'MANUAL' CHECK(status IN ('VERIFIED','PROBABLE','AMBIGUOUS','MANUAL'))"""
                )
            athlete_columns = {row[1] for row in connection.execute("PRAGMA table_info(gpexe_athletes)")}
            for name, definition in {
                "team_id": "INTEGER", "jersey_number": "TEXT",
                "is_active": "INTEGER", "has_tracks": "INTEGER",
            }.items():
                if name not in athlete_columns:
                    connection.execute(
                        f"ALTER TABLE gpexe_athletes ADD COLUMN {name} {definition}"
                    )
            track_columns = {row[1] for row in connection.execute("PRAGMA table_info(gpexe_tracks)")}
            for name, definition in {"athlete_id": "INTEGER", "has_cardio": "INTEGER"}.items():
                if name not in track_columns:
                    connection.execute(f"ALTER TABLE gpexe_tracks ADD COLUMN {name} {definition}")
            athlete_session_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(gpexe_athlete_session_details)")
            }
            for name, definition in {
                "master_athlete_session": "TEXT", "total_time_json": "TEXT",
                "template_id": "TEXT",
            }.items():
                if name not in athlete_session_columns:
                    connection.execute(
                        f"ALTER TABLE gpexe_athlete_session_details ADD COLUMN {name} {definition}"
                    )
            columns = {row[1] for row in connection.execute("PRAGMA table_info(gpexe_sync_runs)")}
            if "sessions_count" not in columns:
                connection.execute(
                    "ALTER TABLE gpexe_sync_runs ADD COLUMN sessions_count INTEGER NOT NULL DEFAULT 0"
                )
            if "inserted_count" not in columns:
                connection.execute(
                    "ALTER TABLE gpexe_sync_runs ADD COLUMN inserted_count INTEGER NOT NULL DEFAULT 0"
                )
            if "updated_count" not in columns:
                connection.execute(
                    "ALTER TABLE gpexe_sync_runs ADD COLUMN updated_count INTEGER NOT NULL DEFAULT 0"
                )
            if "failed_count" not in columns:
                connection.execute(
                    "ALTER TABLE gpexe_sync_runs ADD COLUMN failed_count INTEGER NOT NULL DEFAULT 0"
                )
            for name, definition in {
                "provider": "TEXT", "team_id": "INTEGER", "season": "TEXT",
                "mode": "TEXT", "date_from": "TEXT", "date_to": "TEXT",
                "requested_count": "INTEGER NOT NULL DEFAULT 0",
                "success_count": "INTEGER NOT NULL DEFAULT 0",
                "partial_count": "INTEGER NOT NULL DEFAULT 0",
                "skipped_count": "INTEGER NOT NULL DEFAULT 0",
                "retry_of_run_id": "INTEGER", "summary_json": "TEXT",
            }.items():
                if name not in columns:
                    connection.execute(f"ALTER TABLE gpexe_sync_runs ADD COLUMN {name} {definition}")

            connection.execute(
                """INSERT OR IGNORE INTO gpexe_athlete_team_memberships(
                provider_player_id, team_id, season, jersey_number, is_active,
                first_seen_at, last_seen_at, raw_json)
                SELECT DISTINCT d.provider_player_id, s.team_id, u.season,
                    a.jersey_number, a.is_active, a.synced_at, a.synced_at, '{}'
                FROM gpexe_athlete_session_details d
                JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
                JOIN gpexe_session_sync_results r
                    ON r.provider_session_id=s.provider_session_id AND r.team_id=s.team_id
                JOIN gpexe_sync_runs u ON u.id=r.sync_run_id
                JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
                WHERE d.provider_player_id IS NOT NULL AND s.team_id IS NOT NULL
                    AND u.season IS NOT NULL AND TRIM(u.season)<>''"""
            )
            connection.execute(
                """INSERT OR IGNORE INTO gpexe_athlete_team_memberships(
                provider_player_id, team_id, season, jersey_number, is_active,
                first_seen_at, last_seen_at, raw_json)
                SELECT DISTINCT d.provider_player_id, s.team_id,
                    REPLACE(t.season, '-', '/'), a.jersey_number, a.is_active,
                    a.synced_at, a.synced_at, '{}'
                FROM gpexe_athlete_session_details d
                JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
                JOIN gpexe_teams t ON t.provider_team_id=s.team_id
                JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
                WHERE d.provider_player_id IS NOT NULL AND s.team_id IS NOT NULL
                    AND t.season IS NOT NULL AND TRIM(t.season)<>''"""
            )
            connection.execute(
                """WITH profile_seasons AS (
                    SELECT CAST(team_id AS INTEGER) AS team_id,
                        REPLACE(MIN(season), '-', '/') AS season
                    FROM pas_metric_profiles
                    WHERE team_id GLOB '[0-9]*' AND season IS NOT NULL AND TRIM(season)<>''
                    GROUP BY CAST(team_id AS INTEGER)
                    HAVING COUNT(DISTINCT REPLACE(season, '-', '/'))=1
                )
                INSERT OR IGNORE INTO gpexe_athlete_team_memberships(
                provider_player_id, team_id, season, jersey_number, is_active,
                first_seen_at, last_seen_at, raw_json)
                SELECT DISTINCT d.provider_player_id, s.team_id, p.season,
                    a.jersey_number, a.is_active, a.synced_at, a.synced_at, '{}'
                FROM gpexe_athlete_session_details d
                JOIN gpexe_team_sessions s ON s.provider_session_id=d.provider_session_id
                JOIN profile_seasons p ON p.team_id=s.team_id
                JOIN gpexe_athletes a ON a.provider_player_id=d.provider_player_id
                WHERE d.provider_player_id IS NOT NULL AND s.team_id IS NOT NULL"""
            )
            connection.execute(
                """INSERT OR IGNORE INTO gpexe_athlete_team_memberships(
                provider_player_id, team_id, season, jersey_number, is_active,
                first_seen_at, last_seen_at, raw_json)
                SELECT a.provider_player_id, a.team_id, '', a.jersey_number, a.is_active,
                    a.synced_at, a.synced_at, '{}'
                FROM gpexe_athletes a
                WHERE a.team_id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM gpexe_athlete_team_memberships m
                    WHERE m.provider_player_id=a.provider_player_id AND m.team_id=a.team_id
                )"""
            )

            connection.execute(
                "INSERT INTO pas_connect_meta(key, value) VALUES('schema_version', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (str(SCHEMA_VERSION),),
            )
            connection.commit()

    @staticmethod
    def _json(row: Mapping[str, Any]) -> str:
        return json.dumps(dict(row), ensure_ascii=False, sort_keys=True, default=str)

    def replace_reference_data(self, snapshot: Mapping[str, Any]) -> ReferenceImportResult:
        resources = snapshot.get("resources")
        if not isinstance(resources, Mapping):
            raise ValueError("Snapshot GPExe priva del blocco resources.")
        synced_at = str(snapshot.get("synced_at") or datetime.now(timezone.utc).isoformat())
        teams = list(resources.get("teams") or [])
        categories = list(resources.get("categories") or [])
        tags = list(resources.get("tags") or [])
        athletes = list(resources.get("athletes") or [])
        counts = {
            "teams": len(teams),
            "categories": len(categories),
            "tags": len(tags),
            "athletes": len(athletes),
        }

        self.initialize()
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO gpexe_sync_runs(resource_group, started_at, status) VALUES(?, ?, ?)",
                ("reference", synced_at, "running"),
            )
            run_id = int(cursor.lastrowid)
            connection.commit()
            try:
                connection.execute("BEGIN")
                for row in teams:
                    connection.execute(
                        """
                        INSERT INTO gpexe_teams(
                            provider_team_id, team_name, club_id, season, sport,
                            start_date, end_date, locked, provider_updated_at,
                            synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_team_id) DO UPDATE SET
                            team_name=excluded.team_name,
                            club_id=excluded.club_id,
                            season=excluded.season,
                            sport=excluded.sport,
                            start_date=excluded.start_date,
                            end_date=excluded.end_date,
                            locked=excluded.locked,
                            provider_updated_at=excluded.provider_updated_at,
                            synced_at=excluded.synced_at,
                            raw_json=excluded.raw_json
                        """,
                        (
                            row["provider_team_id"], row["team_name"], row.get("club_id"),
                            row.get("season"), row.get("sport"), row.get("start_date"),
                            row.get("end_date"), int(bool(row.get("locked"))),
                            row.get("updated_at"), synced_at, self._json(row),
                        ),
                    )
                for row in categories:
                    connection.execute(
                        """
                        INSERT INTO gpexe_categories(
                            provider_category_id, category_name, team_id,
                            provider_color, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_category_id) DO UPDATE SET
                            category_name=excluded.category_name,
                            team_id=excluded.team_id,
                            provider_color=excluded.provider_color,
                            synced_at=excluded.synced_at,
                            raw_json=excluded.raw_json
                        """,
                        (
                            row["provider_category_id"], row["category_name"], row.get("team_id"),
                            row.get("provider_color"), synced_at, self._json(row),
                        ),
                    )
                for row in tags:
                    connection.execute(
                        """
                        INSERT INTO gpexe_tags(
                            provider_tag_id, tag_name, team_id, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(provider_tag_id) DO UPDATE SET
                            tag_name=excluded.tag_name,
                            team_id=excluded.team_id,
                            synced_at=excluded.synced_at,
                            raw_json=excluded.raw_json
                        """,
                        (
                            row["provider_tag_id"], row["tag_name"], row.get("team_id"),
                            synced_at, self._json(row),
                        ),
                    )
                for row in athletes:
                    connection.execute(
                        """
                        INSERT INTO gpexe_athletes(
                            provider_player_id, external_player_id, first_name, last_name,
                            player_name, short_name, birth_date, club_id, photo_url,
                            v0, a0, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_player_id) DO UPDATE SET
                            external_player_id=excluded.external_player_id,
                            first_name=excluded.first_name,
                            last_name=excluded.last_name,
                            player_name=excluded.player_name,
                            short_name=excluded.short_name,
                            birth_date=excluded.birth_date,
                            club_id=excluded.club_id,
                            photo_url=excluded.photo_url,
                            v0=excluded.v0,
                            a0=excluded.a0,
                            synced_at=excluded.synced_at,
                            raw_json=excluded.raw_json
                        """,
                        (
                            row["provider_player_id"], row.get("external_player_id"),
                            row.get("first_name"), row.get("last_name"), row["player_name"],
                            row.get("short_name"), row.get("birth_date"), row.get("club_id"),
                            row.get("photo_url"), row.get("v0"), row.get("a0"),
                            synced_at, self._json(row),
                        ),
                    )
                completed_at = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """
                    UPDATE gpexe_sync_runs SET completed_at=?, status='success',
                        teams_count=?, categories_count=?, tags_count=?, athletes_count=?
                    WHERE id=?
                    """,
                    (
                        completed_at, counts["teams"], counts["categories"],
                        counts["tags"], counts["athletes"], run_id,
                    ),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                connection.execute(
                    "UPDATE gpexe_sync_runs SET completed_at=?, status='failed', error_message=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
                )
                connection.commit()
                raise

        return ReferenceImportResult(self.path, synced_at, counts, run_id)

    def replace_tracks(self, payload: Mapping[str, Any]) -> int:
        tracks = list(payload.get("tracks") or [])
        synced_at = str(payload.get("synced_at") or datetime.now(timezone.utc).isoformat())
        self.initialize()
        with self.connect() as connection:
            connection.execute("DELETE FROM gpexe_tracks")
            for index, row in enumerate(tracks):
                track_id = row.get("id") or row.get("pk") or row.get("uuid") or f"row-{index}"
                name = row.get("name") or row.get("title") or row.get("label")
                team = row.get("team") or row.get("team_id")
                if isinstance(team, Mapping):
                    team = team.get("id")
                connection.execute(
                    "INSERT INTO gpexe_tracks(provider_track_id, team_id, track_name, synced_at, raw_json) VALUES(?,?,?,?,?)",
                    (str(track_id), team, str(name) if name is not None else None, synced_at, self._json(row)),
                )
            connection.commit()
        return len(tracks)

    def upsert_team_sessions(self, payload: Mapping[str, Any]) -> SessionImportResult:
        sessions = payload.get("sessions")
        if not isinstance(sessions, list):
            raise ValueError("Payload GPExe privo della lista sessions.")
        synced_at = str(payload.get("synced_at") or datetime.now(timezone.utc).isoformat())
        self.initialize()
        inserted = 0
        updated = 0
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO gpexe_sync_runs(resource_group, started_at, status) VALUES(?, ?, ?)",
                ("team_sessions", synced_at, "running"),
            )
            run_id = int(cursor.lastrowid)
            connection.commit()
            try:
                connection.execute("BEGIN")
                for row in sessions:
                    session_id = int(row["provider_session_id"])
                    exists = connection.execute(
                        "SELECT 1 FROM gpexe_team_sessions WHERE provider_session_id=?",
                        (session_id,),
                    ).fetchone() is not None
                    connection.execute(
                        """
                        INSERT INTO gpexe_team_sessions(
                            provider_session_id, team_id, category_id, session_name, notes,
                            start_timestamp, end_timestamp, total_time, is_stats_valid,
                            drill_enabled, state, submitted_by, provider_created_at,
                            provider_updated_at, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_session_id) DO UPDATE SET
                            team_id=excluded.team_id, category_id=excluded.category_id,
                            session_name=excluded.session_name, notes=excluded.notes,
                            start_timestamp=excluded.start_timestamp, end_timestamp=excluded.end_timestamp,
                            total_time=excluded.total_time, is_stats_valid=excluded.is_stats_valid,
                            drill_enabled=excluded.drill_enabled, state=excluded.state,
                            submitted_by=excluded.submitted_by, provider_created_at=excluded.provider_created_at,
                            provider_updated_at=excluded.provider_updated_at, synced_at=excluded.synced_at,
                            raw_json=excluded.raw_json
                        """,
                        (
                            session_id, row.get("team_id"), row.get("category_id"), row["session_name"],
                            row.get("notes"), row.get("start_timestamp"), row.get("end_timestamp"),
                            row.get("total_time"), int(bool(row.get("is_stats_valid"))),
                            int(bool(row.get("drill_enabled"))), row.get("state"),
                            str(row.get("submitted_by")) if row.get("submitted_by") is not None else None,
                            row.get("created_at"), row.get("updated_at"), synced_at, self._json(row),
                        ),
                    )
                    updated += int(exists)
                    inserted += int(not exists)
                completed_at = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """UPDATE gpexe_sync_runs SET completed_at=?, status='success',
                    sessions_count=?, inserted_count=?, updated_count=? WHERE id=?""",
                    (completed_at, len(sessions), inserted, updated, run_id),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                connection.execute(
                    "UPDATE gpexe_sync_runs SET completed_at=?, status='failed', error_message=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
                )
                connection.commit()
                raise
        return SessionImportResult(self.path, synced_at, len(sessions), inserted, updated, run_id)

    def team_session_ids_for_detail_sync(self, *, only_missing: bool = True) -> list[int]:
        if not self.path.is_file():
            return []
        self.initialize()
        with self.connect() as connection:
            if only_missing:
                rows = connection.execute(
                    """SELECT s.provider_session_id FROM gpexe_team_sessions s
                    LEFT JOIN gpexe_team_session_details d
                    ON d.provider_session_id=s.provider_session_id
                    WHERE d.provider_session_id IS NULL
                    ORDER BY s.start_timestamp, s.provider_session_id"""
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT provider_session_id FROM gpexe_team_sessions ORDER BY start_timestamp, provider_session_id"
                ).fetchall()
            return [int(row[0]) for row in rows]

    def upsert_team_session_details(self, payload: Mapping[str, Any]) -> SessionDetailImportResult:
        details = payload.get("details")
        errors = payload.get("errors") or []
        if not isinstance(details, list):
            raise ValueError("Payload GPExe privo della lista details.")
        synced_at = str(payload.get("synced_at") or datetime.now(timezone.utc).isoformat())
        self.initialize()
        inserted = updated = athlete_rows_count = metric_headers_count = 0
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO gpexe_sync_runs(resource_group, started_at, status) VALUES(?, ?, ?)",
                ("team_session_details", synced_at, "running"),
            )
            run_id = int(cursor.lastrowid)
            connection.commit()
            try:
                connection.execute("BEGIN")
                for row in details:
                    session_id = int(row["provider_session_id"])
                    exists = connection.execute(
                        "SELECT 1 FROM gpexe_team_session_details WHERE provider_session_id=?",
                        (session_id,),
                    ).fetchone() is not None
                    timing = row.get("timing") if isinstance(row.get("timing"), Mapping) else {}
                    connection.execute(
                        """INSERT INTO gpexe_team_session_details(
                        provider_session_id, provider_general_id, team_id, nature, start_timestamp,
                        category_id, category_name, athlete_count, total_time, notes,
                        provider_updated_at, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_session_id) DO UPDATE SET
                        provider_general_id=excluded.provider_general_id, team_id=excluded.team_id,
                        nature=excluded.nature, start_timestamp=excluded.start_timestamp,
                        category_id=excluded.category_id, category_name=excluded.category_name,
                        athlete_count=excluded.athlete_count, total_time=excluded.total_time,
                        notes=excluded.notes, provider_updated_at=excluded.provider_updated_at,
                        synced_at=excluded.synced_at, raw_json=excluded.raw_json""",
                        (session_id, row.get("provider_general_id"), row.get("team_id"), row.get("nature"),
                         row.get("start_timestamp"), row.get("category_id"), row.get("category_name"),
                         row.get("athlete_count"), row.get("total_time"), row.get("notes"),
                         timing.get("updated_on"), synced_at, self._json(row.get("raw") or row)),
                    )
                    inserted += int(not exists); updated += int(exists)
                    connection.execute("DELETE FROM gpexe_session_metric_headers WHERE provider_session_id=?", (session_id,))
                    for header in row.get("headers") or []:
                        connection.execute(
                            """INSERT INTO gpexe_session_metric_headers(
                            provider_session_id, position, metric_label, metric_unit, raw_json
                            ) VALUES (?, ?, ?, ?, ?)""",
                            (session_id, int(header["position"]), str(header["label"]),
                             str(header.get("unit")) if header.get("unit") is not None else None,
                             self._json(header.get("raw") or header)),
                        )
                        metric_headers_count += 1
                    connection.execute("DELETE FROM gpexe_session_athlete_rows WHERE provider_session_id=?", (session_id,))
                    for athlete_row in row.get("athlete_rows") or []:
                        athlete_session_id = athlete_row.get("provider_athlete_session_id")
                        if athlete_session_id is None:
                            continue
                        athlete = athlete_row.get("athlete") if isinstance(athlete_row.get("athlete"), Mapping) else {}
                        connection.execute(
                            """INSERT INTO gpexe_session_athlete_rows(
                            provider_session_id, provider_athlete_session_id, athlete_first_name,
                            athlete_last_name, athlete_role, state, metrics_json, raw_json, synced_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (session_id, int(athlete_session_id), athlete.get("first_name"), athlete.get("last_name"),
                             athlete.get("role"), athlete_row.get("state"),
                             json.dumps(athlete_row.get("metrics") or {}, ensure_ascii=False, default=str),
                             self._json(athlete_row), synced_at),
                        )
                        athlete_rows_count += 1
                completed_at = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """UPDATE gpexe_sync_runs SET completed_at=?, status='success',
                    sessions_count=?, inserted_count=?, updated_count=?, failed_count=? WHERE id=?""",
                    (completed_at, len(details), inserted, updated, len(errors), run_id),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                connection.execute(
                    "UPDATE gpexe_sync_runs SET completed_at=?, status='failed', error_message=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
                )
                connection.commit()
                raise
        return SessionDetailImportResult(self.path, synced_at, len(details), inserted, updated,
                                         athlete_rows_count, metric_headers_count, len(errors), run_id)

    def athlete_session_refs_for_detail_sync(self, *, only_missing: bool = True) -> list[tuple[int, int]]:
        """Restituisce Athlete Sessions collegate alle Team Sessions già importate."""
        if not self.path.is_file():
            return []
        self.initialize()
        with self.connect() as connection:
            sql = """SELECT r.provider_athlete_session_id, r.provider_session_id
                     FROM gpexe_session_athlete_rows r"""
            if only_missing:
                sql += """ LEFT JOIN gpexe_athlete_session_details d
                           ON d.provider_athlete_session_id=r.provider_athlete_session_id
                           WHERE d.provider_athlete_session_id IS NULL"""
            sql += " ORDER BY r.provider_session_id, r.provider_athlete_session_id"
            rows = connection.execute(sql).fetchall()
            return [(int(row[0]), int(row[1])) for row in rows]

    def upsert_athlete_session_details(self, payload: Mapping[str, Any]) -> AthleteSessionImportResult:
        details = payload.get("details")
        errors = payload.get("errors") or []
        if not isinstance(details, list):
            raise ValueError("Payload GPExe privo della lista details Athlete Sessions.")
        synced_at = str(payload.get("synced_at") or datetime.now(timezone.utc).isoformat())
        self.initialize()
        inserted = updated = 0
        with self.connect() as connection:
            cursor = connection.execute(
                "INSERT INTO gpexe_sync_runs(resource_group, started_at, status) VALUES(?, ?, ?)",
                ("athlete_session_details", synced_at, "running"),
            )
            run_id = int(cursor.lastrowid)
            connection.commit()
            try:
                connection.execute("BEGIN")
                for row in details:
                    athlete_session_id = int(row["provider_athlete_session_id"])
                    exists = connection.execute(
                        "SELECT 1 FROM gpexe_athlete_session_details WHERE provider_athlete_session_id=?",
                        (athlete_session_id,),
                    ).fetchone() is not None
                    connection.execute(
                        """INSERT INTO gpexe_athlete_session_details(
                        provider_athlete_session_id, provider_session_id, provider_player_id, drill_id, track_id,
                        start_timestamp, end_timestamp, duration, state, starter, is_stats_valid, need_reprocess,
                        provider_updated_at, metrics_json, zones_json, synced_at, raw_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(provider_athlete_session_id) DO UPDATE SET
                        provider_session_id=excluded.provider_session_id, provider_player_id=excluded.provider_player_id,
                        drill_id=excluded.drill_id, track_id=excluded.track_id,
                        start_timestamp=excluded.start_timestamp, end_timestamp=excluded.end_timestamp,
                        duration=excluded.duration, state=excluded.state, starter=excluded.starter,
                        is_stats_valid=excluded.is_stats_valid, need_reprocess=excluded.need_reprocess,
                        provider_updated_at=excluded.provider_updated_at, metrics_json=excluded.metrics_json,
                        zones_json=excluded.zones_json, synced_at=excluded.synced_at, raw_json=excluded.raw_json""",
                        (
                            athlete_session_id, row.get("provider_session_id"), row.get("provider_player_id"),
                            row.get("drill_id"), row.get("track_id"), row.get("start_timestamp"),
                            row.get("end_timestamp"), str(row.get("duration")) if row.get("duration") is not None else None,
                            row.get("state"), int(bool(row.get("starter"))) if row.get("starter") is not None else None,
                            int(bool(row.get("is_stats_valid"))) if row.get("is_stats_valid") is not None else None,
                            int(bool(row.get("need_reprocess"))) if row.get("need_reprocess") is not None else None,
                            row.get("updated_at"), json.dumps(row.get("metrics") or {}, ensure_ascii=False, default=str),
                            json.dumps(row.get("zones") or {}, ensure_ascii=False, default=str),
                            synced_at, self._json(row.get("raw") or row),
                        ),
                    )
                    inserted += int(not exists)
                    updated += int(exists)
                completed_at = datetime.now(timezone.utc).isoformat()
                connection.execute(
                    """UPDATE gpexe_sync_runs SET completed_at=?, status='success',
                    sessions_count=?, inserted_count=?, updated_count=?, failed_count=? WHERE id=?""",
                    (completed_at, len(details), inserted, updated, len(errors), run_id),
                )
                connection.commit()
            except Exception as exc:
                connection.rollback()
                connection.execute(
                    "UPDATE gpexe_sync_runs SET completed_at=?, status='failed', error_message=? WHERE id=?",
                    (datetime.now(timezone.utc).isoformat(), str(exc), run_id),
                )
                connection.commit()
                raise
        return AthleteSessionImportResult(
            self.path, synced_at, len(details), inserted, updated, len(errors), run_id
        )

    def upsert_graphql_athletes(
        self, athletes: list[Mapping[str, Any]], *, season: str | None = None,
    ) -> tuple[int, int]:
        """UPSERT additivo degli Athletes GraphQL nel database PAS Connect."""
        self.initialize()
        synced_at = datetime.now(timezone.utc).isoformat()
        inserted = updated = 0
        with self.connect() as connection:
            for row in athletes:
                athlete_id = int(row["provider_player_id"])
                exists = connection.execute(
                    "SELECT 1 FROM gpexe_athletes WHERE provider_player_id=?", (athlete_id,)
                ).fetchone() is not None
                connection.execute(
                    """INSERT INTO gpexe_athletes(
                    provider_player_id, external_player_id, first_name, last_name, player_name,
                    short_name, birth_date, photo_url, team_id, jersey_number, is_active,
                    has_tracks, synced_at, raw_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(provider_player_id) DO UPDATE SET
                    external_player_id=excluded.external_player_id, first_name=excluded.first_name,
                    last_name=excluded.last_name, player_name=excluded.player_name,
                    short_name=excluded.short_name, birth_date=excluded.birth_date,
                    photo_url=excluded.photo_url,
                    jersey_number=excluded.jersey_number, is_active=excluded.is_active,
                    has_tracks=excluded.has_tracks, synced_at=excluded.synced_at,
                    raw_json=excluded.raw_json""",
                    (
                        athlete_id, row.get("external_player_id"), row.get("first_name"),
                        row.get("last_name"), row["player_name"], row.get("short_name"),
                        row.get("birth_date"), row.get("photo_url"), row.get("team_id"),
                        str(row.get("jersey_number")) if row.get("jersey_number") is not None else None,
                        int(bool(row.get("is_active"))) if row.get("is_active") is not None else None,
                        int(bool(row.get("has_tracks"))) if row.get("has_tracks") is not None else None,
                        synced_at, self._json(row.get("raw") or row),
                    ),
                )
                if row.get("team_id") not in (None, ""):
                    connection.execute(
                        """INSERT INTO gpexe_athlete_team_memberships(
                        provider_player_id, team_id, season, jersey_number, is_active,
                        first_seen_at, last_seen_at, raw_json)
                        VALUES(?,?,?,?,?,?,?,?)
                        ON CONFLICT(provider_player_id, team_id, season) DO UPDATE SET
                        jersey_number=excluded.jersey_number, is_active=excluded.is_active,
                        last_seen_at=excluded.last_seen_at, raw_json=excluded.raw_json""",
                        (
                            athlete_id, int(row["team_id"]), str(season or ""),
                            str(row.get("jersey_number"))
                            if row.get("jersey_number") is not None else None,
                            int(bool(row.get("is_active")))
                            if row.get("is_active") is not None else None,
                            synced_at, synced_at, self._json(row.get("raw") or row),
                        ),
                    )
                inserted += int(not exists)
                updated += int(exists)
            connection.commit()
        return inserted, updated

    def list_metric_profiles(self, *, team_id: Any | None = None) -> list[dict[str, Any]]:
        """Legge i profili senza modificare i dati sincronizzati GPExe."""
        self.initialize()
        with self.connect() as connection:
            if team_id is None:
                rows = connection.execute(
                    "SELECT * FROM pas_metric_profiles ORDER BY team_name, season, canonical_metric, id"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM pas_metric_profiles WHERE team_id=? ORDER BY season, canonical_metric, id",
                    (str(team_id),),
                ).fetchall()
        return [dict(row) for row in rows]

    def list_metric_catalog(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM pas_metric_catalog ORDER BY is_contextual DESC, provider, category, display_name"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_metric_usage(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT * FROM pas_metric_usage
                ORDER BY module, view_name, display_order, canonical_metric, usage_type"""
            ).fetchall()
        return [dict(row) for row in rows]

    def upsert_metric_usage(self, entry: Mapping[str, Any]) -> tuple[int, bool]:
        """Crea o aggiorna un'associazione senza cancellare utilizzi esistenti."""
        from .metric_usage import MODULES, USAGE_STATUSES, USAGE_TYPES

        row = dict(entry)
        for field in ("canonical_metric", "module", "view_name", "usage_type"):
            row[field] = str(row.get(field) or "").strip()
            if not row[field]:
                raise ValueError(f"Campo utilizzo obbligatorio mancante: {field}.")
        if row["module"] not in MODULES:
            raise ValueError(f"Modulo PAS non supportato: {row['module']}.")
        if row["usage_type"] not in USAGE_TYPES:
            raise ValueError(f"Usage type non supportato: {row['usage_type']}.")
        row["status"] = str(row.get("status") or "MANUAL").strip().upper()
        if row["status"] not in USAGE_STATUSES:
            raise ValueError(f"Status utilizzo non supportato: {row['status']}.")
        row["enabled"] = bool(row.get("enabled", True))
        row["required"] = bool(row.get("required", False))
        row["display_order"] = int(row.get("display_order") or 0)
        row["notes"] = str(row.get("notes") or "").strip() or None
        now = datetime.now(timezone.utc).isoformat()
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            usage_id = row.get("id")
            if usage_id not in (None, ""):
                existing = connection.execute(
                    "SELECT id FROM pas_metric_usage WHERE id=?", (int(usage_id),)
                ).fetchone()
            else:
                existing = connection.execute(
                    """SELECT id FROM pas_metric_usage
                    WHERE canonical_metric=? AND module=? AND view_name=? AND usage_type=?""",
                    (row["canonical_metric"], row["module"], row["view_name"], row["usage_type"]),
                ).fetchone()
            if existing:
                usage_id = int(existing["id"])
                connection.execute(
                    """UPDATE pas_metric_usage SET canonical_metric=?, module=?, view_name=?,
                    usage_type=?, status=?, enabled=?, required=?, display_order=?, notes=?, updated_at=?
                    WHERE id=?""",
                    (row["canonical_metric"], row["module"], row["view_name"],
                     row["usage_type"], row["status"], int(row["enabled"]), int(row["required"]),
                     row["display_order"], row["notes"], now, usage_id),
                )
                inserted = False
            else:
                cursor = connection.execute(
                    """INSERT INTO pas_metric_usage(
                    canonical_metric, module, view_name, usage_type, status, enabled, required,
                    display_order, notes, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                    (row["canonical_metric"], row["module"], row["view_name"],
                     row["usage_type"], row["status"], int(row["enabled"]), int(row["required"]),
                     row["display_order"], row["notes"], now, now),
                )
                usage_id = int(cursor.lastrowid)
                inserted = True
            connection.commit()
        return int(usage_id), inserted

    def import_metric_usage_proposals(self, proposals: list[Mapping[str, Any]]) -> tuple[int, int]:
        inserted = updated = 0
        for proposal in proposals:
            _, was_inserted = self.upsert_metric_usage(proposal)
            inserted += int(was_inserted)
            updated += int(not was_inserted)
        return inserted, updated

    def orphan_metric_usage(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT u.* FROM pas_metric_usage u
                WHERE NOT EXISTS (
                    SELECT 1 FROM pas_metric_catalog c
                    WHERE lower(c.canonical_metric)=lower(u.canonical_metric)
                ) ORDER BY u.id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def catalog_metrics_without_usage(self) -> list[str]:
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT DISTINCT c.canonical_metric FROM pas_metric_catalog c
                WHERE c.is_contextual=0 AND NOT EXISTS (
                    SELECT 1 FROM pas_metric_usage u
                    WHERE lower(u.canonical_metric)=lower(c.canonical_metric)
                ) ORDER BY lower(c.canonical_metric)"""
            ).fetchall()
        return [str(row[0]) for row in rows]

    def upsert_metric_catalog_entry(self, entry: Mapping[str, Any]) -> tuple[int, bool]:
        """UPSERT esplicito e transazionale di un mapping del catalogo."""
        from .metric_catalog import METRIC_TYPES, PROVIDER_REGISTRY, VALUE_TYPES

        row = dict(entry)
        required = ("canonical_metric", "display_name", "provider", "category", "metric_type", "value_type")
        for field in required:
            row[field] = str(row.get(field) or "").strip()
            if not row[field]:
                raise ValueError(f"Campo catalogo obbligatorio mancante: {field}.")
        if row["provider"] not in PROVIDER_REGISTRY:
            raise ValueError(f"Provider non supportato: {row['provider']}.")
        if row["metric_type"] not in METRIC_TYPES:
            raise ValueError(f"Tipo metrica non supportato: {row['metric_type']}.")
        if row["value_type"] not in VALUE_TYPES:
            raise ValueError(f"Value type non supportato: {row['value_type']}.")
        row["acquisition_mode"] = str(
            row.get("acquisition_mode") or PROVIDER_REGISTRY[row["provider"]].acquisition_mode
        ).strip()
        row["provider_metric_name"] = str(row.get("provider_metric_name") or "").strip()
        for field in ("canonical_unit", "provider_unit", "description", "source_template"):
            row[field] = str(row.get(field) or "").strip() or None
        for field in ("requires_profile", "active", "is_contextual"):
            row[field] = bool(row.get(field, False))
        now = datetime.now(timezone.utc).isoformat()
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            catalog_id = row.get("id")
            if catalog_id not in (None, ""):
                existing = connection.execute(
                    "SELECT id FROM pas_metric_catalog WHERE id=?", (int(catalog_id),)
                ).fetchone()
            else:
                existing = connection.execute(
                    """SELECT id FROM pas_metric_catalog
                    WHERE canonical_metric=? AND provider=? AND provider_metric_name=?""",
                    (row["canonical_metric"], row["provider"], row["provider_metric_name"]),
                ).fetchone()
            if existing:
                catalog_id = int(existing["id"])
                connection.execute(
                    """UPDATE pas_metric_catalog SET canonical_metric=?, display_name=?, provider=?,
                    acquisition_mode=?, provider_metric_name=?, category=?, metric_type=?,
                    canonical_unit=?, provider_unit=?, value_type=?, requires_profile=?, active=?,
                    is_contextual=?, description=?, source_template=?, updated_at=? WHERE id=?""",
                    (
                        row["canonical_metric"], row["display_name"], row["provider"],
                        row["acquisition_mode"], row["provider_metric_name"], row["category"],
                        row["metric_type"], row["canonical_unit"], row["provider_unit"],
                        row["value_type"], int(row["requires_profile"]), int(row["active"]),
                        int(row["is_contextual"]), row["description"], row["source_template"],
                        now, catalog_id,
                    ),
                )
                inserted = False
            else:
                cursor = connection.execute(
                    """INSERT INTO pas_metric_catalog(
                    canonical_metric, display_name, provider, acquisition_mode, provider_metric_name,
                    category, metric_type, canonical_unit, provider_unit, value_type,
                    requires_profile, active, is_contextual, description, source_template,
                    created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        row["canonical_metric"], row["display_name"], row["provider"],
                        row["acquisition_mode"], row["provider_metric_name"], row["category"],
                        row["metric_type"], row["canonical_unit"], row["provider_unit"],
                        row["value_type"], int(row["requires_profile"]), int(row["active"]),
                        int(row["is_contextual"]), row["description"], row["source_template"],
                        now, now,
                    ),
                )
                catalog_id = int(cursor.lastrowid)
                inserted = True
            connection.commit()
        return int(catalog_id), inserted

    def import_metric_catalog_proposals(self, proposals: list[Mapping[str, Any]]) -> tuple[int, int]:
        """Inserisce solo mapping assenti, preservando ogni modifica manuale esistente."""
        inserted = preserved = 0
        for proposal in proposals:
            key = (
                str(proposal.get("canonical_metric") or "").strip(),
                str(proposal.get("provider") or "").strip(),
                str(proposal.get("provider_metric_name") or "").strip(),
            )
            self.initialize()
            with self.connect() as connection:
                exists = connection.execute(
                    """SELECT 1 FROM pas_metric_catalog
                    WHERE canonical_metric=? AND provider=? AND provider_metric_name=?""", key
                ).fetchone() is not None
            if exists:
                preserved += 1
            else:
                self.upsert_metric_catalog_entry(proposal)
                inserted += 1
        return inserted, preserved

    def orphan_metric_profiles(self) -> list[dict[str, Any]]:
        """Segnala profili senza metrica canonica catalogata, senza modificarli."""
        self.initialize()
        with self.connect() as connection:
            rows = connection.execute(
                """SELECT p.* FROM pas_metric_profiles p
                WHERE NOT EXISTS (
                    SELECT 1 FROM pas_metric_catalog c
                    WHERE lower(c.canonical_metric)=lower(p.canonical_metric)
                ) ORDER BY p.id"""
            ).fetchall()
        return [dict(row) for row in rows]

    def metric_exists_in_catalog(self, canonical_metric: str) -> bool:
        self.initialize()
        with self.connect() as connection:
            return connection.execute(
                "SELECT 1 FROM pas_metric_catalog WHERE lower(canonical_metric)=lower(?) LIMIT 1",
                (str(canonical_metric).strip(),),
            ).fetchone() is not None

    def metric_profile_catalog_status(self, canonical_metric: str) -> str:
        """Valida la relazione logica senza imporre foreign key ai profili storici."""
        self.initialize()
        with self.connect() as connection:
            catalog_count = int(connection.execute("SELECT COUNT(*) FROM pas_metric_catalog").fetchone()[0])
            exists = connection.execute(
                "SELECT 1 FROM pas_metric_catalog WHERE lower(canonical_metric)=lower(?) LIMIT 1",
                (str(canonical_metric).strip(),),
            ).fetchone() is not None
            if not exists:
                from modules.day_overview_provider import _profile_family
                family = _profile_family(canonical_metric)
                catalog_families = {
                    _profile_family(row[0]) for row in connection.execute(
                        "SELECT canonical_metric FROM pas_metric_catalog WHERE requires_profile=1"
                    )
                }
                exists = family is not None and family in catalog_families
        if exists:
            return "VALID"
        return "CATALOG_EMPTY" if catalog_count == 0 else "ORPHAN"

    def upsert_metric_profile(self, profile: Mapping[str, Any]) -> tuple[int, bool]:
        """Inserisce o aggiorna un profilo preservandone identità e storico."""
        from .metric_profiles import normalize_metric_profile

        row = normalize_metric_profile(profile)
        now = datetime.now(timezone.utc).isoformat()
        self.initialize()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            profile_id = row.get("id")
            if profile_id not in (None, ""):
                existing = connection.execute(
                    "SELECT id FROM pas_metric_profiles WHERE id=?", (int(profile_id),)
                ).fetchone()
            else:
                existing = connection.execute(
                    """SELECT id FROM pas_metric_profiles
                    WHERE team_id=? AND season=? AND canonical_metric=?
                    AND provider_metric_name=? AND source=?
                    AND threshold_min IS ? AND threshold_max IS ?
                    AND threshold_min_inclusive=? AND threshold_max_inclusive=?
                    AND threshold_unit=?
                    AND valid_from IS ? AND valid_to IS ?""",
                    (
                        row["team_id"], row["season"], row["canonical_metric"],
                        row["provider_metric_name"], row["source"],
                        row["threshold_min"], row["threshold_max"],
                        int(row["threshold_min_inclusive"]), int(row["threshold_max_inclusive"]),
                        row["threshold_unit"],
                        row["valid_from"], row["valid_to"],
                    ),
                ).fetchone()
            if existing:
                profile_id = int(existing["id"])
                connection.execute(
                    """UPDATE pas_metric_profiles SET
                    team_id=?, team_name=?, season=?, canonical_metric=?, provider_metric_name=?,
                    threshold_min=?, threshold_max=?, threshold_min_inclusive=?,
                    threshold_max_inclusive=?, threshold_unit=?, source=?, valid_from=?, valid_to=?,
                    verified=?, notes=?, updated_at=? WHERE id=?""",
                    (
                        row["team_id"], row["team_name"], row["season"], row["canonical_metric"],
                        row["provider_metric_name"], row["threshold_min"], row["threshold_max"],
                        int(row["threshold_min_inclusive"]), int(row["threshold_max_inclusive"]),
                        row["threshold_unit"], row["source"], row["valid_from"], row["valid_to"],
                        int(row["verified"]), row["notes"], now, profile_id,
                    ),
                )
                inserted = False
            else:
                cursor = connection.execute(
                    """INSERT INTO pas_metric_profiles(
                    team_id, team_name, season, canonical_metric, provider_metric_name,
                    threshold_min, threshold_max, threshold_min_inclusive, threshold_max_inclusive,
                    threshold_unit, source, valid_from, valid_to, verified, notes, created_at, updated_at
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        row["team_id"], row["team_name"], row["season"], row["canonical_metric"],
                        row["provider_metric_name"], row["threshold_min"], row["threshold_max"],
                        int(row["threshold_min_inclusive"]), int(row["threshold_max_inclusive"]),
                        row["threshold_unit"], row["source"], row["valid_from"], row["valid_to"],
                        int(row["verified"]), row["notes"], now, now,
                    ),
                )
                profile_id = int(cursor.lastrowid)
                inserted = True
            connection.commit()
        return int(profile_id), inserted

    def upsert_graphql_athlete_sessions(
        self, sessions: list[Mapping[str, Any]],
    ) -> tuple[int, int, int, int]:
        """Salva AthleteSessions, track minimi e KPI dinamici in una transazione."""
        self.initialize()
        synced_at = datetime.now(timezone.utc).isoformat()
        inserted = updated = tracks_count = kpis_count = 0
        with self.connect() as connection:
            try:
                connection.execute("BEGIN")
                for row in sessions:
                    session_id = int(row["provider_athlete_session_id"])
                    exists = connection.execute(
                        "SELECT 1 FROM gpexe_athlete_session_details WHERE provider_athlete_session_id=?",
                        (session_id,),
                    ).fetchone() is not None
                    connection.execute(
                        """INSERT INTO gpexe_athlete_session_details(
                        provider_athlete_session_id, provider_session_id, provider_player_id,
                        drill_id, track_id, state, starter, is_stats_valid, metrics_json,
                        zones_json, synced_at, raw_json, master_athlete_session,
                        total_time_json, template_id
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(provider_athlete_session_id) DO UPDATE SET
                        provider_session_id=excluded.provider_session_id,
                        provider_player_id=excluded.provider_player_id, drill_id=excluded.drill_id,
                        track_id=excluded.track_id, state=excluded.state, starter=excluded.starter,
                        is_stats_valid=excluded.is_stats_valid, synced_at=excluded.synced_at,
                        raw_json=excluded.raw_json,
                        master_athlete_session=excluded.master_athlete_session,
                        total_time_json=excluded.total_time_json, template_id=excluded.template_id""",
                        (
                            session_id, row.get("provider_session_id"), row.get("provider_player_id"),
                            row.get("drill_id"), row.get("track_id"), row.get("state"),
                            int(bool(row.get("starter"))) if row.get("starter") is not None else None,
                            int(bool(row.get("is_stats_valid"))) if row.get("is_stats_valid") is not None else None,
                            "{}", "{}", synced_at, self._json(row.get("raw") or row),
                            str(row.get("master_athlete_session")) if row.get("master_athlete_session") is not None else None,
                            json.dumps(row.get("total_time") or {}, ensure_ascii=False, default=str),
                            row.get("template_id"),
                        ),
                    )
                    inserted += int(not exists)
                    updated += int(exists)
                    track = row.get("track") if isinstance(row.get("track"), Mapping) else {}
                    if track.get("id") not in (None, ""):
                        track_athlete = track.get("athlete") if isinstance(track.get("athlete"), Mapping) else {}
                        connection.execute(
                            """INSERT INTO gpexe_tracks(
                            provider_track_id, athlete_id, has_cardio, synced_at, raw_json
                            ) VALUES(?,?,?,?,?) ON CONFLICT(provider_track_id) DO UPDATE SET
                            athlete_id=excluded.athlete_id, has_cardio=excluded.has_cardio,
                            synced_at=excluded.synced_at, raw_json=excluded.raw_json""",
                            (
                                str(track["id"]), track_athlete.get("id"),
                                int(bool(track.get("hasCardio"))) if track.get("hasCardio") is not None else None,
                                synced_at, self._json(track),
                            ),
                        )
                        tracks_count += 1
                    connection.execute(
                        "DELETE FROM gpexe_athlete_session_kpis WHERE provider_athlete_session_id=?",
                        (session_id,),
                    )
                    for source, key in (("identifierKpi", "identifier_kpi"), ("kpi", "kpi")):
                        for position, kpi in enumerate(row.get(key) or []):
                            connection.execute(
                                """INSERT INTO gpexe_athlete_session_kpis(
                                provider_athlete_session_id, source, position, name, value,
                                kpi_group, uom, unit, raw_json
                                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                                (
                                    session_id, source, position, str(kpi.get("name") or ""),
                                    str(kpi.get("value")) if kpi.get("value") is not None else None,
                                    kpi.get("group"), kpi.get("uom"), kpi.get("unit"), self._json(kpi),
                                ),
                            )
                            kpis_count += 1
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return inserted, updated, tracks_count, kpis_count

    def create_sync_run(self, context: Mapping[str, Any]) -> int:
        """Apre un tentativo provider-neutral senza modificare i dati prestazionali."""
        self.initialize()
        started_at = str(context.get("started_at") or datetime.now(timezone.utc).isoformat())
        transport = str(context.get("transport") or "graphql").strip().lower()
        if transport not in {"graphql", "rest"}:
            raise ValueError(f"Transport sync non valido: {transport}")
        resource_group = f"{transport}_session_sync"
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO gpexe_sync_runs(
                resource_group, started_at, status, provider, team_id, season, mode,
                date_from, date_to, requested_count, retry_of_run_id
                ) VALUES(?, ?, 'running', 'gpexe', ?, ?, ?, ?, ?, ?, ?)""",
                (
                    resource_group, started_at, context.get("team_id"), context.get("season"),
                    context.get("mode"), context.get("date_from"), context.get("date_to"),
                    int(context.get("requested_count") or 0), context.get("retry_of_run_id"),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid)

    def record_session_sync_result(self, result: Mapping[str, Any]) -> int:
        """Registra solo diagnostica redatta e risultato terminale di una sessione."""
        self.initialize()
        status = str(result["status"]).upper()
        readiness = str(result["readiness"]).upper()
        if status not in {"SUCCESS", "PARTIAL", "FAILED", "SKIPPED"}:
            raise ValueError(f"Stato sync non valido: {status}")
        if readiness not in {"READY", "INCOMPLETE"}:
            raise ValueError(f"Readiness sync non valida: {readiness}")
        with self.connect() as connection:
            cursor = connection.execute(
                """INSERT INTO gpexe_session_sync_results(
                sync_run_id, provider_session_id, team_id, status, readiness,
                athlete_sessions_count, tracks_count, kpis_count, operation_name,
                variables_json, diagnostics_json, error_message, started_at, completed_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(sync_run_id, provider_session_id) DO UPDATE SET
                status=excluded.status, readiness=excluded.readiness,
                athlete_sessions_count=excluded.athlete_sessions_count,
                tracks_count=excluded.tracks_count, kpis_count=excluded.kpis_count,
                operation_name=excluded.operation_name, variables_json=excluded.variables_json,
                diagnostics_json=excluded.diagnostics_json, error_message=excluded.error_message,
                completed_at=excluded.completed_at""",
                (
                    int(result["sync_run_id"]), int(result["provider_session_id"]),
                    result.get("team_id"), status, readiness,
                    int(result.get("athlete_sessions_count") or 0),
                    int(result.get("tracks_count") or 0), int(result.get("kpis_count") or 0),
                    result.get("operation_name"), json.dumps(result.get("variables") or {}, sort_keys=True),
                    json.dumps(result.get("diagnostics") or [], sort_keys=True),
                    result.get("error_message"),
                    str(result.get("started_at") or datetime.now(timezone.utc).isoformat()),
                    str(result.get("completed_at") or datetime.now(timezone.utc).isoformat()),
                ),
            )
            connection.commit()
            return int(cursor.lastrowid or 0)

    def complete_sync_run(self, run_id: int, summary: Mapping[str, Any]) -> None:
        self.initialize()
        with self.connect() as connection:
            connection.execute(
                """UPDATE gpexe_sync_runs SET completed_at=?, status=?,
                success_count=?, partial_count=?, failed_count=?, skipped_count=?, summary_json=?
                WHERE id=?""",
                (
                    datetime.now(timezone.utc).isoformat(), str(summary.get("status") or "failed"),
                    int(summary.get("success_count") or 0), int(summary.get("partial_count") or 0),
                    int(summary.get("failed_count") or 0), int(summary.get("skipped_count") or 0),
                    json.dumps(dict(summary), ensure_ascii=False, sort_keys=True, default=str), int(run_id),
                ),
            )
            connection.commit()

    def list_session_sync_results(
        self, *, run_id: int | None = None, team_id: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        clauses: list[str] = []
        values: list[Any] = []
        if run_id is not None:
            clauses.append("r.sync_run_id=?")
            values.append(int(run_id))
        if team_id is not None:
            clauses.append("r.team_id=?")
            values.append(int(team_id))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gpexe_session_sync_results'"
            ).fetchone() is None:
                return []
            rows = connection.execute(
                "SELECT r.*, u.resource_group AS transport_resource "
                "FROM gpexe_session_sync_results r "
                "JOIN gpexe_sync_runs u ON u.id=r.sync_run_id" + where
                + " ORDER BY r.id DESC", values,
            ).fetchall()
            return [dict(row) for row in rows]

    def retryable_session_ids(self, run_id: int) -> list[int]:
        return [
            int(row["provider_session_id"])
            for row in self.list_session_sync_results(run_id=run_id)
            if row["status"] in {"FAILED", "PARTIAL"}
        ]

    def latest_ready_session_ids(
        self, *, team_id: int | None = None, transport: str | None = None,
    ) -> list[int]:
        """Restituisce sessioni con almeno un bundle READY, anche dopo un refresh fallito."""
        if not self.path.is_file():
            return []
        params: list[Any] = []
        team_clause = ""
        if team_id is not None:
            team_clause = " AND r.team_id=?"
            params.append(int(team_id))
        transport_clause = ""
        if transport is not None:
            normalized = str(transport).strip().lower()
            if normalized not in {"graphql", "rest"}:
                raise ValueError(f"Transport sync non valido: {transport}")
            transport_clause = " AND u.resource_group=?"
            params.append(f"{normalized}_session_sync")
        with self.connect() as connection:
            if connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='gpexe_session_sync_results'"
            ).fetchone() is None:
                return []
            rows = connection.execute(
                """SELECT DISTINCT r.provider_session_id FROM gpexe_session_sync_results r
                JOIN gpexe_sync_runs u ON u.id=r.sync_run_id
                WHERE r.readiness='READY' AND r.status IN ('SUCCESS','SKIPPED')"""
                + team_clause + transport_clause,
                params,
            ).fetchall()
            return [int(row[0]) for row in rows]

    def upsert_team_session_bundle(
        self, team_session: Mapping[str, Any], athletes: list[Mapping[str, Any]],
        sessions: list[Mapping[str, Any]], *, replace_kpis: bool = True,
        season: str | None = None,
    ) -> tuple[int, int, int]:
        """Pubblica un bundle provider-neutral completo in una sola transazione.

        KPI precedenti vengono sostituiti soltanto se l'intero bundle arriva al
        commit. Un bundle strutturale incompleto non sostituisce mai KPI già
        validi. Qualunque errore lascia quindi operativo l'ultimo bundle valido.
        """
        self.initialize()
        synced_at = datetime.now(timezone.utc).isoformat()
        provider_session_id = int(team_session["provider_session_id"])
        with self.connect() as connection:
            try:
                connection.execute("BEGIN")
                if not replace_kpis:
                    existing_kpis = connection.execute(
                        """SELECT COUNT(*) FROM gpexe_athlete_session_kpis k
                        JOIN gpexe_athlete_session_details d
                          ON d.provider_athlete_session_id=k.provider_athlete_session_id
                        WHERE d.provider_session_id=?""",
                        (provider_session_id,),
                    ).fetchone()[0]
                    if int(existing_kpis):
                        connection.rollback()
                        return 0, 0, 0
                connection.execute(
                    """INSERT INTO gpexe_team_sessions(
                    provider_session_id, team_id, category_id, session_name, notes,
                    start_timestamp, end_timestamp, total_time, is_stats_valid,
                    drill_enabled, state, submitted_by, provider_created_at,
                    provider_updated_at, synced_at, raw_json
                    ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(provider_session_id) DO UPDATE SET
                    team_id=excluded.team_id, category_id=excluded.category_id,
                    session_name=excluded.session_name, notes=excluded.notes,
                    start_timestamp=excluded.start_timestamp, end_timestamp=excluded.end_timestamp,
                    total_time=excluded.total_time, is_stats_valid=excluded.is_stats_valid,
                    drill_enabled=excluded.drill_enabled, state=excluded.state,
                    submitted_by=excluded.submitted_by, provider_created_at=excluded.provider_created_at,
                    provider_updated_at=excluded.provider_updated_at, synced_at=excluded.synced_at,
                    raw_json=excluded.raw_json""",
                    (
                        provider_session_id, team_session.get("team_id"), team_session.get("category_id"),
                        team_session["session_name"], team_session.get("notes"),
                        team_session.get("start_timestamp"), team_session.get("end_timestamp"),
                        team_session.get("total_time"), int(bool(team_session.get("is_stats_valid"))),
                        int(bool(team_session.get("drill_enabled"))), team_session.get("state"),
                        team_session.get("submitted_by"), team_session.get("created_at"),
                        team_session.get("updated_at"), synced_at, self._json(team_session),
                    ),
                )
                for athlete in athletes:
                    connection.execute(
                        """INSERT INTO gpexe_athletes(
                        provider_player_id, external_player_id, first_name, last_name, player_name,
                        short_name, birth_date, photo_url, team_id, jersey_number, is_active,
                        has_tracks, synced_at, raw_json
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(provider_player_id) DO UPDATE SET
                        external_player_id=excluded.external_player_id, first_name=excluded.first_name,
                        last_name=excluded.last_name, player_name=excluded.player_name,
                        short_name=excluded.short_name, birth_date=excluded.birth_date,
                            photo_url=excluded.photo_url,
                            jersey_number=excluded.jersey_number, is_active=excluded.is_active,
                        has_tracks=excluded.has_tracks, synced_at=excluded.synced_at,
                        raw_json=excluded.raw_json""",
                        (
                            int(athlete["provider_player_id"]), athlete.get("external_player_id"),
                            athlete.get("first_name"), athlete.get("last_name"), athlete["player_name"],
                            athlete.get("short_name"), athlete.get("birth_date"), athlete.get("photo_url"),
                            athlete.get("team_id"), athlete.get("jersey_number"),
                            int(bool(athlete.get("is_active"))) if athlete.get("is_active") is not None else None,
                            int(bool(athlete.get("has_tracks"))) if athlete.get("has_tracks") is not None else None,
                            synced_at, self._json(athlete.get("raw") or athlete),
                        ),
                    )
                    if team_session.get("team_id") not in (None, ""):
                        connection.execute(
                            """INSERT INTO gpexe_athlete_team_memberships(
                            provider_player_id, team_id, season, jersey_number, is_active,
                            first_seen_at, last_seen_at, raw_json)
                            VALUES(?,?,?,?,?,?,?,?)
                            ON CONFLICT(provider_player_id, team_id, season) DO UPDATE SET
                            jersey_number=excluded.jersey_number, is_active=excluded.is_active,
                            last_seen_at=excluded.last_seen_at, raw_json=excluded.raw_json""",
                            (
                                int(athlete["provider_player_id"]), int(team_session["team_id"]),
                                str(season or ""),
                                str(athlete.get("jersey_number"))
                                if athlete.get("jersey_number") is not None else None,
                                int(bool(athlete.get("is_active")))
                                if athlete.get("is_active") is not None else None,
                                synced_at, synced_at, self._json(athlete.get("raw") or athlete),
                            ),
                        )
                tracks_count = kpis_count = 0
                for row in sessions:
                    session_id = int(row["provider_athlete_session_id"])
                    connection.execute(
                        """INSERT INTO gpexe_athlete_session_details(
                        provider_athlete_session_id, provider_session_id, provider_player_id,
                        drill_id, track_id, state, starter, is_stats_valid, metrics_json,
                        zones_json, synced_at, raw_json, master_athlete_session,
                        total_time_json, template_id
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(provider_athlete_session_id) DO UPDATE SET
                        provider_session_id=excluded.provider_session_id,
                        provider_player_id=excluded.provider_player_id, drill_id=excluded.drill_id,
                        track_id=excluded.track_id, state=excluded.state, starter=excluded.starter,
                        is_stats_valid=excluded.is_stats_valid, synced_at=excluded.synced_at,
                        raw_json=excluded.raw_json, master_athlete_session=excluded.master_athlete_session,
                        total_time_json=excluded.total_time_json, template_id=excluded.template_id""",
                        (
                            session_id, provider_session_id, row.get("provider_player_id"), row.get("drill_id"),
                            row.get("track_id"), row.get("state"),
                            int(bool(row.get("starter"))) if row.get("starter") is not None else None,
                            int(bool(row.get("is_stats_valid"))) if row.get("is_stats_valid") is not None else None,
                            "{}", "{}", synced_at, self._json(row.get("raw") or row),
                            str(row.get("master_athlete_session")) if row.get("master_athlete_session") is not None else None,
                            json.dumps(row.get("total_time") or {}, default=str), row.get("template_id"),
                        ),
                    )
                    track = row.get("track") if isinstance(row.get("track"), Mapping) else {}
                    if track.get("id") not in (None, ""):
                        track_athlete = track.get("athlete") if isinstance(track.get("athlete"), Mapping) else {}
                        connection.execute(
                            """INSERT INTO gpexe_tracks(provider_track_id, athlete_id, has_cardio, synced_at, raw_json)
                            VALUES(?,?,?,?,?) ON CONFLICT(provider_track_id) DO UPDATE SET
                            athlete_id=excluded.athlete_id, has_cardio=excluded.has_cardio,
                            synced_at=excluded.synced_at, raw_json=excluded.raw_json""",
                            (str(track["id"]), track_athlete.get("id"),
                             int(bool(track.get("hasCardio"))) if track.get("hasCardio") is not None else None,
                             synced_at, self._json(track)),
                        )
                        tracks_count += 1
                    if replace_kpis:
                        connection.execute(
                            "DELETE FROM gpexe_athlete_session_kpis WHERE provider_athlete_session_id=?", (session_id,),
                        )
                        provider_kpis = row.get("provider_kpis")
                        if isinstance(provider_kpis, list):
                            kpi_groups = ((None, provider_kpis),)
                        else:
                            kpi_groups = tuple(
                                (source, row.get(key) or [])
                                for source, key in (("identifierKpi", "identifier_kpi"), ("kpi", "kpi"))
                            )
                        for default_source, kpis in kpi_groups:
                            for position, kpi in enumerate(kpis):
                                source = str(kpi.get("source") or default_source or "provider")
                                connection.execute(
                                    """INSERT INTO gpexe_athlete_session_kpis(
                                    provider_athlete_session_id, source, position, name, value,
                                    kpi_group, uom, unit, raw_json) VALUES(?,?,?,?,?,?,?,?,?)""",
                                    (session_id, source, position, str(kpi.get("name") or ""),
                                     str(kpi.get("value")) if kpi.get("value") is not None else None,
                                     kpi.get("group"), kpi.get("uom"), kpi.get("unit"), self._json(kpi)),
                                )
                                kpis_count += 1
                connection.commit()
                return len(sessions), tracks_count, kpis_count
            except Exception:
                connection.rollback()
                raise

    def upsert_graphql_team_session_bundle(
        self, team_session: Mapping[str, Any], athletes: list[Mapping[str, Any]],
        sessions: list[Mapping[str, Any]], *, replace_kpis: bool = True,
        season: str | None = None,
    ) -> tuple[int, int, int]:
        """Alias compatibile per il percorso GraphQL esistente."""
        return self.upsert_team_session_bundle(
            team_session, athletes, sessions,
            replace_kpis=replace_kpis, season=season,
        )

    def athlete_session_detail_count(self) -> int:
        if not self.path.is_file():
            return 0
        self.initialize()
        with self.connect() as connection:
            return int(connection.execute(
                "SELECT COUNT(*) FROM gpexe_athlete_session_details"
            ).fetchone()[0])

    def last_athlete_session_detail_sync(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM gpexe_sync_runs WHERE resource_group='athlete_session_details'
                AND status='success' ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            return dict(row) if row is not None else None

    def team_session_detail_count(self) -> int:
        if not self.path.is_file():
            return 0
        self.initialize()
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM gpexe_team_session_details").fetchone()[0])

    def last_team_session_detail_sync(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM gpexe_sync_runs WHERE resource_group='team_session_details'
                AND status='success' ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            return dict(row) if row is not None else None

    def latest_team_session_updated_at(self) -> str | None:
        if not self.path.is_file():
            return None
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT MAX(provider_updated_at) FROM gpexe_team_sessions"
            ).fetchone()
            return str(row[0]) if row and row[0] else None

    def team_session_count(self) -> int:
        if not self.path.is_file():
            return 0
        self.initialize()
        with self.connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM gpexe_team_sessions").fetchone()[0])

    def last_team_session_sync(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                """SELECT * FROM gpexe_sync_runs WHERE resource_group='team_sessions'
                AND status='success' ORDER BY id DESC LIMIT 1"""
            ).fetchone()
            return dict(row) if row is not None else None

    def counts(self) -> dict[str, int]:
        if not self.path.is_file():
            return {"teams": 0, "categories": 0, "tags": 0, "athletes": 0}
        self.initialize()
        with self.connect() as connection:
            return {
                "teams": int(connection.execute("SELECT COUNT(*) FROM gpexe_teams").fetchone()[0]),
                "categories": int(connection.execute("SELECT COUNT(*) FROM gpexe_categories").fetchone()[0]),
                "tags": int(connection.execute("SELECT COUNT(*) FROM gpexe_tags").fetchone()[0]),
                "athletes": int(connection.execute("SELECT COUNT(*) FROM gpexe_athletes").fetchone()[0]),
            }

    def last_successful_sync(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        self.initialize()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM gpexe_sync_runs
                WHERE resource_group='reference' AND status='success'
                ORDER BY id DESC LIMIT 1
                """
            ).fetchone()
            return dict(row) if row is not None else None
