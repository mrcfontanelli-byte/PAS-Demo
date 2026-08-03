import json
from urllib.request import Request

from pas_connect import GPExeAPIDataProvider, GPExeClient, GPExeConfig, GPExeServices
from pas_connect.endpoints import TEAMS


def test_authentication_and_token_management():
    requests: list[Request] = []
    def transport(request, timeout, verify_tls):
        requests.append(request)
        if request.full_url.endswith('/auth/token/'):
            return 200, b'{"token":"runtime-token"}'
        return 200, b'{"results":[]}'
    client = GPExeClient(GPExeConfig(username='user', password='pass'), transport=transport)
    assert client.authenticate() == 'runtime-token'
    assert client.request(TEAMS) == {'results': []}
    assert requests[-1].headers['Authorization'] == 'Token runtime-token'


def test_202_and_rate_limit_are_retried_without_real_sleep():
    statuses = iter([(202, b'', {'Retry-After':'0'}), (429, b'', {'Retry-After':'0'}), (200, b'[]', {})])
    client = GPExeClient(GPExeConfig(token='x', max_retries=3), transport=lambda *args: next(statuses), sleep=lambda _: None)
    assert client.request(TEAMS) == []


def test_401_refreshes_token_once():
    calls = []
    def transport(request, timeout, verify_tls):
        calls.append(request.full_url)
        if request.full_url.endswith('/auth/token/'):
            return 200, b'{"token":"new"}'
        if len([url for url in calls if url.endswith('/team/')]) == 1:
            return 401, b'{}'
        return 200, b'[]'
    client = GPExeClient(GPExeConfig(username='u', password='p', token='old'), transport=transport, sleep=lambda _: None)
    assert client.request(TEAMS) == []
    assert client.token == 'new'


def test_services_and_api_provider_are_separate_from_excel():
    def transport(request, timeout, verify_tls):
        if '/session/team/' in request.full_url:
            return 200, json.dumps({'results':[{'id': 10}]}).encode()
        return 200, json.dumps({'results':[{'id': 1, 'name':'First Team'}]}).encode()
    provider = GPExeAPIDataProvider(GPExeServices(GPExeClient(GPExeConfig(token='x'), transport=transport)))
    assert provider.provider_id == 'gpexe_api'
    assert provider.get_teams()[0]['name'] == 'First Team'
    assert provider.get_team_sessions(1)[0]['id'] == 10
