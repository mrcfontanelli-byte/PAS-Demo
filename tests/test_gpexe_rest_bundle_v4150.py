from __future__ import annotations

import copy
import json
from pathlib import Path

from pas_connect import GPExeRESTService, RESTProcessingResponse
from pas_connect.exceptions import APIRequestError, RateLimitError

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


class FakeRESTClient:
    _positive_id = staticmethod(lambda value, _label: int(value))

    def __init__(self, team=None, ids=None, details=None, team_error=None, list_error=None):
        self.team = team if team is not None else fixture("gpexe_rest_team_session_143261_anonymized.json")
        self.ids = ids if ids is not None else fixture("gpexe_rest_athlete_sessions_143261_anonymized.json")
        self.details = details or {}
        self.team_error = team_error
        self.list_error = list_error
        self.calls = []

    @staticmethod
    def redact(value):
        return str(value).replace("secret", "[dato sensibile rimosso]")

    def team_session(self, team_session_id, **options):
        self.calls.append(("team", team_session_id, options))
        if self.team_error:
            raise self.team_error
        return copy.deepcopy(self.team)

    def athlete_sessions(self, team_session_id):
        self.calls.append(("list", team_session_id))
        if self.list_error:
            raise self.list_error
        return copy.deepcopy(self.ids)

    def athlete_session(self, athlete_session_id):
        self.calls.append(("detail", athlete_session_id))
        value = self.details[athlete_session_id]
        if isinstance(value, Exception):
            raise value
        return copy.deepcopy(value)


def complete_client(count=27):
    team = fixture("gpexe_rest_team_session_143261_anonymized.json")
    team["header"]["athletes"] = count
    team["counts"]["n_tracks"] = count
    base = fixture("gpexe_rest_athlete_session_anonymized.json")
    ids = list(range(910001, 910001 + count))
    team["table_data"]["athlete_sessions"] = [{"id": value} for value in ids]
    details = {}
    for index, session_id in enumerate(ids):
        row = copy.deepcopy(base)
        row.update(id=session_id, athlete=810001 + index, track=710001 + index)
        details[session_id] = row
    return FakeRESTClient(team=team, ids={"athletesessions_id": ids}, details=details)


def messages(result):
    return [str(item["message"]) for item in result.diagnostics]


def test_complete_bundle_with_27_athlete_sessions_is_ready_and_serial():
    client = complete_client()
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "READY"
    assert result.processing is False
    assert len(result.bundle["athlete_session_ids"]) == 27
    assert len(result.bundle["athlete_sessions"]) == 27
    assert [call[0] for call in client.calls] == ["team", "list", *(["detail"] * 27)]
    assert result.diagnostics == ()


def test_duplicate_ids_fail_before_detail_requests():
    client = complete_client(2)
    client.ids = {"athletesessions_id": [910001, 910001]}
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "FAILED"
    assert result.bundle is None
    assert not any(call[0] == "detail" for call in client.calls)
    assert any("duplicati" in message for message in messages(result))


def test_internal_team_session_reference_is_provenance_not_membership_gate():
    client = complete_client(1)
    client.details[910001]["teamsession"] = 999999
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "READY"
    session = result.bundle["athlete_sessions"][0]
    assert session["provider_session_id"] == 999999
    assert session["raw"]["teamsession"] == 999999
    assert session["provenance"] == "gpexe_rest_athlete_session_detail"


def test_detail_id_different_from_scoped_id_is_not_ready():
    client = complete_client(1)
    client.details[910001]["id"] = 910099
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert any("non presente nella lista" in message for message in messages(result))


def test_scoped_and_aggregate_set_mismatch_is_not_ready_without_detail_requests():
    client = complete_client(2)
    client.team["table_data"]["athlete_sessions"] = [{"id": 910001}, {"id": 910099}]
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert result.bundle is None
    assert not any(call[0] == "detail" for call in client.calls)
    diagnostic = next(
        item for item in result.diagnostics
        if item["stage"] == "athlete_session_membership"
    )
    assert diagnostic["scoped_only_count"] == 1
    assert diagnostic["aggregate_only_count"] == 1


def test_missing_track_makes_bundle_incomplete():
    client = complete_client(1)
    client.details[910001]["track"] = None
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert len(result.bundle["athlete_sessions"]) == 0
    assert any(item.get("failed_count") == 1 for item in result.diagnostics)


def test_required_kpi_null_is_not_replaced_with_zero_and_is_incomplete():
    client = complete_client(1)
    client.details[910001]["distance"] = None
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    metric = next(
        row for row in result.bundle["athlete_sessions"][0]["kpis"]
        if row["provider_name"] == "distance"
    )
    assert metric["value"] is None
    assert any("distance" in message for message in messages(result))


def test_null_rpe_is_preserved_without_making_bundle_incomplete():
    result = GPExeRESTService(complete_client(1)).build_team_session_bundle(143261)
    assert result.status == "READY"
    rpe = next(
        row for row in result.bundle["athlete_sessions"][0]["kpis"]
        if row["provider_name"] == "rpe"
    )
    assert rpe["value"] is None
    assert rpe["active"] is True


def test_missing_optional_max_speed_does_not_make_bundle_incomplete():
    client = complete_client(1)
    del client.details[910001]["max_values_speed"]
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "READY"
    assert not any(
        metric["provider_name"] == "max_values_speed"
        for metric in result.bundle["athlete_sessions"][0]["kpis"]
    )


def test_unknown_metric_is_preserved_but_inactive():
    client = complete_client(1)
    client.details[910001]["future_metric"] = 12.5
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "READY"
    metric = next(
        row for row in result.bundle["athlete_sessions"][0]["kpis"]
        if row["provider_name"] == "future_metric"
    )
    assert metric["value"] == 12.5
    assert metric["canonical_metric"] is None
    assert metric["active"] is False


def test_one_failed_athlete_session_produces_incomplete_bundle_and_redacted_diagnostic():
    client = complete_client(3)
    client.details[910002] = APIRequestError("Authorization: Token secret")
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert len(result.bundle["athlete_sessions"]) == 2
    assert "secret" not in repr(result.diagnostics)
    assert any(item.get("failed_count") == 1 for item in result.diagnostics)


def test_multiple_failed_athlete_sessions_produce_incomplete_bundle():
    client = complete_client(3)
    client.details[910001] = APIRequestError("first")
    client.details[910003] = APIRequestError("second")
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert len(result.bundle["athlete_sessions"]) == 1
    assert any(item.get("failed_count") == 2 for item in result.diagnostics)


def test_team_session_failure_is_failed():
    client = FakeRESTClient(team_error=APIRequestError("team failed"))
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "FAILED"
    assert result.bundle is None
    assert [call[0] for call in client.calls] == ["team"]


def test_athlete_session_list_failure_is_failed():
    client = FakeRESTClient(list_error=APIRequestError("list failed"))
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "FAILED"
    assert result.bundle is None
    assert [call[0] for call in client.calls] == ["team", "list"]


def test_rate_limit_error_from_list_is_failed_without_retry_in_service():
    client = FakeRESTClient(list_error=RateLimitError("HTTP 429"))
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "FAILED"
    assert result.bundle is None
    assert [call[0] for call in client.calls] == ["team", "list"]


def test_team_session_202_is_processing_incomplete_without_polling():
    client = FakeRESTClient(team=RESTProcessingResponse(
        payload={"status": "processing"}, retry_after_seconds=5.0,
    ), ids=RESTProcessingResponse(payload={"status": "processing"}))
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert result.processing is True
    assert result.bundle is None
    assert result.diagnostics[0]["retry_after_seconds"] == 5.0
    assert [call[0] for call in client.calls] == ["team", "list"]


def test_one_athlete_session_202_is_processing_incomplete_without_polling():
    client = complete_client(2)
    client.details[910002] = RESTProcessingResponse(retry_after_seconds=4.0)
    result = GPExeRESTService(client).build_team_session_bundle(143261)
    assert result.status == "INCOMPLETE"
    assert result.processing is True
    assert len(result.bundle["athlete_sessions"]) == 1
    assert any(item.get("retry_after_seconds") == 4.0 for item in result.diagnostics)


def test_dry_run_is_idempotent_and_does_not_mutate_provider_payloads():
    client = complete_client(3)
    original_team = copy.deepcopy(client.team)
    original_details = copy.deepcopy(client.details)
    service = GPExeRESTService(client)
    first = service.build_team_session_bundle(143261)
    client.calls.clear()
    second = service.build_team_session_bundle(143261)
    assert first == second
    assert client.team == original_team
    assert client.details == original_details


def test_rest_bundle_service_has_no_excel_database_or_graphql_dependency():
    import pas_connect.rest_service as module

    source = Path(module.__file__).read_text(encoding="utf-8").lower()
    assert "excel" not in source
    assert "pasconnectdatabase" not in source
    assert "run_full_sync" not in source
    assert "graphql" not in source
