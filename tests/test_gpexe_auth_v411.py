from urllib.request import Request

import pytest

from pas_connect import GPExeClient, GPExeConfig
from pas_connect.exceptions import AuthenticationError


def test_authentication_uses_form_payload_first():
    captured: list[Request] = []

    def transport(request, timeout, verify_tls):
        captured.append(request)
        return 200, b'{"token":"form-token"}', {"Content-Type": "application/json"}

    client = GPExeClient(GPExeConfig(username="user", password="pass"), transport=transport)
    assert client.authenticate() == "form-token"
    assert captured[0].headers["Content-type"] == "application/x-www-form-urlencoded"
    assert captured[0].data == b"username=user&password=pass"


def test_authentication_falls_back_to_json():
    captured: list[Request] = []

    def transport(request, timeout, verify_tls):
        captured.append(request)
        if len(captured) == 1:
            return 200, b"<html>form not supported</html>", {"Content-Type": "text/html"}
        return 200, b'{"access_token":"json-token"}', {"Content-Type": "application/json"}

    client = GPExeClient(GPExeConfig(username="user", password="pass"), transport=transport)
    assert client.authenticate() == "json-token"
    assert captured[1].headers["Content-type"] == "application/json"


def test_non_json_diagnostic_is_safe_and_actionable():
    def transport(request, timeout, verify_tls):
        return 200, b"<html>Login page</html>", {"Content-Type": "text/html; charset=utf-8"}

    client = GPExeClient(GPExeConfig(username="user", password="secret"), transport=transport)
    with pytest.raises(AuthenticationError) as exc_info:
        client.authenticate()
    message = str(exc_info.value)
    assert "Content-Type text/html" in message
    assert "/rest/v2/auth/token/" in message
    assert "Login page" in message
    assert "secret" not in message
