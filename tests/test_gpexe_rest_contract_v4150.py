from __future__ import annotations

import json

import pytest

from pas_connect import GPExeConfig, GPExeRESTClient
from pas_connect.exceptions import APIRequestError, AuthenticationError, RateLimitError


def _json(payload: object) -> bytes:
    return json.dumps(payload).encode("utf-8")


def test_rest_authentication_uses_official_endpoint_and_payload():
    calls = []

    def transport(request, timeout, verify_tls):
        calls.append((request, timeout, verify_tls))
        return 200, _json({"token": "rest-token"}), {"Content-Type": "application/json"}

    client = GPExeRESTClient(
        GPExeConfig(
            base_url="https://example.test",
            username="api-user",
            password="api-password",
            timeout_seconds=12,
        ),
        transport=transport,
    )

    assert client.authenticate() == "rest-token"
    request, timeout, verify_tls = calls[0]
    assert request.full_url == "https://example.test/rest/v2/auth/token/"
    assert request.get_method() == "POST"
    assert request.headers.get("Authorization") is None
    assert request.headers["Content-type"] == "application/json"
    assert json.loads(request.data) == {"username": "api-user", "password": "api-password"}
    assert timeout == 12
    assert verify_tls is True


def test_rest_gets_are_read_only_and_send_token_authorization_header():
    calls = []
    responses = iter(
        [
            {"id": 143261},
            [{"id": 9001}],
            {"id": 9001, "distance": 1234},
        ]
    )

    def transport(request, *_):
        calls.append(request)
        return 200, _json(next(responses)), {"Content-Type": "application/json"}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token"),
        transport=transport,
    )

    assert client.team_session(143261, all_params=True, export_template=17)["id"] == 143261
    assert client.athlete_sessions(143261)[0]["id"] == 9001
    assert client.athlete_session(9001)["distance"] == 1234
    assert [request.get_method() for request in calls] == ["GET", "GET", "GET"]
    assert [request.headers["Authorization"] for request in calls] == [
        "Token rest-token",
        "Token rest-token",
        "Token rest-token",
    ]
    assert calls[0].full_url == (
        "https://example.test/rest/v2/session/team/143261/"
        "?all_params=true&export_template=17"
    )
    assert calls[1].full_url == (
        "https://example.test/rest/v2/session/team/143261/athlete_sessions/"
    )
    assert calls[2].full_url == "https://example.test/rest/v2/session/athlete/9001/"


def test_rest_redaction_removes_known_secrets_and_arbitrary_authorization_values():
    password = "password-never-print"
    token = "token-never-print"
    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", password=password, token=token)
    )

    safe = client.redact(
        f"password={password}; token={token}; Authorization: Token unknown-server-secret"
    )

    assert password not in safe
    assert token not in safe
    assert "unknown-server-secret" not in safe
    assert safe.count("[dato sensibile rimosso]") == 3


@pytest.mark.parametrize("status", [401, 403])
def test_rest_auth_errors_clear_runtime_token(status):
    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token", max_retries=0),
        transport=lambda *_: (status, b"Authorization: Token leaked", {}),
    )

    with pytest.raises(AuthenticationError, match=f"HTTP {status}") as exc_info:
        client.team_session(143261)

    assert client.token == ""
    assert "rest-token" not in str(exc_info.value)
    assert "leaked" not in str(exc_info.value)


def test_rest_404_is_terminal_and_does_not_expose_response_body():
    secret = "body-secret"
    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token", max_retries=3),
        transport=lambda *_: (404, secret.encode(), {}),
    )

    with pytest.raises(APIRequestError, match="HTTP 404") as exc_info:
        client.team_session(143261)

    assert secret not in str(exc_info.value)


def test_rest_429_honors_retry_after_then_raises_rate_limit_error():
    delays = []
    calls = []

    def transport(*_):
        calls.append(True)
        return 429, b'{"detail":"limited"}', {"Retry-After": "2"}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token", max_retries=1),
        transport=transport,
        sleep=delays.append,
    )

    with pytest.raises(RateLimitError, match="HTTP 429"):
        client.athlete_sessions(143261)

    assert len(calls) == 2
    assert delays == [2.0]


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_rest_server_errors_retry_then_fail_safely(status):
    calls = []

    def transport(*_):
        calls.append(True)
        return status, b"password=server-secret", {}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token", max_retries=1),
        transport=transport,
        sleep=lambda _: None,
    )

    with pytest.raises(APIRequestError, match=f"HTTP {status}") as exc_info:
        client.athlete_session(9001)

    assert len(calls) == 2
    assert "server-secret" not in str(exc_info.value)


@pytest.mark.parametrize("bad_id", [0, -1, "", "not-an-id", None])
def test_rest_contract_methods_reject_invalid_ids_before_transport(bad_id):
    called = False

    def transport(*_):
        nonlocal called
        called = True
        return 200, b"{}", {}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="rest-token"),
        transport=transport,
    )

    with pytest.raises(ValueError, match="intero positivo"):
        client.team_session(bad_id)
    assert called is False


def test_rest_client_has_no_database_or_full_sync_dependency():
    import pas_connect.rest_client as module

    source = open(module.__file__, encoding="utf-8").read()
    assert "PASConnectDatabase" not in source
    assert "run_full_sync" not in source
    assert "excel" not in source.lower()
