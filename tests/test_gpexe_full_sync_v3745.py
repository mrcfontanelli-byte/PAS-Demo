from pathlib import Path

from pas_connect.database import PASConnectDatabase
from pas_connect.sync import run_full_sync


class FakeClient:
    def request(self, endpoint, *, path_values=None, query=None, body=None, headers=None):
        path = endpoint.format(**(path_values or {}))
        if path == "/rest/v2/team/":
            return [{"id": 1, "name": "PAS Team"}]
        if path == "/rest/v2/session/category/":
            return [{"id": 10, "name": "FULL TRAINING", "team": 1}]
        if path == "/rest/v2/session/tags/":
            return [{"id": 20, "name": "MD-3", "team": 1}]
        if path == "/rest/v2/athlete/":
            return [{"id": 30, "name": "PLAYER ONE", "first_name": "ONE", "last_name": "PLAYER"}]
        if path == "/rest/v2/session/team/":
            return [{"id": 40, "team": 1, "category": 10, "name": "SESSION", "updated_on": "2026-08-03T10:00:00Z"}]
        if path == "/rest/v2/session/team/40/":
            return {
                "general": {"id": 40, "team": 1},
                "header": {"category": "FULL TRAINING", "athletes": 1},
                "table_data": {
                    "headers": [{"label": "athlete"}, {"label": "distance", "unit": "m"}],
                    "athlete_sessions": [{"id": 50, "athlete": {"first_name": "ONE", "last_name": "PLAYER"}, "values": ["PLAYER ONE", "1000"]}],
                },
            }
        if path == "/rest/v2/session/athlete/50/":
            return {"id": 50, "athlete_id": 30, "distance": 1000, "is_stats_valid": True}
        raise AssertionError(path)


def test_complete_pipeline_persists_all_current_resources(tmp_path: Path):
    database = PASConnectDatabase.default(tmp_path)
    events = []
    result = run_full_sync(FakeClient(), database, progress=events.append)
    assert result["status"] == "success"
    assert database.counts()["athletes"] == 1
    assert database.team_session_count() == 1
    assert database.team_session_detail_count() == 1
    assert database.athlete_session_detail_count() == 1
    assert events[-1].step == "Tracks"
    assert events[-1].status == "warning"
