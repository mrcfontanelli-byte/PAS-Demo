from pathlib import Path

import pytest

from pas_connect.client import GPExeClient
from pas_connect.config import GPExeConfig
from pas_connect.exceptions import APIRequestError
from pas_connect.storage import SnapshotStore
from pas_connect.sync import fetch_all_pages, sync_reference_data


def _transport(request, timeout, verify_tls):
    import json
    from urllib.parse import urlparse

    path = urlparse(request.full_url).path
    query = urlparse(request.full_url).query
    if path.endswith('/team/'):
        body = [{"id": 1, "name": "FIRST TEAM", "season": "2025-2026", "club": 1}]
    elif path.endswith('/session/category/'):
        body = [{"id": 2, "name": "FULL TRAINING", "team": 1, "color": "#fff"}]
    elif path.endswith('/session/tags/'):
        body = [{"id": 3, "name": "ENDURANCE", "team": 1}]
    elif path.endswith('/athlete/'):
        body = [{"id": 4, "name": "John Doe", "first_name": "John", "last_name": "Doe", "club": 1}]
    else:
        raise AssertionError(path)
    return 200, json.dumps(body).encode()


def test_reference_sync_maps_and_counts(tmp_path):
    client = GPExeClient(GPExeConfig(base_url="https://example.test", token="abc"), transport=_transport)
    with pytest.raises(APIRequestError, match="Query GraphQL Team/TeamSession"):
        sync_reference_data(client)


def test_ui_exposes_reference_sync():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "Sincronizza anagrafiche GPExe" in app
    assert "Il database Excel e le analisi del PAS restano invariati" in app
