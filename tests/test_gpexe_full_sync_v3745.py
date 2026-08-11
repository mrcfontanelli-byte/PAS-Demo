from pathlib import Path

from pas_connect.database import PASConnectDatabase
from pas_connect.sync import SyncRequest, run_full_sync


class FakeServices:
    def team_sessions(self, **kwargs):
        return [{"id": 40, "team": 1, "name": "SESSION", "startTimestamp": "2026-08-03"}]

    def team_session_athlete_sessions(self, *, team_session_id, trace=None, **kwargs):
        assert isinstance(team_session_id, int)
        if trace:
            trace("C-03", {"variables": {"id": team_session_id}})
            trace("C-04", {"operationName": "TeamSessionAthletesession", "variables": {"id": team_session_id}})
            trace("C-05", {"status": "SUCCESS"})
        return {"athleteSessions": [{
            "id": 50,
            "athlete": {"id": 30, "firstName": "ONE", "lastName": "PLAYER"},
            "track": {"id": "60", "athlete": {"id": 30}},
            "kpi": [{"name": "total_distance", "value": 1000, "unit": "m"}],
        }]}


def test_complete_pipeline_persists_all_current_resources(tmp_path: Path):
    database = PASConnectDatabase.default(tmp_path)
    events = []
    result = run_full_sync(
        FakeServices(), database, progress=events.append,
        request=SyncRequest(1, "2026/2027", date_from="2026-08-03", date_to="2026-08-03"),
    )
    assert result.status == "success"
    assert database.counts()["athletes"] == 1
    assert database.team_session_count() == 1
    assert database.athlete_session_detail_count() == 1
    assert events[-1].step == "C-05"
    assert all("/rest/" not in event.message for event in events)
