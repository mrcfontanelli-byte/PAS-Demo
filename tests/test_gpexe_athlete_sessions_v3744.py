from pathlib import Path
import json
import sqlite3

from pas_connect.database import PASConnectDatabase
from pas_connect.mapper import map_athlete_session_detail
from pas_connect.sync import sync_athlete_session_details


class FakeClient:
    def request(self, endpoint, *, path_values=None, **kwargs):
        aid = int(path_values["id"])
        return {
            "id": aid,
            "athlete": {"id": 77, "first_name": "TEST", "last_name": "PLAYER"},
            "drill": 32767,
            "track": 456,
            "duration": "79:17",
            "distance": 5577.1,
            "relative_speed_events": 13,
            "recovery_average_time": 18.7,
            "speed_zones": [{"zone_number": 1, "distance": 123.4}],
            "is_stats_valid": True,
            "starter": False,
            "updated_on": "2026-08-03T10:00:00Z",
        }


def _seed(db: PASConnectDatabase):
    db.upsert_team_sessions({"synced_at": "2026-08-03T12:00:00+00:00", "sessions": [{
        "provider_session_id": 101, "team_id": 1, "category_id": 1, "session_name": "FULL TRAINING",
        "notes": None, "start_timestamp": "2026-08-01T09:00:00Z", "end_timestamp": None,
        "total_time": "1:19:17", "is_stats_valid": True, "drill_enabled": False, "state": "completed",
        "submitted_by": None, "created_at": None, "updated_at": "2026-08-01T12:00:00Z", "tags": []
    }]})
    db.upsert_team_session_details({
        "synced_at": "2026-08-03T12:05:00+00:00", "errors": [], "details": [{
            "provider_session_id": 101, "provider_general_id": 101, "team_id": 1, "nature": "S",
            "start_timestamp": "2026-08-01T09:00:00Z", "category_id": 1, "category_name": "FULL TRAINING",
            "athlete_count": 1, "total_time": "1:19:17", "notes": None, "timing": {}, "headers": [],
            "athlete_rows": [{"provider_athlete_session_id": 9001, "athlete": {"first_name": "TEST", "last_name": "PLAYER", "role": "CM"}, "metrics": {}, "state": "ready"}],
            "raw": {}
        }]
    })


def test_mapper_keeps_scalar_metrics_and_zones():
    row = map_athlete_session_detail(FakeClient().request(None, path_values={"id": 9001}), provider_athlete_session_id=9001, provider_session_id=101)
    assert row["provider_session_id"] == 101
    assert row["provider_player_id"] == 77
    assert row["metrics"]["distance"] == 5577.1
    assert row["metrics"]["recovery_average_time"] == 18.7
    assert row["zones"]["speed_zones"][0]["zone_number"] == 1


def test_sync_and_database_persist_athlete_sessions(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    _seed(db)
    assert db.athlete_session_refs_for_detail_sync() == [(9001, 101)]
    payload = sync_athlete_session_details(FakeClient(), [(9001, 101)])
    result = db.upsert_athlete_session_details(payload)
    assert result.received == 1 and result.inserted == 1 and result.failed == 0
    assert db.athlete_session_detail_count() == 1
    assert db.athlete_session_refs_for_detail_sync() == []
    with sqlite3.connect(db.path) as connection:
        metrics_json, zones_json = connection.execute(
            "SELECT metrics_json, zones_json FROM gpexe_athlete_session_details"
        ).fetchone()
    assert json.loads(metrics_json)["distance"] == 5577.1
    assert json.loads(zones_json)["speed_zones"][0]["distance"] == 123.4


def test_app_exposes_athlete_sync_without_switching_source():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Sincronizza Athlete Sessions GPExe" in app
    assert "Excel e analisi non cambiano" in app
