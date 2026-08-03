import pytest

from pas_connect import GPExeAPIDataProvider, GPExeConfig, GPExeGraphQLClient, GPExeServices
from pas_connect.exceptions import APIRequestError


def test_transient_http_errors_are_retried_without_real_sleep():
    statuses = iter([
        (429, b"", {"Retry-After": "0"}),
        (200, b'{"data":{"tokenAuth":{"isActive":true,"token":"jwt","refreshToken":"refresh"}}}', {}),
    ])
    client = GPExeGraphQLClient(
        GPExeConfig(username="user", password="pass", max_retries=1),
        transport=lambda *_: next(statuses),
        sleep=lambda _: None,
    )
    assert client.authenticate() == "jwt"


def test_provider_remains_separate_but_unverified_queries_are_blocked():
    client = GPExeGraphQLClient(GPExeConfig(token="runtime-token"))
    provider = GPExeAPIDataProvider(GPExeServices(client))
    assert provider.provider_id == "gpexe_api"
    with pytest.raises(APIRequestError, match="Query GraphQL Team/TeamSession"):
        provider.get_teams()
    with pytest.raises(APIRequestError, match="Query GraphQL Team/TeamSession"):
        provider.get_team_sessions(1)
