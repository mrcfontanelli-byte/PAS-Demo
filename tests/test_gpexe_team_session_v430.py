from __future__ import annotations

import json
import socket

import pytest

from pas_connect import (
    GPExeAPIDataProvider, GPExeConfig, GPExeGraphQLClient, GPExeServices,
    PASConnectDatabase, invalidate_team_filter_state,
)
from pas_connect.exceptions import APIRequestError
from pas_connect.mapper import map_team_session
from pas_connect.services import GET_TEAM_SESSIONS_QUERY, TEAM_SELECTOR_QUERY


def _client(payload=None, *, error=None, token="token", password=""):
    def transport(request, timeout, verify_tls):
        if error:
            raise error
        body = json.loads(request.data)
        response = payload(body) if callable(payload) else payload
        return 200, json.dumps(response).encode()

    config = GPExeConfig(
        base_url="https://example.test/ui/v2/", token=token, password=password,
        max_retries=0,
    )
    return GPExeGraphQLClient(config, transport=transport, sleep=lambda _: None)


def _page(content, count):
    return {"data": {"res": {"content": content, "count": count}}}


def test_team_selector_matches_real_schema_and_alias():
    captured = {}

    def response(body):
        captured.update(body)
        return _page([{"id": "7", "name": "First", "season": "2026"}], 1)

    teams = GPExeServices(_client(response)).teams()
    assert teams[0]["id"] == "7"
    assert captured["operationName"] == "TeamSelector"
    assert captured["variables"] == {
        "sort": "club__name,name,season", "active": True, "first": 100, "skip": 0,
    }
    assert "res: teams(" in captured["query"]
    assert "content {" in captured["query"]
    assert "limitedClub {" in captured["query"]


@pytest.mark.parametrize("active", [True, False])
def test_team_selector_passes_requested_active_state(active):
    captured = {}

    def response(body):
        captured.update(body["variables"])
        return _page([], 0)

    GPExeServices(_client(response)).teams(active=active)
    assert captured["active"] is active
    assert captured["sort"] == "club__name,name,season"


def test_all_teams_calls_active_and_expired_and_deduplicates_by_id():
    active_calls = []

    def response(body):
        active = body["variables"]["active"]
        active_calls.append(active)
        rows = ([{"id": "1", "name": "SERIE A"}, {"id": "2"}]
                if active else [{"id": "2"}, {"id": "3"}])
        return _page(rows, len(rows))

    provider = GPExeAPIDataProvider(GPExeServices(_client(response)))
    teams = provider.get_teams(active=None)
    assert active_calls == [True, False]
    assert [team["id"] for team in teams] == ["1", "2", "3"]


def test_team_filter_change_invalidates_only_team_dependent_state():
    state = {
        "pas_gpexe_teams": [{"id": "1"}],
        "pas_gpexe_selected_team_index": 0,
        "pas_gpexe_team_sessions": [{"id": "10"}],
        "pas_gpexe_session_selection": {"edited_rows": {}},
        "pas_gpexe_runtime_token": "keep-token",
        "unrelated": "keep",
    }
    invalidate_team_filter_state(state)
    assert state == {"pas_gpexe_runtime_token": "keep-token", "unrelated": "keep"}


def test_get_team_sessions_matches_real_schema_and_fragments():
    captured = {}

    def response(body):
        captured.update(body)
        return _page([{"id": "11", "category": {"id": "2", "name": "Training"}}], 1)

    sessions = GPExeServices(_client(response)).team_sessions(
        team_id="7", start_date="2026-07-29", end_date="2026-08-04"
    )
    assert sessions[0]["id"] == "11"
    assert captured["operationName"] == "GetTeamSessions"
    assert captured["variables"] == {
        "teamId": "7", "startDate": "2026-07-29", "endDate": "2026-08-04",
        "first": 100, "skip": 0,
    }
    assert "fragment TeamSessionCategoryTypeFields on TeamSessionCategoryType" in captured["query"]
    assert "res: teamSessions(" in captured["query"]
    for field in ("totalTime", "originalTeamsession", "athleteCount", "rpeSet"):
        assert field in captured["query"]


@pytest.mark.parametrize("graphql_query", [TEAM_SELECTOR_QUERY, GET_TEAM_SESSIONS_QUERY])
def test_queries_do_not_use_unverified_pagination_arguments(graphql_query):
    for argument in ("offset:", "pageSize:", "after:", "pageInfo", "endCursor"):
        assert argument not in graphql_query
    assert "first:" in graphql_query
    assert "skip:" in graphql_query


def test_team_selector_paginates_with_first_skip_count_and_deduplicates():
    calls = []

    def response(body):
        variables = body["variables"]
        calls.append(dict(variables))
        if variables["skip"] == 0:
            return _page([{"id": "1"}, {"id": "2"}], 4)
        return _page([{"id": "2"}, {"id": "3"}], 4)

    teams = GPExeServices(_client(response), page_size=2).teams()
    assert [team["id"] for team in teams] == ["1", "2", "3"]
    assert [call["skip"] for call in calls] == [0, 2]
    assert all(call["first"] == 2 for call in calls)


def test_team_sessions_pagination_stops_on_empty_page():
    calls = []

    def response(body):
        calls.append(dict(body["variables"]))
        return _page([{"id": "10"}, {"id": "11"}], 5) if len(calls) == 1 else _page([], 5)

    sessions = GPExeServices(_client(response), page_size=2).team_sessions(
        team_id="7", start_date="2026-07-29", end_date="2026-08-04"
    )
    assert [session["id"] for session in sessions] == ["10", "11"]
    assert [call["skip"] for call in calls] == [0, 2]


def test_single_page_response_returns_complete_content():
    service = GPExeServices(_client(_page([{"id": "1"}, {"id": "2"}], 2)))
    assert [team["id"] for team in service.teams()] == ["1", "2"]


def test_empty_team_and_team_sessions_responses():
    assert GPExeServices(_client(_page([], 0))).teams() == []
    assert GPExeServices(_client(_page([], 0))).team_sessions(
        team_id="7", start_date="2026-07-29", end_date="2026-08-04"
    ) == []


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


def test_http_400_diagnostic_is_useful_and_redacts_sensitive_data():
    token = "jwt-never-show"
    password = "password-never-show"
    payload = {
        "errors": [{"message": f"invalid query {token} {password}"}],
        "debug": {"Authorization": f"JWT {token}", "Cookie": "secret-cookie"},
    }

    def transport(request, timeout, verify_tls):
        return 400, json.dumps(payload).encode(), {"Set-Cookie": "secret-cookie"}

    client = GPExeGraphQLClient(
        GPExeConfig(base_url="https://example.test/ui/v2/", token=token, password=password, max_retries=0),
        transport=transport,
    )
    with pytest.raises(APIRequestError) as exc_info:
        GPExeServices(client).teams()
    message = str(exc_info.value)
    assert "TeamSelector" in message
    assert "HTTP 400" in message
    assert "invalid query" in message
    for secret in (token, password, "secret-cookie", "Authorization"):
        assert secret not in message


def test_selected_team_sessions_persist_in_pas_connect_database(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    raw = {
        "id": "11", "category": {"id": 2, "name": "Training"},
        "startTimestamp": "2026-08-03T10:00:00Z", "duration": 5400,
        "athleteCount": 22, "matchCycle": 4, "state": "READY", "drill": False,
        "drillEnabled": True, "team": "7",
    }
    result = database.upsert_team_sessions({"sessions": [map_team_session(raw)]})
    assert result.received == 1
    assert result.inserted == 1
    assert database.team_session_count() == 1


def test_unimplemented_controls_keep_release_message():
    service = GPExeServices(_client(_page([], 0)))
    with pytest.raises(APIRequestError, match="Funzione disponibile in una release successiva"):
        service.tracks()
