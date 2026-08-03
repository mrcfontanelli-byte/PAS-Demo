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


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class ReferenceImportResult:
    database_path: Path
    synced_at: str
    counts: dict[str, int]
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
                """
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
