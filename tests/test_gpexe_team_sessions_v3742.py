from pathlib import Path
import sqlite3

from pas_connect.database import PASConnectDatabase
from pas_connect.mapper import map_team_session
from pas_connect.sync import sync_team_sessions


class FakeClient:
    def __init__(self):
        self.calls = []

    def request(self, endpoint, *, query=None, **kwargs):
        self.calls.append((endpoint.path, dict(query or {})))
        return [
            {
                "id": 101,
                "team": 1,
                "category": 2,
                "name": "MD-3 FULL TRAINING",
                "notes": "",
                "start_timestamp": "2026-08-01T09:00:00Z",
                "end_timestamp": "2026-08-01T10:30:00Z",
                "total_time": "1:30:00",
                "is_stats_valid": True,
                "drill_enabled": True,
                "state": "completed",
                "submitted_by": 5,
                "created_on": "2026-08-01T11:00:00Z",
                "updated_on": "2026-08-01T12:00:00Z",
                "tags": [3],
            }
        ]


def test_team_session_mapper_and_incremental_sync():
    row = map_team_session({"id": 1, "name": "MATCH", "team": 2})
    assert row["provider_session_id"] == 1
    assert row["session_name"] == "MATCH"
    client = FakeClient()
    payload = sync_team_sessions(client, updated_since="2026-07-01T00:00:00Z")
    assert payload["count"] == 1
    assert payload["sessions"][0]["provider_session_id"] == 101
    query = client.calls[0][1]
    assert query["updated_on_gte"] == "2026-07-01T00:00:00Z"


def test_team_sessions_database_upsert_and_log(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    payload = {
        "synced_at": "2026-08-03T12:00:00+00:00",
        "sessions": [{
            "provider_session_id": 101,
            "team_id": 1,
            "category_id": 2,
            "session_name": "MD-3 FULL TRAINING",
            "notes": None,
            "start_timestamp": "2026-08-01T09:00:00Z",
            "end_timestamp": "2026-08-01T10:30:00Z",
            "total_time": "1:30:00",
            "is_stats_valid": True,
            "drill_enabled": True,
            "state": "completed",
            "submitted_by": 5,
            "created_at": "2026-08-01T11:00:00Z",
            "updated_at": "2026-08-01T12:00:00Z",
            "tags": [3],
        }],
    }
    first = db.upsert_team_sessions(payload)
    assert (first.received, first.inserted, first.updated) == (1, 1, 0)
    second = db.upsert_team_sessions(payload)
    assert (second.received, second.inserted, second.updated) == (1, 0, 1)
    assert db.team_session_count() == 1
    assert db.latest_team_session_updated_at() == "2026-08-01T12:00:00Z"
    with sqlite3.connect(db.path) as connection:
        name = connection.execute(
            "SELECT session_name FROM gpexe_team_sessions WHERE provider_session_id=101"
        ).fetchone()[0]
    assert name == "MD-3 FULL TRAINING"
    assert db.last_team_session_sync()["status"] == "success"


def test_app_exposes_team_session_sync_without_switching_source():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Sincronizza Team Sessions GPExe" in app
    assert "Dashboard, report e database Excel restano invariati" in app
