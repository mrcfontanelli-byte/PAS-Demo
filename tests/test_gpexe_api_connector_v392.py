from urllib.request import Request

from pas_connect.client import GPExeClient
from pas_connect.config import GPExeConfig, normalize_gpexe_base_url
from pas_connect.endpoints import TEAMS, TEAM_SESSIONS


def test_documentation_url_is_valid_api_root():
    assert normalize_gpexe_base_url(" https://e15-ui.gpexe.com/api/ ") == "https://e15-ui.gpexe.com/api"


def test_client_preserves_api_prefix_when_building_endpoints():
    captured: list[Request] = []

    def transport(request: Request, timeout: float, verify_tls: bool):
        captured.append(request)
        return 200, b"[]"

    client = GPExeClient(
        GPExeConfig(base_url="https://e15-ui.gpexe.com/api", token="secret"),
        transport=transport,
    )
    assert client.request(TEAMS) == []
    assert captured[0].full_url == "https://e15-ui.gpexe.com/api/rest/v2/team/"
    assert captured[0].headers["Authorization"] == "Token secret"


def test_session_endpoint_is_composed_from_instance_api_root():
    urls: list[str] = []

    def transport(request: Request, timeout: float, verify_tls: bool):
        urls.append(request.full_url)
        return 200, b'{"results": []}'

    client = GPExeClient(
        GPExeConfig(base_url="https://e15-ui.gpexe.com/api/", token="secret"),
        transport=transport,
    )
    client.request(TEAM_SESSIONS, query={"page": 1, "page_size": 25})
    assert urls == ["https://e15-ui.gpexe.com/api/rest/v2/session/team/?page=1&page_size=25"]
