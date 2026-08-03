import json

from pas_connect import GPExeConfig, GPExeGraphQLClient
from pas_connect.config import normalize_gpexe_base_url


def test_graphql_endpoint_is_configurable_and_normalized():
    assert normalize_gpexe_base_url(" https://example.test/graphql/ ") == "https://example.test/graphql"


def test_client_posts_json_to_configured_graphql_endpoint():
    captured = {}

    def transport(request, timeout, verify_tls):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode())
        return 200, b'{"data":{"tokenAuth":{"isActive":true,"token":"jwt","refreshToken":"refresh"}}}'

    client = GPExeGraphQLClient(
        GPExeConfig(base_url="https://example.test/graphql/", username="user", password="secret"),
        transport=transport,
    )
    assert client.authenticate() == "jwt"
    assert captured["url"] == "https://example.test/graphql/"
    assert captured["method"] == "POST"
    assert captured["body"]["operationName"] == "TokenAuth"
