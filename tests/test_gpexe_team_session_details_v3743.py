from pathlib import Path
import sqlite3

from pas_connect.database import PASConnectDatabase
from pas_connect.mapper import map_team_session_detail
from pas_connect.sync import sync_team_session_details


class FakeClient:
    def request(self, endpoint, *, path_values=None, query=None, **kwargs):
        sid = int(path_values["id"])
        return {
            "general": {"id": sid, "team": 1, "nature": "S"},
            "header": {"start_timestamp": "2026-08-01T09:00:00Z", "category": "FULL TRAINING", "athletes": 1, "total_time": "1:19:17"},
            "table_data": {
                "headers": [{"label": "athlete", "unit": None}, {"label": "distance", "unit": "m"}],
                "athlete_sessions": [{"id": 9001, "athlete": {"first_name": "TEST", "last_name": "PLAYER", "role": "CM"}, "values": ["PLAYER TEST", "5577.1"], "state": "ready"}],
            },
            "category": {"id": 1, "name": "FULL TRAINING"},
            "timing": {"updated_on": "2026-08-01T12:00:00Z"},
            "status": {"completed": True, "is_stats_valid": True},
            "counts": {"n_tracks": 1},
        }


def test_mapper_uses_dynamic_headers():
    detail = map_team_session_detail(FakeClient().request(None, path_values={"id": 101}), provider_session_id=101)
    assert detail["headers"][1]["label"] == "distance"
    assert detail["athlete_rows"][0]["metrics"]["distance"] == "5577.1"


def test_sync_and_database_persist_details(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    db.upsert_team_sessions({"synced_at": "2026-08-03T12:00:00+00:00", "sessions": [{
        "provider_session_id": 101, "team_id": 1, "category_id": 1, "session_name": "FULL TRAINING",
        "notes": None, "start_timestamp": "2026-08-01T09:00:00Z", "end_timestamp": None,
        "total_time": "1:19:17", "is_stats_valid": True, "drill_enabled": False, "state": "completed",
        "submitted_by": None, "created_at": None, "updated_at": "2026-08-01T12:00:00Z", "tags": []
    }]})
    assert db.team_session_ids_for_detail_sync() == [101]
    payload = sync_team_session_details(FakeClient(), [101])
    result = db.upsert_team_session_details(payload)
    assert result.received == 1 and result.inserted == 1
    assert result.athlete_rows == 1 and result.metric_headers == 2
    assert db.team_session_detail_count() == 1
    assert db.team_session_ids_for_detail_sync() == []
    with sqlite3.connect(db.path) as connection:
        distance = connection.execute("SELECT metrics_json FROM gpexe_session_athlete_rows").fetchone()[0]
    assert '"distance": "5577.1"' in distance


def test_app_exposes_detail_sync_without_switching_source():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Sincronizza dettagli Team Sessions GPExe" in app
    assert "Excel e analisi restano invariati" in app
