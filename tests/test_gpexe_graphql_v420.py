import json
from pas_connect import GPExeClient, GPExeConfig


def test_graphql_token_auth_and_connection_test():
    calls=[]
    def transport(request, timeout, verify_tls):
        calls.append(request)
        payload=json.loads(request.data.decode())
        if payload.get('operationName') == 'TokenAuth':
            return 200, json.dumps({'data': {'tokenAuth': {'isActive': True, 'token': 'jwt-token', 'refreshToken': 'refresh'}}}).encode(), {'Content-Type':'application/json'}
        assert request.headers['Authorization'] == 'JWT jwt-token'
        return 200, b'{"data":{"__typename":"Query"}}', {'Content-Type':'application/json'}
    client=GPExeClient(GPExeConfig(username='mail@example.com', password='pass'), transport=transport)
    assert client.authenticate() == 'jwt-token'
    assert client.refresh_token == 'refresh'
    assert client.test_connection() is True
    assert calls[0].full_url == 'https://e15.gpexe.com/ui/v2/'
    body=json.loads(calls[0].data.decode())
    assert body['variables'] == {'email':'mail@example.com','password':'pass'}
    assert body['operationName'] == 'TokenAuth'


def test_graphql_errors_are_reported_without_password():
    def transport(request, timeout, verify_tls):
        return 200, b'{"errors":[{"message":"invalid credentials"}]}', {'Content-Type':'application/json'}
    client=GPExeClient(GPExeConfig(username='mail@example.com', password='secret'), transport=transport)
    try:
        client.authenticate()
    except Exception as exc:
        assert 'invalid credentials' in str(exc)
        assert 'secret' not in str(exc)
    else:
        raise AssertionError('Expected authentication error')
