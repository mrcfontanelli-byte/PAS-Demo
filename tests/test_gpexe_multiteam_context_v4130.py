from pathlib import Path

from pas_connect.database import PASConnectDatabase
from pas_connect.pas_bridge import available_contexts, available_sessions


def _ready(database, team, season, session):
    database.initialize()
    with database.connect() as connection:
        connection.execute(
            "INSERT INTO gpexe_team_sessions(provider_session_id,team_id,session_name,start_timestamp,synced_at,raw_json) VALUES(?,?,?,?,?,?)",
            (session, team, "FULL TRAINING", "2026-07-31" if team == 543 else "2025-07-30", "now", "{}"),
        )
        connection.commit()
    run = database.create_sync_run({"team_id": team, "season": season, "mode": "MANUAL", "requested_count": 1})
    database.record_session_sync_result({
        "sync_run_id": run, "provider_session_id": session, "team_id": team,
        "status": "SUCCESS", "readiness": "READY",
    })
    database.complete_sync_run(run, {"status": "success", "success_count": 1})


def test_team_season_and_calendar_are_isolated_from_excel(tmp_path: Path):
    path = tmp_path / "pas.sqlite3"
    database = PASConnectDatabase(path)
    _ready(database, 469, "2025-2026", 121188)
    _ready(database, 543, "2026/2027", 143095)
    assert available_contexts(path) == [
        {"team_id": 469, "season": "2025-2026"},
        {"team_id": 543, "season": "2026/2027"},
    ]
    team_543 = available_sessions(path, team_id=543, season="2026/2027", ready_only=True)
    assert [row["provider_session_id"] for row in team_543] == [143095]
    assert team_543[0]["start_timestamp"] == "2026-07-31"
    assert not available_sessions(path, team_id=469, season="2026/2027", ready_only=True)

