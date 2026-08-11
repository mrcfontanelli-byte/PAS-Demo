from __future__ import annotations

from pathlib import Path
import hashlib

import pytest

from pas_connect.database import PASConnectDatabase
from pas_connect.exceptions import APIRequestError
from pas_connect.sync import (
    SyncRequest,
    retry_sync_errors,
    retry_sync_session,
    run_graphql_sync,
)


def _session(session_id: int, team_id: int = 543) -> dict:
    return {
        "id": session_id, "team": team_id, "name": "FULL TRAINING",
        "startTimestamp": "2026-07-31T10:00:00", "state": "R",
    }


def _bundle(session_id: int, athlete_id: int = 9001) -> dict:
    return {
        "id": session_id,
        "athleteSessions": [{
            "id": session_id * 10 + 1,
            "athlete": {"id": athlete_id, "firstName": "Ada", "lastName": "Rossi"},
            "track": {"id": f"track-{session_id}", "athlete": {"id": athlete_id}},
            "identifierKpi": [{"name": "athlete", "value": athlete_id}],
            "kpi": [{"name": "total_distance", "value": 4321, "unit": "m"}],
            "totalTime": {"value": "60:00", "unit": "min"},
        }],
    }


class FakeServices:
    def __init__(self, sessions, bundles, fallback_bundles=None):
        self.sessions = sessions
        self.bundles = bundles
        self.fallback_bundles = fallback_bundles or {}
        self.calls = []

    def team_sessions(self, **kwargs):
        self.calls.append(("GetTeamSessions", kwargs))
        return list(self.sessions)

    def team_session_athlete_sessions(self, *, team_session_id, trace=None, **kwargs):
        self.calls.append(("TeamSessionAthletesession", team_session_id))
        variables = {"id": int(team_session_id), "templateId": None, "drill": None}
        if trace:
            trace("C-03", {"operationName": "TeamSessionAthletesession", "variables": variables})
            trace("C-04", {"operationName": "TeamSessionAthletesession", "variables": variables})
        value = self.bundles[int(team_session_id)]
        if isinstance(value, Exception):
            if trace:
                trace("C-05", {"status": "ERROR", "errorType": type(value).__name__})
            raise value
        if trace:
            trace("C-05", {"status": "SUCCESS", "hasDataRes": True})
        return value

    def team_session_athlete_sessions_without_kpis(self, *, team_session_id, trace=None, **kwargs):
        self.calls.append(("TeamSessionAthletesessionNoKpi", team_session_id))
        if trace:
            trace("C-04-KPI-FALLBACK", {
                "operationName": "TeamSessionAthletesessionNoKpi",
                "variables": {"id": int(team_session_id), "templateId": None, "drill": None},
            })
        value = self.fallback_bundles[int(team_session_id)]
        if isinstance(value, Exception):
            raise value
        if trace:
            trace("C-05-KPI-FALLBACK", {"status": "SUCCESS", "hasDataRes": True})
        return value


@pytest.mark.parametrize("team_id", [0, -1])
def test_sync_request_rejects_invalid_team(team_id):
    with pytest.raises(ValueError):
        SyncRequest(team_id, "2026/2027", date_from="2026-07-01", date_to="2026-07-31").validate()


def test_graphql_orchestrator_traces_complete_chain_and_skips_second_import(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    services = FakeServices([_session(143095)], {143095: _bundle(143095)})
    request = SyncRequest(
        543, "2026/2027", date_from="2026-07-31", date_to="2026-07-31",
        selected_session_ids=(143095,),
    )

    first = run_graphql_sync(services, database, request)
    assert first.status == "success"
    assert first.sessions[0].status == "SUCCESS"
    assert first.sessions[0].readiness == "READY"
    assert first.sessions[0].athlete_sessions_count == 1
    assert first.sessions[0].tracks_count == 1
    assert first.sessions[0].kpis_count == 2
    assert [item["checkpoint"] for item in first.sessions[0].diagnostics] == [
        "C-01", "C-02", "C-03", "C-04", "C-05",
    ]
    c04 = first.sessions[0].diagnostics[3]
    assert c04["variables"]["id"] == 143095
    assert isinstance(c04["variables"]["id"], int)
    assert "" not in c04["variables"].values()

    def row_counts():
        with database.connect() as connection:
            return tuple(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in (
                "gpexe_team_sessions", "gpexe_athlete_session_details", "gpexe_tracks",
                "gpexe_athlete_session_kpis",
            ))

    before = row_counts()
    second = run_graphql_sync(services, database, request)
    after = row_counts()
    assert second.sessions[0].status == "SKIPPED"
    assert after == before


def test_partial_failed_and_retry_contracts(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    services = FakeServices(
        [_session(1), _session(2)],
        {1: {"id": 1, "athleteSessions": []}, 2: RuntimeError("Authorization: JWT-secret Cookie=session-secret")},
    )
    request = SyncRequest(543, "2026/2027", date_from="2026-07-01", date_to="2026-07-31")
    result = run_graphql_sync(services, database, request)
    assert [item.status for item in result.sessions] == ["PARTIAL", "FAILED"]
    assert "JWT-secret" not in result.sessions[1].error_message
    assert "session-secret" not in result.sessions[1].error_message
    assert database.retryable_session_ids(result.sync_run_id) == [2, 1]

    services.bundles[1] = _bundle(1)
    one = retry_sync_session(services, database, request, 1, run_id=result.sync_run_id)
    assert [item.status for item in one.sessions] == ["SUCCESS"]
    services.bundles[2] = _bundle(2)
    all_errors = retry_sync_errors(services, database, request, run_id=result.sync_run_id)
    assert {item.provider_session_id for item in all_errors.sessions} == {1, 2}
    assert all(item.status == "SUCCESS" for item in all_errors.sessions)


def _provider_error(field: str, count: int = 27) -> APIRequestError:
    return APIRequestError(
        "Errore GraphQL GPExe: Field 'id' expected a number but got ''.",
        graphql_errors=tuple({
            "message": "Field 'id' expected a number but got ''.",
            "path": ["res", "athleteSessions", index, field],
        } for index in range(count)),
    )


def _structural_bundle(session_id: int, count: int = 27, athlete_base: int = 9000) -> dict:
    return {
        "id": session_id,
        "athleteSessions": [{
            "id": session_id * 100 + index,
            "athlete": {
                "id": athlete_base + index, "firstName": f"Atleta {index}", "lastName": "Test",
            },
            "track": {
                "id": f"track-{session_id}-{index}",
                "athlete": {"id": athlete_base + index},
            },
            "state": "R", "isStatsValid": True, "starter": False,
            "totalTime": {"value": 60, "unit": "min"},
        } for index in range(count)],
    }


def test_kpi_only_errors_persist_partial_bundle_idempotently_and_isolate_team(tmp_path: Path):
    excel = Path(__file__).parents[1] / "Database Hellas 25-26.xlsx"
    excel_before = (excel.stat().st_size, hashlib.sha256(excel.read_bytes()).hexdigest())
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")

    team_469_services = FakeServices([_session(469001, 469)], {469001: _bundle(469001, 46901)})
    team_469_request = SyncRequest(
        469, "2025/2026", date_from="2026-07-01", date_to="2026-07-31",
        selected_session_ids=(469001,),
    )
    assert run_graphql_sync(team_469_services, database, team_469_request).sessions[0].status == "SUCCESS"

    def team_469_snapshot():
        with database.connect() as connection:
            return {
                "sessions": tuple(connection.execute(
                    "SELECT * FROM gpexe_team_sessions WHERE team_id=469 ORDER BY provider_session_id"
                )),
                "memberships": tuple(connection.execute(
                    """SELECT * FROM gpexe_athlete_team_memberships
                    WHERE team_id=469 ORDER BY provider_player_id,season"""
                )),
                "details": tuple(connection.execute(
                    "SELECT * FROM gpexe_athlete_session_details "
                    "WHERE provider_session_id=469001 ORDER BY provider_athlete_session_id"
                )),
                "tracks": tuple(connection.execute(
                    """SELECT t.* FROM gpexe_tracks t JOIN gpexe_athlete_session_details d
                       ON d.track_id=t.provider_track_id WHERE d.provider_session_id=469001
                       ORDER BY t.provider_track_id"""
                )),
                "kpis": tuple(connection.execute(
                    """SELECT k.* FROM gpexe_athlete_session_kpis k
                       JOIN gpexe_athlete_session_details d
                         ON d.provider_athlete_session_id=k.provider_athlete_session_id
                       WHERE d.provider_session_id=469001
                       ORDER BY k.provider_athlete_session_id,k.source,k.position"""
                )),
            }

    team_469_before = team_469_snapshot()

    errors = tuple(
        list(_provider_error("identifierKpi").graphql_errors)
        + list(_provider_error("kpi").graphql_errors)
    )
    services = FakeServices(
        [_session(143261)],
        {143261: APIRequestError("provider KPI error", graphql_errors=errors)},
        {143261: _structural_bundle(143261)},
    )
    request = SyncRequest(
        543, "2026/2027", date_from="2026-07-31", date_to="2026-07-31",
        selected_session_ids=(143261,),
    )
    first = run_graphql_sync(services, database, request)
    session = first.sessions[0]
    assert first.status == "partial"
    assert (session.status, session.readiness) == ("PARTIAL", "INCOMPLETE")
    assert (session.athlete_sessions_count, session.tracks_count, session.kpis_count) == (27, 27, 0)
    assert session.error_message.startswith("provider KPI error:")
    diagnostic = next(item for item in session.diagnostics if item["checkpoint"] == "KPI-PROVIDER-ERROR")
    assert len(diagnostic["graphqlErrors"]) == 54
    assert {tuple(item["path"][-1:]) for item in diagnostic["graphqlErrors"]} == {
        ("identifierKpi",), ("kpi",),
    }

    def counts():
        with database.connect() as connection:
            return tuple(connection.execute(
                f"SELECT COUNT(*) FROM {table}"
            ).fetchone()[0] for table in (
                "gpexe_team_sessions", "gpexe_athlete_session_details",
                "gpexe_tracks", "gpexe_athlete_session_kpis",
            ))

    before_second = counts()
    second = run_graphql_sync(services, database, request)
    assert second.sessions[0].status == "PARTIAL"
    assert counts() == before_second
    assert services.calls.count(("TeamSessionAthletesessionNoKpi", 143261)) == 2
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_athlete_session_details WHERE provider_session_id=143261"
        ).fetchone()[0] == 27
        assert connection.execute(
            """SELECT COUNT(*) FROM gpexe_tracks t JOIN gpexe_athlete_session_details d
               ON d.track_id=t.provider_track_id WHERE d.provider_session_id=143261"""
        ).fetchone()[0] == 27
        assert connection.execute(
            """SELECT COUNT(*) FROM gpexe_athlete_session_kpis k
               JOIN gpexe_athlete_session_details d
               ON d.provider_athlete_session_id=k.provider_athlete_session_id
               WHERE d.provider_session_id=143261"""
        ).fetchone()[0] == 0
    assert team_469_snapshot() == team_469_before
    assert (excel.stat().st_size, hashlib.sha256(excel.read_bytes()).hexdigest()) == excel_before


def test_non_kpi_graphql_error_stays_failed_and_does_not_publish(tmp_path: Path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    mixed_errors = _provider_error("kpi", 1).graphql_errors + ({
        "message": "track failed", "path": ["res", "athleteSessions", 0, "track"],
    },)
    services = FakeServices(
        [_session(143261)],
        {143261: APIRequestError("mixed provider error", graphql_errors=mixed_errors)},
        {143261: _structural_bundle(143261)},
    )
    result = run_graphql_sync(
        services, database,
        SyncRequest(543, "2026/2027", date_from="2026-07-31", date_to="2026-07-31"),
    )
    assert (result.sessions[0].status, result.sessions[0].readiness) == ("FAILED", "INCOMPLETE")
    assert not any(call[0] == "TeamSessionAthletesessionNoKpi" for call in services.calls)
    with database.connect() as connection:
        for table in ("gpexe_team_sessions", "gpexe_athlete_session_details", "gpexe_tracks"):
            assert connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
