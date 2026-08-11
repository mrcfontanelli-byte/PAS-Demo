from pathlib import Path

from pas_connect.client import GPExeGraphQLClient
from pas_connect.config import GPExeConfig


def test_gpexe_client_authenticates_with_graphql_without_network():
    calls = []

    def transport(request, timeout, verify_tls):
        calls.append((request.full_url, request.get_method(), request.headers.get("Authorization")))
        return 200, b'{"data":{"tokenAuth":{"isActive":true,"token":"runtime-token","refreshToken":"refresh"}}}'

    client = GPExeGraphQLClient(
        GPExeConfig(
            base_url="https://example.test",
            username="user",
            password="secret",
        ),
        transport=transport,
    )
    assert client.authenticate() == "runtime-token"
    assert calls[0][1] == "POST"
    assert calls[0][0] == "https://example.test/"


def test_settings_exposes_connection_test_and_keeps_excel_active():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Connetti a GPExe" in app
    assert "Excel resta la sorgente predefinita" in app
    assert "pas_gpexe_runtime_token" in app
    assert "App settings → Secrets" in app
    assert '"Recupera Team Sessions"' in app
    assert '"Importa nel database PAS"' not in app
    assert '"Team da mostrare"' in app
    assert '("Attivi", "Scaduti", "Tutti")' in app
    assert "invalidate_team_filter_state" in app
    assert '"Club ID GPExe"' in app
    assert "resolve_team_club_id" in app
