import hashlib
import sqlite3
from pathlib import Path

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.metric_usage import MODULES, USAGE_STATUSES, USAGE_TYPES, scan_metric_usage, usage_record


def _catalog(database):
    for metric, provider in (
        ("Distance", "GPExe"),
        ("MPE Rec Avg Time", "GPExe"),
        ("High Intensity Training", "Firstbeat"),
        ("Anaerobic Threshold Zone", "Firstbeat"),
        ("Unused Metric", "GPExe"),
    ):
        database.upsert_metric_catalog_entry({
            "canonical_metric": metric, "display_name": metric, "provider": provider,
            "acquisition_mode": "GRAPHQL" if provider == "GPExe" else "MANUAL",
            "provider_metric_name": "" if provider == "Firstbeat" else metric.lower(),
            "category": "GPS", "metric_type": "direct", "value_type": "numeric",
        })


def test_schema_9_adds_non_destructive_usage_table(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_teams(provider_team_id, team_name, synced_at, raw_json)
            VALUES(1,'TEAM','now','{}')"""
        )
        connection.commit()
    database.initialize()
    with database.connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(pas_metric_usage)")}
        version = connection.execute(
            "SELECT value FROM pas_connect_meta WHERE key='schema_version'"
        ).fetchone()[0]
        assert connection.execute("SELECT team_name FROM gpexe_teams").fetchone()[0] == "TEAM"
    assert SCHEMA_VERSION == 12
    assert version == "12"
    assert columns == {
        "id", "canonical_metric", "module", "view_name", "usage_type", "status", "enabled",
        "required", "display_order", "notes", "created_at", "updated_at",
    }


def test_usage_upsert_flags_order_and_multiple_modules_views(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    first_id, inserted = database.upsert_metric_usage({
        "canonical_metric": "Distance", "module": "Dashboard",
        "view_name": "Panoramica del giorno", "usage_type": "display",
        "enabled": True, "required": False, "display_order": 2,
    })
    same_id, inserted_again = database.upsert_metric_usage({
        "canonical_metric": "Distance", "module": "Dashboard",
        "view_name": "Panoramica del giorno", "usage_type": "display",
        "enabled": False, "required": True, "display_order": 7,
    })
    database.upsert_metric_usage({
        "canonical_metric": "Distance", "module": "Bridge Validation",
        "view_name": "Bridge Validation", "usage_type": "comparison",
    })
    database.upsert_metric_usage({
        "canonical_metric": "Distance", "module": "PAS Connect",
        "view_name": "Distance Pilot", "usage_type": "display",
    })
    rows = database.list_metric_usage()
    assert inserted and not inserted_again and first_id == same_id
    assert len(rows) == 3
    dashboard = next(row for row in rows if row["module"] == "Dashboard")
    assert not dashboard["enabled"] and dashboard["required"] and dashboard["display_order"] == 7
    assert dashboard["status"] == "MANUAL"


def test_orphans_and_catalog_metrics_without_usage_are_only_reported(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    _catalog(database)
    database.upsert_metric_usage({
        "canonical_metric": "Orphan", "module": "Planner", "view_name": "Planner",
        "usage_type": "internal",
    })
    assert [row["canonical_metric"] for row in database.orphan_metric_usage()] == ["Orphan"]
    missing = database.catalog_metrics_without_usage()
    assert "Unused Metric" in missing and "Distance" in missing
    assert len(database.list_metric_usage()) == 1


def test_preview_is_read_only_and_classifies_required_initial_usage(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    _catalog(database)
    before = hashlib.sha256(database.path.read_bytes()).hexdigest()
    proposals = scan_metric_usage(Path(__file__).resolve().parents[1], database.list_metric_catalog())
    after = hashlib.sha256(database.path.read_bytes()).hexdigest()
    assert before == after
    assert database.list_metric_usage() == []
    keys = {(p["canonical_metric"], p["module"], p["view_name"], p["usage_type"]) for p in proposals}
    assert ("Distance", "Dashboard", "Panoramica del giorno", "display") in keys
    assert ("Distance", "Bridge Validation", "Bridge Validation", "comparison") in keys
    assert ("Distance", "PAS Connect", "Distance Pilot", "display") in keys
    assert ("MPE Rec Avg Time", "Drills", "Drills Analysis", "display") in keys
    assert ("MPE Rec Avg Time", "Match", "Performance Model", "calculation") in keys
    assert ("MPE Rec Avg Time", "Match Report", "Match Report", "report") in keys
    assert not any(p["canonical_metric"] == "MPE Rec Avg Time" and p["module"] == "Dashboard" for p in proposals)
    assert {p["confidence"] for p in proposals} <= {"verificata", "probabile", "ambigua"}
    assert {p["status"] for p in proposals} <= {"VERIFIED", "PROBABLE", "AMBIGUOUS"}
    assert all(p["source_file"] and p["source_line"] for p in proposals)
    assert any(p["canonical_metric"] == "Distance" and p["module"] == "Session Report" for p in proposals)


def test_firstbeat_usage_is_provider_independent_and_has_no_invented_gpexe_mapping(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    _catalog(database)
    proposals = scan_metric_usage(Path(__file__).resolve().parents[1], database.list_metric_catalog())
    firstbeat = [p for p in proposals if p["canonical_metric"] in {
        "High Intensity Training", "Anaerobic Threshold Zone",
    }]
    assert firstbeat
    assert all("provider" not in proposal for proposal in firstbeat)
    assert all(proposal["module"] in {"Dashboard", "Session Report"} for proposal in firstbeat)
    assert all(proposal["status"] == "VERIFIED" for proposal in firstbeat)


def test_confirmation_imports_preview_without_duplicates(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    _catalog(database)
    proposals = scan_metric_usage(Path(__file__).resolve().parents[1], database.list_metric_catalog())
    records = [usage_record(item) for item in proposals]
    assert database.import_metric_usage_proposals(records) == (len(records), 0)
    assert database.import_metric_usage_proposals(records) == (0, len(records))
    assert len(database.list_metric_usage()) == len(records)
    distance = [row for row in database.list_metric_usage() if row["canonical_metric"] == "Distance"]
    assert distance and all(row["status"] == "VERIFIED" for row in distance)
    mpe_drills = [
        row for row in database.list_metric_usage()
        if row["canonical_metric"] == "MPE Rec Avg Time" and row["module"] == "Drills"
    ]
    assert mpe_drills and all(row["status"] == "AMBIGUOUS" for row in mpe_drills)


def test_supported_modules_types_and_pas_connect_ui_are_complete():
    assert set(MODULES) == {
        "Dashboard", "Drills", "Match", "Match Report", "Session Report",
        "Bridge Validation", "PAS Connect", "Player Profile", "Forecast", "Planner",
    }
    assert set(USAGE_TYPES) == {
        "display", "filter", "calculation", "comparison", "export", "report", "internal",
    }
    assert set(USAGE_STATUSES) == {"VERIFIED", "PROBABLE", "AMBIGUOUS", "MANUAL"}
    app = open("app.py", encoding="utf-8").read()
    ui = open("pas_connect/usage_ui.py", encoding="utf-8").read()
    assert "render_metric_usage_section(" in app
    assert "pas_connect_database, base_dir, embedded=True" in app
    assert "Utilizzo metriche PAS" in ui
    assert "Conferma e salva associazioni proposte" in ui
    assert "Metriche senza utilizzo registrato" in ui
    assert 'selectbox("Status"' in ui
    assert "Stato associazioni" in ui


def test_manual_save_status_and_invalid_status_are_enforced(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    usage_id, inserted = database.upsert_metric_usage({
        "canonical_metric": "Distance", "module": "Dashboard",
        "view_name": "Manual View", "usage_type": "display", "status": "MANUAL",
    })
    assert inserted and usage_id
    assert database.list_metric_usage()[0]["status"] == "MANUAL"
    import pytest
    with pytest.raises(ValueError, match="Status utilizzo non supportato"):
        database.upsert_metric_usage({
            "canonical_metric": "Distance", "module": "Dashboard",
            "view_name": "Bad", "usage_type": "display", "status": "INVALID",
        })


def test_migration_adds_manual_status_to_existing_usage_rows(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.executescript(
            """CREATE TABLE pas_connect_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            INSERT INTO pas_connect_meta VALUES('schema_version','9');
            CREATE TABLE pas_metric_usage(
                id INTEGER PRIMARY KEY AUTOINCREMENT, canonical_metric TEXT NOT NULL,
                module TEXT NOT NULL, view_name TEXT NOT NULL, usage_type TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1, required INTEGER NOT NULL DEFAULT 0,
                display_order INTEGER NOT NULL DEFAULT 0, notes TEXT,
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(canonical_metric,module,view_name,usage_type));
            INSERT INTO pas_metric_usage(
                canonical_metric,module,view_name,usage_type,created_at,updated_at
            ) VALUES('Distance','Dashboard','Legacy','display','old','old');"""
        )
    database = PASConnectDatabase(path)
    database.initialize()
    assert database.list_metric_usage()[0]["status"] == "MANUAL"
