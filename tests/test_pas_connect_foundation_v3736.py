from __future__ import annotations

import json

import pytest

from pas_connect.auth import authorization_header
from pas_connect.client import GPExeClient
from pas_connect.config import DataProvider, GPExeConfig, PASConnectConfig
from pas_connect.endpoints import ATHLETE_DETAIL
from pas_connect.mapper import map_athlete, parse_headers_table
from pas_connect.sync import build_default_sync_plan


def test_excel_remains_default_provider():
    config = PASConnectConfig()
    assert config.provider is DataProvider.EXCEL
    config.validate()


def test_client_builds_authenticated_request_without_network():
    captured = {}

    def transport(request, timeout, verify_tls):
        captured["url"] = request.full_url
        captured["auth"] = request.headers.get("Authorization")
        captured["timeout"] = timeout
        captured["verify_tls"] = verify_tls
        return 200, json.dumps({"id": 9}).encode()

    client = GPExeClient(
        GPExeConfig(base_url="https://example.test", token="abc", timeout_seconds=12),
        transport=transport,
    )
    result = client.request(ATHLETE_DETAIL, path_values={"id": 9})
    assert result == {"id": 9}
    assert captured == {
        "url": "https://example.test/rest/v2/athlete/9/",
        "auth": "Token abc",
        "timeout": 12,
        "verify_tls": True,
    }


def test_headers_drive_positional_metric_mapping():
    parsed = parse_headers_table(
        {
            "headers": [
                {"label": "athlete"},
                {"label": "distance"},
                {"label": "duration"},
            ],
            "athlete_sessions": [
                {
                    "id": 42,
                    "athlete": {"first_name": "A", "last_name": "B"},
                    "values": ["B A", "5577.1", "79:17"],
                }
            ],
        }
    )
    assert parsed[0]["metrics"] == {
        "athlete": "B A",
        "distance": "5577.1",
        "duration": "79:17",
    }


def test_athlete_mapping_and_sync_plan():
    athlete = map_athlete(
        {
            "id": 3,
            "first_name": "Mario",
            "last_name": "Rossi",
            "name": "ROSSI MARIO",
            "club": 1,
        }
    )
    assert athlete["provider_player_id"] == 3
    assert athlete["player_name"] == "ROSSI MARIO"
    plan = build_default_sync_plan()
    assert plan.steps[0].resource.value == "teams"
    assert plan.steps[-1].resource.value == "tracks"


def test_authorization_header_rejects_empty_token():
    with pytest.raises(Exception):
        authorization_header("")
