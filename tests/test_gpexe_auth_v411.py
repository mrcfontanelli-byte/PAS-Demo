import json

import pytest

from pas_connect import GPExeConfig, GPExeGraphQLClient
from pas_connect.exceptions import APIRequestError, AuthenticationError


def test_authentication_uses_token_auth_json_payload_only():
    captured = []

    def transport(request, timeout, verify_tls):
        captured.append(request)
        return 200, b'{"data":{"tokenAuth":{"isActive":true,"token":"jwt","refreshToken":"refresh"}}}'

    client = GPExeGraphQLClient(GPExeConfig(username="user", password="pass"), transport=transport)
    assert client.authenticate() == "jwt"
    assert captured[0].headers["Content-type"] == "application/json"
    assert json.loads(captured[0].data)["variables"] == {"email": "user", "password": "pass"}


def test_graphql_authentication_errors_are_authentication_errors():
    client = GPExeGraphQLClient(
        GPExeConfig(username="user", password="secret"),
        transport=lambda *_: (200, b'{"errors":[{"message":"invalid credentials"}]}'),
    )
    with pytest.raises(AuthenticationError, match="Credenziali GPExe non valide"):
        client.authenticate()


def test_non_json_diagnostic_is_safe_and_actionable():
    client = GPExeGraphQLClient(
        GPExeConfig(username="user", password="secret"),
        transport=lambda *_: (200, b"<html>secret</html>", {"Content-Type": "text/html"}),
    )
    with pytest.raises(APIRequestError) as exc_info:
        client.authenticate()
    message = str(exc_info.value)
    assert "Content-Type text/html" in message
    assert "https://e15.gpexe.com/ui/v2/" in message
    assert "secret" not in message
