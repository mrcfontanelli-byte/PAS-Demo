from __future__ import annotations

import json
import sqlite3

import pytest

from pas_connect import GPExeAPIDataProvider, GPExeConfig, GPExeGraphQLClient, GPExeServices, PASConnectDatabase, invalidate_athlete_filter_state, invalidate_athlete_session_state, invalidate_athlete_context_state, resolve_team_club_id, store_athlete_fetch_result, athletes_from_team_session_results, team_session_error_diagnostic, normalize_team_session_error_diagnostics, TEAM_SESSION_DIAGNOSTIC_COLUMNS
from pas_connect.exceptions import APIRequestError
from pas_connect.mapper import map_graphql_athlete, map_graphql_athlete_session, map_team_session
from pas_connect.services import ATHLETES_QUERY, TEAM_SESSION_ATHLETESESSION_QUERY


def _client(responder):
    def transport(request, timeout, verify_tls):
        body = json.loads(request.data)
        return 200, json.dumps(responder(body)).encode(), {}
    return GPExeGraphQLClient(
        GPExeConfig(base_url="https://example.test/ui/v2/", token="safe", max_retries=0),
        transport=transport,
    )


def _page(rows, count):
    return {"data": {"res": {"content": rows, "count": count}}}


@pytest.mark.parametrize(
    ("tab", "club_id", "expected"),
    [("CURRENT", None, {"teamId": "7", "tab": "CURRENT"}),
     ("EXPIRED", "9", {"teamId": "7", "clubId": "9", "tab": "EXPIRED"})],
)
def test_athletes_real_query_current_and_expired(tab, club_id, expected):
    captured = {}
    service = GPExeServices(_client(lambda body: captured.update(body) or _page([], 0)))
    service.athletes(team_id="7", club_id=club_id, tab=tab)
    assert captured["operationName"] == "Athletes"
    for key, value in expected.items():
        assert captured["variables"][key] == value
    assert captured["variables"]["first"] == 50
    assert captured["variables"]["skip"] == 0
    assert captured["variables"]["sort"] == "last_name,first_name"
    assert "res: athletes(" in ATHLETES_QUERY
    assert "deviceSet" in ATHLETES_QUERY


def test_expired_athletes_requires_team_club_id():
    service = GPExeServices(_client(lambda _: _page([], 0)))
    with pytest.raises(APIRequestError, match="Club ID non disponibile"):
        service.athletes(team_id="7", tab="EXPIRED")


def test_current_athletes_does_not_require_or_send_club_id():
    captured = {}
    service = GPExeServices(_client(lambda body: captured.update(body["variables"]) or _page([], 0)))
    service.athletes(team_id="7", tab="CURRENT")
    assert "clubId" not in captured


def test_expired_athletes_uses_automatic_limited_club_id():
    captured = {}
    team = {"id": "7", "limitedClub": {"id": "9", "name": "Club"}}
    club_id = resolve_team_club_id(team)
    GPExeServices(_client(lambda body: captured.update(body["variables"]) or _page([], 0))).athletes(
        team_id=team["id"], club_id=club_id, tab="EXPIRED",
    )
    assert captured["clubId"] == "9"


def test_expired_athletes_uses_manual_club_id_without_hardcode():
    captured = {}
    team = {"id": "7", "limitedClub": {"name": "Club"}}
    club_id = resolve_team_club_id(team, " 12 ")
    GPExeServices(_client(lambda body: captured.update(body["variables"]) or _page([], 0))).athletes(
        team_id=team["id"], club_id=club_id, tab="EXPIRED",
    )
    assert captured["clubId"] == "12"


def test_expired_click_variables_and_populated_content_diagnostics():
    captured = {}
    athlete = {"id": "5", "playerSet": [{"team": {"id": "7"}}]}
    service = GPExeServices(_client(lambda body: captured.update(body["variables"]) or _page([athlete], 1)))
    provider = GPExeAPIDataProvider(service)
    assert provider.get_athletes("7", club_id="4", tab="EXPIRED") == [athlete]
    assert captured == {
        "teamId": "7", "clubId": "4", "sort": "last_name,first_name",
        "tab": "EXPIRED", "first": 50, "skip": 0,
    }
    assert service.last_diagnostics == {
        "operationName": "Athletes", "received": 1, "count": 1,
        "serverReceived": 1, "teamMatched": 1, "teamId": "7",
    }


def test_empty_content_has_explicit_zero_diagnostics():
    service = GPExeServices(_client(lambda _: _page([], 0)))
    assert service.athletes(team_id="7", club_id="4", tab="EXPIRED") == []
    assert service.last_diagnostics == {
        "operationName": "Athletes", "received": 0, "count": 0,
        "serverReceived": 0, "teamMatched": 0, "teamId": "7",
    }


def test_expired_filters_mixed_teams_with_string_integer_ids_and_multiple_memberships():
    rows = [
        {"id": "1", "playerSet": [{"team": {"id": 469}}]},
        {"id": "2", "playerSet": [{"team": {"id": "100"}}, {"team": {"id": "469"}}]},
        {"id": "3", "playerSet": [{"team": {"id": 100}}]},
        {"id": "4", "playerSet": []},
    ]
    service = GPExeServices(_client(
        lambda body: _page(rows, 849) if body["variables"]["skip"] == 0 else _page([], 849)
    ))
    result = service.athletes(team_id="469", club_id="4", tab="EXPIRED")
    assert [row["id"] for row in result] == ["1", "2"]
    assert service.last_diagnostics["serverReceived"] == 4
    assert service.last_diagnostics["teamMatched"] == 2
    assert service.last_diagnostics["count"] == 849
    assert service.last_diagnostics["teamId"] == "469"


def test_all_filters_expired_before_deduplication():
    def response(body):
        if body["variables"]["tab"] == "CURRENT":
            return _page([{"id": "1"}, {"id": "2"}], 2)
        return _page([
            {"id": "2", "playerSet": [{"team": {"id": "469"}}]},
            {"id": "3", "playerSet": [{"team": {"id": 999}}]},
            {"id": "4", "playerSet": [{"team": {"id": 469}}]},
        ], 3)
    provider = GPExeAPIDataProvider(GPExeServices(_client(response)))
    assert [row["id"] for row in provider.get_athletes("469", club_id="4", tab=None)] == ["1", "2", "4"]


def test_participant_roster_excludes_historical_absent_athlete_and_counts_sessions():
    results = [
        {"team_session_id": "10", "result": {"athleteSessions": [
            {"id": "100", "athlete": {"id": "1", "name": "One"}},
            {"id": "101", "athlete": {"id": 2, "name": "Two"}},
        ]}},
        {"team_session_id": "11", "result": {"athleteSessions": [
            {"id": "102", "athlete": {"id": "1", "name": "One"}},
        ]}},
    ]
    roster = athletes_from_team_session_results(results)
    assert [str(item["id"]) for item in roster] == ["1", "2"]
    assert {str(item["id"]): item["teamSessionAppearances"] for item in roster} == {"1": 2, "2": 1}
    assert "historical-absent" not in {str(item["id"]) for item in roster}


def test_participant_roster_without_selected_sessions_is_empty():
    assert athletes_from_team_session_results([]) == []


def test_participant_import_is_limited_to_encountered_athletes(tmp_path):
    results = [{"team_session_id": "10", "result": {"athleteSessions": [
        {"id": "100", "athlete": {"id": "1", "name": "Present"}},
    ]}}]
    encountered = athletes_from_team_session_results(results)
    database = PASConnectDatabase(tmp_path / "participants.sqlite3")
    assert database.upsert_graphql_athletes([
        map_graphql_athlete(item, team_id="469") for item in encountered
    ]) == (1, 0)
    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT provider_player_id FROM gpexe_athletes").fetchall() == [(1,)]


def test_athlete_result_persists_in_session_state_across_rerun_reads():
    state = {"pas_gpexe_runtime_token": "keep", "pas_gpexe_athlete_selection": {"stale": True}}
    store_athlete_fetch_result(
        state, [{"id": "5"}], {"operationName": "Athletes", "received": 1, "count": 1},
    )
    rerun_state = state
    assert rerun_state["pas_gpexe_athletes"] == [{"id": "5"}]
    assert rerun_state["pas_gpexe_athletes_loaded"] is True
    assert rerun_state["pas_gpexe_runtime_token"] == "keep"
    assert "pas_gpexe_athlete_selection" not in rerun_state


def test_ui_contains_empty_result_message_and_safe_diagnostics():
    from pathlib import Path
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Nessun atleta trovato per il Team e il filtro selezionati." in app
    assert "operationName:" in app
    assert "ricevuti dal server:" in app
    assert "appartenenti al Team:" in app
    assert "Nessun atleta associato al Team selezionato." in app
    assert '"Seleziona": False' in app
    assert "on_change=invalidate_athlete_context_state" in app
    assert "Tutti gli associati al Team" in app
    assert "Solo partecipanti alle TeamSession selezionate" in app
    assert "Seleziona almeno una TeamSession per ricostruire la rosa del periodo." in app
    assert '"Presenze TeamSession"' in app


def test_athletes_http_error_diagnostic_does_not_expose_secrets():
    token = "athletes-token-never-show"
    password = "athletes-password-never-show"
    def transport(request, timeout, verify_tls):
        payload = {"errors": [{"message": f"bad request {token} {password}"}], "cookie": "hidden"}
        return 400, json.dumps(payload).encode(), {"Set-Cookie": "hidden"}
    client = GPExeGraphQLClient(
        GPExeConfig(base_url="https://example.test/ui/v2/", token=token, password=password, max_retries=0),
        transport=transport,
    )
    with pytest.raises(APIRequestError) as exc_info:
        GPExeServices(client).athletes(team_id="7", club_id="4", tab="EXPIRED")
    message = str(exc_info.value)
    assert "Athletes" in message and "HTTP 400" in message
    assert token not in message and password not in message and "hidden" not in message


def test_all_athletes_deduplicates_and_keeps_first_skip_count():
    calls = []
    def response(body):
        variables = body["variables"]
        calls.append(dict(variables))
        if variables["tab"] == "CURRENT":
            return _page([{"id": "1"}, {"id": "2"}], 2)
        return _page([
            {"id": "2", "playerSet": [{"team": {"id": "7"}}]},
            {"id": "3", "playerSet": [{"team": {"id": 7}}]},
        ], 2)
    provider = GPExeAPIDataProvider(GPExeServices(_client(response), page_size=50))
    assert [row["id"] for row in provider.get_athletes("7", club_id="9", tab=None)] == ["1", "2", "3"]
    assert [(call["tab"], call["skip"], call["first"]) for call in calls] == [
        ("CURRENT", 0, 50), ("EXPIRED", 0, 50)
    ]


def test_athletes_pagination_uses_received_rows_for_skip():
    skips = []
    def response(body):
        skip = body["variables"]["skip"]
        skips.append(skip)
        return _page([{"id": "1"}, {"id": "2"}], 3) if skip == 0 else _page([{"id": "3"}], 3)
    rows = GPExeServices(_client(response), page_size=2).athletes(team_id="7")
    assert [row["id"] for row in rows] == ["1", "2", "3"]
    assert skips == [0, 2]


def test_athlete_filter_invalidation_does_not_touch_team_or_sessions():
    state = {
        "pas_gpexe_athletes": [1], "pas_gpexe_athlete_selection": {"x": 1},
        "pas_gpexe_teams": [2], "pas_gpexe_selected_team_index": 0,
        "pas_gpexe_team_sessions": [3],
    }
    invalidate_athlete_filter_state(state)
    assert state == {
        "pas_gpexe_teams": [2], "pas_gpexe_selected_team_index": 0,
        "pas_gpexe_team_sessions": [3],
    }


def test_club_id_change_uses_same_athlete_only_invalidation():
    state = {
        "pas_gpexe_athletes": [1], "pas_gpexe_athlete_selection": {"selected": [1]},
        "pas_gpexe_teams": [2], "pas_gpexe_team_sessions": [3],
        "pas_gpexe_club_id_7": "4",
    }
    invalidate_athlete_filter_state(state)
    assert state == {
        "pas_gpexe_teams": [2], "pas_gpexe_team_sessions": [3],
        "pas_gpexe_club_id_7": "4",
    }


@pytest.mark.parametrize("template_id", ["2319", 2319, None, ""])
def test_team_session_athlete_sessions_template_and_null_options(template_id):
    captured = {}
    response = {"data": {"res": {"id": "10", "athleteSessions": []}}}
    service = GPExeServices(_client(lambda body: captured.update(body) or response))
    result = service.team_session_athlete_sessions(
        team_session_id="10", template_id=template_id, drill=None,
    )
    assert result["athleteSessions"] == []
    assert captured["operationName"] == "TeamSessionAthletesession"
    assert captured["variables"]["id"] == 10
    assert captured["variables"]["templateId"] == (2319 if template_id not in (None, "") else None)
    assert captured["variables"]["drill"] is None
    assert "identifierKpi" in TEAM_SESSION_ATHLETESESSION_QUERY
    assert " kpi {" in TEAM_SESSION_ATHLETESESSION_QUERY


def test_team_session_athlete_sessions_normalizes_and_omits_empty_scalars():
    captured = {}
    service = GPExeServices(_client(lambda body: captured.update(body) or {"data": {"res": {"id": 10}}}))
    service.team_session_athlete_sessions(
        team_session_id="10", template_id="", drill="42", fields_limit="",
    )
    assert captured["variables"] == {
        "id": 10, "templateId": None, "drill": 42,
    }
    assert all(value != "" for value in captured["variables"].values())


@pytest.mark.parametrize("team_session_id", ["", None, "not-a-number"])
def test_team_session_athlete_sessions_never_sends_invalid_required_id(team_session_id):
    called = False

    def responder(_body):
        nonlocal called
        called = True
        return {"data": {"res": {}}}

    with pytest.raises(APIRequestError):
        GPExeServices(_client(responder)).team_session_athlete_sessions(
            team_session_id=team_session_id,
        )
    assert called is False


def test_team_session_error_diagnostic_has_request_context_and_redacts_secrets():
    token = "jwt-secret-value"
    error = APIRequestError(
        f"Operazione TeamSessionAthletesession · HTTP 400 · errori GraphQL: invalid template {token} Authorization: JWT-secret Cookie=session-secret."
    )
    diagnostic = team_session_error_diagnostic(
        error, team_session_id="10", template_id="2319", drill=None,
        fields_limit=80, secrets=(token, "session-secret"),
    )
    assert diagnostic["operationName"] == "TeamSessionAthletesession"
    assert diagnostic["httpStatus"] == 400
    assert "invalid template" in diagnostic["graphqlErrors"]
    assert diagnostic["teamSessionId"] == 10
    assert diagnostic["templateId"] == 2319
    assert diagnostic["drill"] is None
    assert diagnostic["fieldsLimit"] == 80
    assert diagnostic["variables"] == {
        "id": 10, "templateId": 2319, "drill": None, "fieldsLimit": 80,
    }
    serialized = json.dumps(diagnostic)
    assert token not in serialized
    assert "session-secret" not in serialized


def test_ui_renders_team_session_error_diagnostics_below_summary():
    from pathlib import Path
    app = Path("app.py").read_text(encoding="utf-8")
    summary_position = app.index("st.dataframe(pd.DataFrame(summary)")
    diagnostics_position = app.index("Diagnostica TeamSessionAthletesession")
    assert diagnostics_position > summary_position
    assert tuple(TEAM_SESSION_DIAGNOSTIC_COLUMNS) == (
        "operationName", "httpStatus", "graphqlErrors", "message",
        "teamSessionId", "templateId", "drill", "fieldsLimit", "variables",
    )
    assert "columns=TEAM_SESSION_DIAGNOSTIC_COLUMNS" in app


def test_historical_diagnostic_without_variables_is_normalized():
    records = normalize_team_session_error_diagnostics([{
        "operationName": "TeamSessionAthletesession",
        "message": "errore storico",
        "teamSessionId": 10,
    }])
    assert records[0]["message"] == "errore storico"
    assert records[0]["variables"]["id"] == 10
    assert set(TEAM_SESSION_DIAGNOSTIC_COLUMNS).issubset(records[0])


def test_mixed_old_and_new_diagnostics_create_complete_dataframe_without_keyerror():
    import pandas as pd

    old = {"message": "old", "teamSessionId": "10"}
    new = {"message": "new", "teamSessionId": 11, "variables": {"id": 11}}
    records = normalize_team_session_error_diagnostics([old, new])
    frame = pd.DataFrame(records).reindex(columns=TEAM_SESSION_DIAGNOSTIC_COLUMNS)
    assert list(frame.columns) == list(TEAM_SESSION_DIAGNOSTIC_COLUMNS)
    assert frame.loc[0, "variables"]["id"] == "10"
    assert frame.loc[1, "variables"] == {"id": 11}
    assert frame["message"].tolist() == ["old", "new"]


def test_ui_normalizes_historical_diagnostics_before_rendering():
    from pathlib import Path

    app = Path("app.py").read_text(encoding="utf-8")
    normalize_at = app.index("normalize_team_session_error_diagnostics(")
    render_at = app.index("diagnostic_frame = pd.DataFrame", normalize_at)
    assert normalize_at < render_at
    assert ".reindex(" in app[render_at:render_at + 300]


def test_database_migration_and_idempotent_graphql_imports(tmp_path):
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    athlete_raw = {
        "id": "5", "firstName": "Ada", "lastName": "Lovelace", "name": "Ada Lovelace",
        "shortName": "A. Lovelace", "customId": "custom-5", "isActive": True,
        "hasTracks": True, "deviceSet": [{"id": "d1"}],
        "playerSet": {"number": 10, "team": {"id": "7"}},
    }
    athlete = map_graphql_athlete(athlete_raw, team_id="7")
    assert database.upsert_graphql_athletes([athlete]) == (1, 0)
    assert database.upsert_graphql_athletes([athlete]) == (0, 1)
    database.upsert_team_sessions({"sessions": [map_team_session({"id": "10", "team": 7, "name": "Training"})]})
    raw_session = {
        "id": "20", "masterAthleteSession": "master", "drill": None,
        "state": "READY", "isStatsValid": True, "starter": False,
        "athlete": {"id": "5"},
        "track": {"id": "30", "hasCardio": True, "athlete": {"id": "5"}},
        "totalTime": {"value": 60, "unit": "s", "uom": "s"},
        "identifierKpi": [{"name": "Distance", "value": 100, "group": "GPS", "unit": "m", "uom": "m"}],
        "kpi": [{"name": "Speed", "value": 8.2, "group": "GPS", "unit": "m/s", "uom": "m/s"}],
    }
    mapped = map_graphql_athlete_session(raw_session, team_session_id="10", template_id="2319")
    assert database.upsert_graphql_athlete_sessions([mapped]) == (1, 0, 1, 2)
    assert database.upsert_graphql_athlete_sessions([mapped]) == (0, 1, 1, 2)
    with sqlite3.connect(database.path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM gpexe_athletes").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM gpexe_athlete_session_details").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM gpexe_tracks").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM gpexe_athlete_session_kpis").fetchone()[0] == 2
        assert connection.execute("SELECT template_id FROM gpexe_athlete_session_details").fetchone()[0] == "2319"
        assert {row[0] for row in connection.execute("SELECT source FROM gpexe_athlete_session_kpis")} == {"identifierKpi", "kpi"}


def test_normal_rerun_preserves_team_sessions_results_and_last_import():
    state = {
        "pas_gpexe_selected_team_index": 1,
        "pas_gpexe_session_selection": {"edited_rows": {0: {"Seleziona": True}}},
        "pas_gpexe_athlete_session_results": [{"team_session_id": "10"}],
        "pas_gpexe_athlete_session_errors": [],
        "pas_gpexe_last_athlete_session_import": {"status": "success", "message": "ok"},
    }
    rerun_state = state
    assert rerun_state == state


def test_team_session_change_invalidates_only_retrieval_and_import_message():
    state = {
        "pas_gpexe_selected_team_index": 1,
        "pas_gpexe_session_selection": {"edited_rows": {}},
        "pas_gpexe_athlete_session_results": [1],
        "pas_gpexe_athlete_session_errors": [2],
        "pas_gpexe_last_athlete_session_import": {"status": "success"},
    }
    invalidate_athlete_session_state(state)
    assert state == {
        "pas_gpexe_selected_team_index": 1,
        "pas_gpexe_session_selection": {"edited_rows": {}},
    }


def test_context_change_invalidates_athletes_and_athlete_sessions_but_not_team():
    state = {
        "pas_gpexe_teams": [{"id": "469"}], "pas_gpexe_selected_team_index": 0,
        "pas_gpexe_athletes": [1], "pas_gpexe_athlete_selection": {},
        "pas_gpexe_athlete_session_results": [2],
        "pas_gpexe_last_athlete_session_import": {"status": "success"},
    }
    invalidate_athlete_context_state(state)
    assert state == {"pas_gpexe_teams": [{"id": "469"}], "pas_gpexe_selected_team_index": 0}


def test_ui_import_is_guarded_and_persists_success_or_error_message():
    from pathlib import Path
    app = Path("app.py").read_text(encoding="utf-8")
    import_position = app.index('if st.button("Importa Athlete Sessions e KPI nel database PAS"')
    block = app[import_position:import_position + 5000]
    assert "try:" in block and "except Exception as exc:" in block
    assert 'st.session_state["pas_gpexe_last_athlete_session_import"]' in block
    assert "st.error(" in block
    assert "Tracks in UPSERT" in block and "KPI sostituiti" in block


def test_v440_does_not_connect_new_data_to_dashboard_or_reports():
    from pathlib import Path
    app = Path("app.py").read_text(encoding="utf-8")
    assert "upsert_graphql_athlete_sessions" in app
    assert "Dashboard" not in ATHLETES_QUERY
    assert "report" not in TEAM_SESSION_ATHLETESESSION_QUERY.lower()
