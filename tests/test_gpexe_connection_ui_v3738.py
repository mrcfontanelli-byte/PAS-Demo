from pathlib import Path

from pas_connect.client import GPExeClient
from pas_connect.config import GPExeConfig
from pas_connect.endpoints import TEAMS


def test_gpexe_client_authenticates_then_reads_teams_without_network():
    calls = []

    def transport(request, timeout, verify_tls):
        calls.append((request.full_url, request.get_method(), request.headers.get("Authorization")))
        if request.full_url.endswith("/rest/v2/auth/token/"):
            return 200, b'{"token":"runtime-token"}'
        return 200, b'{"count":1,"results":[{"id":10,"name":"First Team"}]}'

    client = GPExeClient(
        GPExeConfig(
            base_url="https://example.test",
            username="user",
            password="secret",
        ),
        transport=transport,
    )
    assert client.authenticate() == "runtime-token"
    response = client.request(TEAMS, query={"page": 1, "page_size": 1})
    assert response["count"] == 1
    assert calls[0][1] == "POST"
    assert calls[1][2] == "Token runtime-token"


def test_settings_exposes_connection_test_and_keeps_excel_active():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Connetti a GPExe" in app
    assert "Excel resta la sorgente dati attiva" in app
    assert "pas_gpexe_runtime_token" in app
    assert "App settings → Secrets" in app
