import json
import socket
from urllib.error import URLError

import pytest

from pas_connect import GPExeConfig, GPExeGraphQLClient
from pas_connect.exceptions import APIRequestError, AuthenticationError


def _auth_response(*, active=True, token="jwt-token", refresh="refresh-token"):
    return json.dumps(
        {"data": {"tokenAuth": {"isActive": active, "token": token, "refreshToken": refresh}}}
    ).encode("utf-8")


def test_graphql_token_auth_succeeds_and_manages_tokens():
    calls = []

    def transport(request, timeout, verify_tls):
        calls.append((request, timeout, verify_tls))
        return 200, _auth_response(), {"Content-Type": "application/json"}

    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password", timeout_seconds=12),
        transport=transport,
    )

    assert client.test_connection() is True
    assert client.token == "jwt-token"
    assert client.refresh_token == "refresh-token"
    assert client.is_active is True
    request, timeout, verify_tls = calls[0]
    assert request.full_url == "https://e15.gpexe.com/ui/v2/"
    assert request.get_method() == "POST"
    assert request.headers["Content-type"] == "application/json"
    assert timeout == 12
    assert verify_tls is True
    body = json.loads(request.data.decode("utf-8"))
    assert body["operationName"] == "TokenAuth"
    assert body["variables"] == {"email": "mail@example.com", "password": "password"}


def test_invalid_credentials_from_graphql_errors_are_readable_and_safe():
    secret = "password-never-expose"

    def transport(*_):
        payload = {"errors": [{"message": f"invalid credentials: {secret}"}]}
        return 200, json.dumps(payload).encode(), {"Content-Type": "application/json"}

    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password=secret), transport=transport
    )
    with pytest.raises(AuthenticationError) as exc_info:
        client.authenticate()
    assert "Credenziali GPExe non valide" in str(exc_info.value)
    assert secret not in str(exc_info.value)


def test_inactive_account_is_rejected():
    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password"),
        transport=lambda *_: (200, _auth_response(active=False), {}),
    )
    with pytest.raises(AuthenticationError, match="non attivo"):
        client.authenticate()


def test_response_without_token_is_rejected():
    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password"),
        transport=lambda *_: (200, _auth_response(token=""), {}),
    )
    with pytest.raises(AuthenticationError, match="token valido"):
        client.authenticate()


@pytest.mark.parametrize("network_error", [TimeoutError(), socket.timeout(), URLError("offline")])
def test_network_errors_and_timeouts_are_retried_then_reported(network_error):
    calls = []

    def transport(*_):
        calls.append(True)
        raise network_error

    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password", max_retries=1),
        transport=transport,
        sleep=lambda _: None,
    )
    with pytest.raises(APIRequestError):
        client.authenticate()
    assert len(calls) == 2


def test_http_error_is_reported_without_response_secrets():
    leaked = "server-token-never-expose"
    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password", max_retries=0),
        transport=lambda *_: (403, leaked.encode(), {"Content-Type": "text/plain"}),
    )
    with pytest.raises(APIRequestError, match="HTTP 403") as exc_info:
        client.authenticate()
    assert leaked not in str(exc_info.value)


def test_non_json_response_has_safe_diagnostics():
    secret = "password-never-expose"
    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password=secret),
        transport=lambda *_: (
            200,
            f"<html>{secret}</html>".encode(),
            {"Content-Type": "text/html"},
        ),
    )
    with pytest.raises(APIRequestError) as exc_info:
        client.authenticate()
    message = str(exc_info.value)
    assert "non JSON" in message
    assert "Content-Type text/html" in message
    assert secret not in message


def test_missing_or_invalid_data_is_rejected():
    client = GPExeGraphQLClient(
        GPExeConfig(username="mail@example.com", password="password"),
        transport=lambda *_: (200, b'{"data":null}', {}),
    )
    with pytest.raises(APIRequestError, match="campo data valido"):
        client.authenticate()


def test_old_rest_auth_endpoint_is_absent_from_active_code():
    from pathlib import Path

    active_files = [Path("app.py"), *Path("pas_connect").glob("*.py")]
    old_endpoint = "/api/rest/v2/auth/" + "token/"
    assert all(old_endpoint not in path.read_text(encoding="utf-8") for path in active_files)
