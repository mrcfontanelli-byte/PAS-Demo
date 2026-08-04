from __future__ import annotations

import json
import socket

import pytest

from pas_connect import GPExeConfig, GPExeGraphQLClient, GPExeServices, PASConnectDatabase
from pas_connect.exceptions import APIRequestError
from pas_connect.mapper import map_team_session


def _client(payload=None, *, error=None):
    def transport(request, timeout, verify_tls):
        if error:
            raise error
        body = json.loads(request.data)
        responses = payload if callable(payload) else payload
        return 200, json.dumps(responses(body)).encode() if callable(responses) else json.dumps(responses).encode()

    config = GPExeConfig(base_url="https://example.test/ui/v2/", token="token", max_retries=0)
    return GPExeGraphQLClient(config, transport=transport, sleep=lambda _: None)


def test_team_selector_uses_verified_operation_and_variables():
    captured = {}

    def response(body):
        captured.update(body)
        return {"data": {"teams": [{"id": "7", "name": "First", "season": "2026"}]}}

    teams = GPExeServices(_client(response)).teams()
    assert teams == [{"id": "7", "name": "First", "season": "2026"}]
    assert captured["operationName"] == "TeamSelector"
    assert captured["variables"] == {"sort": "club__name,name,season", "active": True}
    assert "limitedClub { name }" in captured["query"]


def test_get_team_sessions_uses_verified_operation_and_variables():
    captured = {}

    def response(body):
        captured.update(body)
        return {"data": {"teamSessions": {"results": [{"id": "11", "category": "Training"}]}}}

    sessions = GPExeServices(_client(response)).team_sessions(
        team_id="7", start_date="2026-07-29", end_date="2026-08-04"
    )
    assert sessions[0]["id"] == "11"
    assert captured["operationName"] == "GetTeamSessions"
    assert captured["variables"] == {
        "teamId": "7", "startDate": "2026-07-29", "endDate": "2026-08-04"
    }
    for field in ("athleteCount", "matchCycle", "drillEnabled", "drillCount"):
        assert field in captured["query"]


def test_team_selector_collects_offset_pages_without_duplicates():
    calls = []

    def response(body):
        calls.append(body["variables"])
        offset = body["variables"].get("offset", 0)
        rows = ([{"id": "1", "name": "A"}, {"id": "2", "name": "B"}]
                if offset == 0 else [{"id": "2", "name": "B"}, {"id": "3", "name": "C"}])
        return {"data": {"teams": {"count": 4, "offset": offset, "pageSize": 2, "results": rows}}}

    teams = GPExeServices(_client(response)).teams()
    assert [team["id"] for team in teams] == ["1", "2", "3"]
    assert calls == [
        {"sort": "club__name,name,season", "active": True},
        {"sort": "club__name,name,season", "active": True, "offset": 2, "pageSize": 2},
    ]


def test_get_team_sessions_collects_cursor_pages_and_stops_at_last_page():
    calls = []

    def response(body):
        calls.append(body["variables"])
        after = body["variables"].get("after")
        if after is None:
            page = {
                "edges": [{"node": {"id": "10"}}, {"node": {"id": "11"}}],
                "pageInfo": {"hasNextPage": True, "endCursor": "cursor-1"},
            }
        else:
            page = {
                "edges": [{"node": {"id": "11"}}, {"node": {"id": "12"}}],
                "pageInfo": {"hasNextPage": False, "endCursor": "cursor-2"},
            }
        return {"data": {"teamSessions": page}}

    sessions = GPExeServices(_client(response)).team_sessions(
        team_id="7", start_date="2026-07-29", end_date="2026-08-04"
    )
    assert [session["id"] for session in sessions] == ["10", "11", "12"]
    assert len(calls) == 2
    assert calls[1]["after"] == "cursor-1"


@pytest.mark.parametrize("data", [{"teams": []}, {"teams": None}])
def test_empty_team_selector_response(data):
    assert GPExeServices(_client({"data": data})).teams() == []


def test_team_without_team_sessions_returns_empty_list():
    service = GPExeServices(_client({"data": {"teamSessions": []}}))
    assert service.team_sessions(team_id="7", start_date="2026-07-29", end_date="2026-08-04") == []


def test_graphql_errors_are_reported():
    service = GPExeServices(_client({"errors": [{"message": "denied"}], "data": {}}))
    with pytest.raises(APIRequestError, match="Errore GraphQL"):
        service.teams()


def test_timeout_is_reported():
    with pytest.raises(APIRequestError, match="Timeout"):
        GPExeServices(_client(error=socket.timeout())).teams()


def test_non_json_response_is_reported():
    def transport(request, timeout, verify_tls):
        return 200, b"<html>bad gateway</html>", {"Content-Type": "text/html"}

    client = GPExeGraphQLClient(
        GPExeConfig(base_url="https://example.test/ui/v2/", token="token", max_retries=0),
        transport=transport,
    )
    with pytest.raises(APIRequestError, match="non JSON"):
        GPExeServices(client).teams()


def test_selected_team_sessions_persist_in_pas_connect_database(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    raw = {
        "id": "11", "category": "Training", "startTimestamp": "2026-08-03T10:00:00Z",
        "duration": 5400, "athleteCount": 22, "matchCycle": "MD-4", "state": "READY",
        "drill": False, "drillEnabled": True, "team": "7",
    }
    result = database.upsert_team_sessions({"sessions": [map_team_session(raw)]})
    assert result.received == 1
    assert result.inserted == 1
    assert database.team_session_count() == 1


def test_unimplemented_controls_keep_release_message():
    service = GPExeServices(_client({"data": {}}))
    with pytest.raises(APIRequestError, match="Funzione disponibile in una release successiva"):
        service.athletes()
    with pytest.raises(APIRequestError, match="Funzione disponibile in una release successiva"):
        service.tracks()
