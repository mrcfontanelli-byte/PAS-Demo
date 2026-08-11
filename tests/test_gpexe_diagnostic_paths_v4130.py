import json

import pytest

from pas_connect import GPExeConfig, GPExeGraphQLClient, GPExeServices
from pas_connect.services import TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY
from pas_connect.exceptions import APIRequestError


def _client_with_errors(errors, *, token="runtime-token-never-display"):
    def transport(*_):
        return 200, json.dumps({"errors": errors}).encode(), {"Content-Type": "application/json"}

    return GPExeGraphQLClient(
        GPExeConfig(token=token), transport=transport,
    )


def test_graphql_errors_preserve_path_and_optional_extension_code():
    client = _client_with_errors([{
        "message": "Field 'id' expected a number but got ''.",
        "path": ["res", "athleteSessions", 0, "track", "athlete", "id"],
        "extensions": {"code": "GRAPHQL_VALIDATION_FAILED", "private": "discard-me"},
    }])
    with pytest.raises(APIRequestError) as captured:
        client.graphql("query X { x }", operation_name="X")
    assert captured.value.graphql_errors == ({
        "message": "Field 'id' expected a number but got ''.",
        "path": ["res", "athleteSessions", 0, "track", "athlete", "id"],
        "extensions": {"code": "GRAPHQL_VALIDATION_FAILED"},
    },)


def test_graphql_error_message_only_remains_compatible_and_sensitive_values_are_redacted():
    secret = "secret-never-display"
    client = _client_with_errors([
        {"message": f"Authorization: {secret}"},
        {"message": "message only"},
    ], token=secret)
    with pytest.raises(APIRequestError) as captured:
        client.graphql("query X { x }", operation_name="X")
    assert secret not in str(captured.value)
    assert secret not in repr(captured.value.graphql_errors)
    assert captured.value.graphql_errors[1] == {"message": "message only"}


def test_service_adds_structured_errors_to_c05_trace():
    trace = []
    services = GPExeServices(_client_with_errors([{
        "message": "bad id", "path": ["res", "athleteSessions", 3, "athlete", "id"],
        "extensions": {"code": "BAD_USER_INPUT"},
    }]))
    with pytest.raises(APIRequestError):
        services.team_session_athlete_sessions(team_session_id=143261, trace=lambda c, d: trace.append((c, d)))
    c05 = trace[-1]
    assert c05[0] == "C-05"
    assert c05[1]["graphqlErrors"] == [{
        "message": "bad id",
        "path": ["res", "athleteSessions", 3, "athlete", "id"],
        "extensions": {"code": "BAD_USER_INPUT"},
    }]


def test_structural_fallback_query_omits_only_kpi_resolvers():
    assert "identifierKpi" not in TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY
    assert " kpi " not in TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY
    for field in ("athleteSessions", "track {", "athlete {", "masterAthleteSession", "totalTime"):
        assert field in TEAM_SESSION_ATHLETESESSION_NO_KPI_QUERY
