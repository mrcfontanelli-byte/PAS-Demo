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


SCHEMA_VERSION = 6


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
                """
            )
            athlete_columns = {row[1] for row in connection.execute("PRAGMA table_info(gpexe_athletes)")}
            for name, definition in {
                "team_id": "INTEGER", "jersey_number": "TEXT",
                "is_active": "INTEGER", "has_tracks": "INTEGER",
            }.items():
                if name not in athlete_columns:
                    connection.execute(f"ALTER TABLE gpexe_athletes ADD COLUMN {name} {definition}")
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

    def upsert_graphql_athletes(self, athletes: list[Mapping[str, Any]]) -> tuple[int, int]:
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
                    photo_url=excluded.photo_url, team_id=excluded.team_id,
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
                inserted += int(not exists)
                updated += int(exists)
            connection.commit()
        return inserted, updated

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
