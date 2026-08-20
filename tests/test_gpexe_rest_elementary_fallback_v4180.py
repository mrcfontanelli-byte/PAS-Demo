from __future__ import annotations

import copy
import json
from pathlib import Path

from pas_connect.config import GPExeConfig
from pas_connect.rest_client import GPExeRESTClient, RESTProcessingResponse
from pas_connect.rest_mapper import map_rest_team_session
from pas_connect.rest_service import (
    BUNDLE_PROVENANCE_AGGREGATE,
    BUNDLE_PROVENANCE_ELEMENTARY,
    GPExeRESTService,
)


FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def canonical_team(count: int = 2):
    raw = fixture("gpexe_rest_team_session_143261_anonymized.json")
    raw["header"]["athletes"] = count
    raw["counts"]["n_tracks"] = count
    raw["table_data"]["athlete_sessions"] = [
        {"id": value} for value in range(910001, 910001 + count)
    ]
    return raw, map_rest_team_session(raw)


def detail_payloads(count: int = 2):
    base = fixture("gpexe_rest_athlete_session_anonymized.json")
    ids = list(range(910001, 910001 + count))
    details = {}
    for offset, athlete_session_id in enumerate(ids):
        row = copy.deepcopy(base)
        row.update(
            id=athlete_session_id,
            athlete=810001 + offset,
            track=710001 + offset,
        )
        details[athlete_session_id] = row
    return ids, details


class Client:
    _positive_id = staticmethod(lambda value, _label: int(value))

    def __init__(self, team, ids, details):
        self.team = team
        self.ids = ids
        self.details = details
        self.calls = []

    @staticmethod
    def redact(value):
        return str(value)

    def team_session(self, session_id, **options):
        self.calls.append(("aggregate", session_id, options))
        return copy.deepcopy(self.team)

    def athlete_sessions(self, session_id):
        self.calls.append(("list", session_id))
        return copy.deepcopy(self.ids)

    def athlete_session(self, athlete_session_id):
        self.calls.append(("detail", athlete_session_id))
        return copy.deepcopy(self.details[athlete_session_id])


def test_aggregate_200_keeps_existing_path_and_provenance():
    raw_team, _ = canonical_team()
    ids, details = detail_payloads()
    client = Client(raw_team, {"athletesessions_id": ids}, details)
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "READY"
    assert result.bundle["provenance"] == BUNDLE_PROVENANCE_AGGREGATE
    assert [call[0] for call in client.calls] == ["aggregate", "list", "detail", "detail"]


def test_aggregate_202_uses_complete_elementary_bundle_once_and_is_equivalent():
    raw_team, metadata = canonical_team()
    ids, details = detail_payloads()
    aggregate_client = Client(raw_team, {"athletesessions_id": ids}, details)
    aggregate = GPExeRESTService(aggregate_client).build_team_session_bundle(143261)
    fallback_client = Client(
        RESTProcessingResponse(payload={"status": "processing", "task_id": "task-safe"}),
        {"athletesessions_id": ids},
        details,
    )
    fallback = GPExeRESTService(fallback_client).build_team_session_bundle(
        143261, team_session_metadata=metadata,
    )
    assert fallback.status == "READY"
    assert fallback.processing is False
    assert fallback.bundle["provenance"] == BUNDLE_PROVENANCE_ELEMENTARY
    assert fallback.bundle["athlete_sessions"] == aggregate.bundle["athlete_sessions"]
    assert fallback.bundle["athlete_session_ids"] == aggregate.bundle["athlete_session_ids"]
    assert [call[0] for call in fallback_client.calls] == [
        "aggregate", "list", "detail", "detail",
    ]
    assert fallback.diagnostics[0]["task_id"] == "task-safe"


def test_elementary_missing_track_or_required_kpi_is_not_ready():
    _, metadata = canonical_team()
    ids, details = detail_payloads()
    details[ids[0]]["track"] = None
    details[ids[1]]["distance"] = None
    client = Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        {"athletesessions_id": ids}, details,
    )
    result = GPExeRESTService(client).build_team_session_bundle(
        143261, team_session_metadata=metadata,
    )
    assert result.status == "INCOMPLETE"
    assert result.processing is True
    assert any("Track" in item["message"] for item in result.diagnostics)
    assert any("distance" in item["message"] for item in result.diagnostics)


def test_normal_session_internal_teamsession_match_remains_ready():
    _, metadata = canonical_team(1)
    ids, details = detail_payloads(1)
    details[ids[0]]["teamsession"] = 143261
    result = GPExeRESTService(Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        {"athletesessions_id": ids}, details,
    )).build_team_session_bundle(143261, team_session_metadata=metadata)
    assert result.status == "READY"


def test_drill_session_uses_scoped_membership_and_preserves_internal_parent():
    _, metadata = canonical_team(1)
    metadata = dict(metadata)
    metadata["provider_session_id"] = 144769
    metadata["nature"] = "D"
    metadata["drill"] = {"number": 6, "count": 0, "enabled": False}
    ids, details = detail_payloads(1)
    details[ids[0]]["teamsession"] = 144761
    details[ids[0]]["drill"] = 6
    result = GPExeRESTService(Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        {"athletesessions_id": ids}, details,
    )).build_team_session_bundle(144769, team_session_metadata=metadata)
    assert result.status == "READY"
    session = result.bundle["athlete_sessions"][0]
    assert session["raw"]["teamsession"] == 144761
    assert session["raw"]["drill"] == 6


def test_elementary_missing_scoped_detail_is_not_ready():
    _, metadata = canonical_team(2)
    ids, details = detail_payloads(2)
    details[ids[1]] = RuntimeError("missing")
    result = GPExeRESTService(Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        {"athletesessions_id": ids}, details,
    )).build_team_session_bundle(143261, team_session_metadata=metadata)
    assert result.status == "INCOMPLETE"
    assert len(result.bundle["athlete_sessions"]) == 1


def test_aggregate_and_list_202_defer_without_detail_calls():
    _, metadata = canonical_team()
    client = Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        RESTProcessingResponse(payload={"status": "processing"}),
        {},
    )
    result = GPExeRESTService(client).build_team_session_bundle(
        143261, team_session_metadata=metadata,
    )
    assert result.status == "INCOMPLETE"
    assert result.processing is True
    assert [call[0] for call in client.calls] == ["aggregate", "list"]


def test_processing_retry_after_body_header_precedence_and_task_metadata():
    responses = [
        (202, b'{"retry_after":7,"task_id":"a","original_task_id":"b"}', {}),
        (202, b'{"retry_after":7,"task_id":"a","original_task_id":"b"}',
         {"Retry-After": "3"}),
    ]
    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="token", max_retries=0),
        transport=lambda *_: responses.pop(0),
    )
    body = client.team_session(143261)
    header = client.team_session(143261)
    assert body.retry_after_seconds == 7.0
    assert header.retry_after_seconds == 3.0
    assert body.task_id == "a" and body.original_task_id == "b"


def test_elementary_metrics_zones_tracks_have_no_duplicates_or_source_blending():
    _, metadata = canonical_team(1)
    ids, details = detail_payloads(1)
    client = Client(
        RESTProcessingResponse(payload={"status": "processing"}),
        {"athletesessions_id": ids}, details,
    )
    result = GPExeRESTService(client).build_team_session_bundle(
        143261, team_session_metadata=metadata,
    )
    session = result.bundle["athlete_sessions"][0]
    provider_names = [metric["provider_name"] for metric in session["kpis"]]
    assert len(provider_names) == len(set(provider_names))
    assert session["track"]["provider_track_id"] == str(details[ids[0]]["track"])
    assert session["zones"]["speed_zones"]
    assert {metric["provenance"] for metric in session["kpis"]} == {
        "gpexe_rest_athlete_session_detail"
    }
