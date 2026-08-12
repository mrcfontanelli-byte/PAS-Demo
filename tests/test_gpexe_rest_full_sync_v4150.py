from __future__ import annotations

import json

import pytest

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.rest_service import GPExeRESTService, RESTBundleResult
from pas_connect.sync import SyncRequest, run_full_sync, run_rest_sync


class DummyRESTClient:
    def redact(self, value):
        return str(value).replace("secret", "[redacted]")


def _metric(name, canonical, value):
    return {
        "provider_name": name, "canonical_metric": canonical, "value": value,
        "value_type": "null" if value is None else "number", "unit": None,
        "active": True, "provenance": "gpexe_rest_athlete_session_detail",
        "raw": {"name": name, "value": value, "unit": None},
    }


def _ready(session_id=143261, team_id=543, athlete_id=7001, detail_id=8001, track_id=9001):
    metrics = [
        _metric("distance", "Distance", 1000), _metric("duration", "Duration", 600),
        _metric("acceleration_events", "Acc Events", 3),
        _metric("deceleration_events", "Dec Events", 4),
        _metric("speed_events", "Speed Events", 2), _metric("rpe", "RPE", None),
    ]
    detail = {
        "provider_athlete_session_id": detail_id, "provider_session_id": session_id,
        "athlete": {"provider_player_id": athlete_id},
        "track": {"provider_track_id": str(track_id)}, "state": "READY",
        "starter": False, "is_stats_valid": True, "total_time": 600,
        "kpis": metrics, "raw": {"id": detail_id},
        "provenance": "gpexe_rest_athlete_session_detail",
    }
    return RESTBundleResult("READY", False, {
        "provider_contract": "rest_v2", "provider_session_id": session_id,
        "team_session": {
            "provider_session_id": session_id, "team_id": team_id,
            "category": {"id": 1, "name": "Training"}, "nature": "training",
            "start_timestamp": "2026-08-01T10:00:00Z", "total_time": 600,
            "is_stats_valid": True, "drill": {}, "raw": {"id": session_id},
        },
        "athlete_session_ids": (detail_id,), "athlete_sessions": (detail,),
    }, ())


def _service(results):
    service = GPExeRESTService(DummyRESTClient())
    calls = []
    def build(session_id, **kwargs):
        calls.append((session_id, kwargs))
        value = results[session_id]
        if isinstance(value, Exception):
            raise value
        return value
    service.build_team_session_bundle = build
    service.calls = calls
    return service


def _request(*ids, team=543, force=True):
    return SyncRequest(team, "2026/2027", selected_session_ids=tuple(ids),
                       force_refresh=force, transport="REST")


def test_full_sync_rest_ready_persists_history_membership_and_is_idempotent(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    service = _service({143261: _ready()})
    first = run_full_sync(service, db, request=_request(143261))
    second = run_full_sync(service, db, request=_request(143261))
    assert first.transport == second.transport == "REST"
    assert first.sessions[0].status == "SUCCESS"
    with db.connect() as con:
        counts = [con.execute(f"select count(*) from {table}").fetchone()[0] for table in (
            "gpexe_team_sessions", "gpexe_athlete_session_details", "gpexe_tracks",
            "gpexe_athlete_session_kpis", "gpexe_athlete_team_memberships",
        )]
        resources = {r[0] for r in con.execute("select resource_group from gpexe_sync_runs")}
    assert counts == [1, 1, 1, 6, 1]
    assert resources == {"rest_session_sync"}
    rows = db.list_session_sync_results(run_id=first.sync_run_id)
    assert rows[0]["readiness"] == "READY"
    assert rows[0]["operation_name"] == "RESTv2TeamSessionBundle"


@pytest.mark.parametrize("built,status,processing", [
    (RESTBundleResult("INCOMPLETE", False, None, ({"message": "missing"},)), "PARTIAL", False),
    (RESTBundleResult("FAILED", False, None, ({"message": "failed"},)), "FAILED", False),
    (RESTBundleResult("INCOMPLETE", True, None, ({"http_status": 202},)), "PARTIAL", True),
])
def test_rest_non_ready_is_recorded_and_never_published(tmp_path, built, status, processing):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(_service({1: built}), db, _request(1))
    assert result.sessions[0].status == status
    assert result.sessions[0].readiness == "INCOMPLETE"
    assert result.sessions[0].processing is processing
    with db.connect() as con:
        assert con.execute("select count(*) from gpexe_team_sessions").fetchone()[0] == 0
    stored = db.list_session_sync_results(run_id=result.sync_run_id)[0]
    assert json.loads(stored["diagnostics_json"])[-1]["processing"] is processing


def test_rest_failure_has_no_graphql_or_excel_fallback(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    service = _service({1: RuntimeError("provider failed secret")})
    result = run_full_sync(service, db, request=_request(1))
    assert result.sessions[0].status == "FAILED"
    assert "secret" not in result.sessions[0].error_message
    assert service.calls == [(1, {"all_params": True})]


def test_transport_type_mismatch_never_falls_back(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    rest = _service({1: _ready(1)})
    with pytest.raises(TypeError, match="GraphQL"):
        run_full_sync(rest, db, request=SyncRequest(
            543, "2026/2027", selected_session_ids=(1,), transport="GRAPHQL",
        ))
    with pytest.raises(TypeError, match="REST"):
        run_full_sync(object(), db, request=_request(1))
    assert not db.path.exists()


def test_rest_multi_team_isolation_and_schema_12(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    run_rest_sync(_service({1: _ready(1, 10, 70, 80, 90)}), db, _request(1, team=10))
    run_rest_sync(_service({2: _ready(2, 20, 70, 81, 91)}), db, _request(2, team=20))
    with db.connect() as con:
        memberships = con.execute(
            "select team_id,season from gpexe_athlete_team_memberships order by team_id"
        ).fetchall()
        assert con.execute("select value from pas_connect_meta where key='schema_version'").fetchone()[0] == "12"
    assert [tuple(row) for row in memberships] == [(10, "2026/2027"), (20, "2026/2027")]
    assert SCHEMA_VERSION == 12


def test_streamlit_ui_exposes_explicit_transport_and_summary_without_fallback():
    source = (__import__("pathlib").Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert '("REST ufficiale", "GraphQL legacy/internal")' in source
    assert 'key="pas_gpexe_sync_transport"' in source
    assert 'summary_columns[0].metric("Transport", latest_transport)' in source
    assert '"processing":' in source
    assert "GPExeRESTService(runtime_rest_client)" in source
    assert "runtime_rest_client.clear_token()" in source
