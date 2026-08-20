from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from pas_connect.config import GPExeConfig
from pas_connect.daily_sync import (
    DAILY_SEASON,
    DAILY_TEAM_ID,
    MAX_DAILY_ATTEMPTS,
    WINDOW_DAYS,
    DailyCatalogResult,
    DailySyncAction,
    next_retry_at,
    plan_daily_sync,
    refresh_daily_catalog,
    retry_is_mature,
    run_daily_sync,
)
from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.pas_bridge import available_sessions
from pas_connect.rest_client import GPExeRESTClient, RESTProcessingResponse
from pas_connect.sync import RESTIdentitySyncResult, SessionSyncResult, SyncRunResult


ROOT = Path(__file__).parents[1]
TODAY = date(2026, 8, 20)
NOW = datetime(2026, 8, 20, 12, tzinfo=timezone.utc)


def row(
    session_id: int,
    days_ago: int,
    description: str = "FULL TRAINING",
    *,
    team: int = DAILY_TEAM_ID,
    season: str = DAILY_SEASON,
    **extra,
):
    return {
        "team_id": team,
        "season": season,
        "team_session_id": session_id,
        "session_date": (TODAY - timedelta(days=days_ago)).isoformat(),
        "description": description,
        "locally_present": 0,
        "performance_usable": 0,
        **extra,
    }


def database(tmp_path: Path) -> PASConnectDatabase:
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    db.initialize()
    db.upsert_team_references([{
        "provider_team_id": DAILY_TEAM_ID,
        "team_name": "SERIE B",
        "season": DAILY_SEASON,
        "raw": {"id": DAILY_TEAM_ID, "season": DAILY_SEASON},
    }])
    return db


def client() -> GPExeRESTClient:
    return GPExeRESTClient(GPExeConfig(
        base_url="https://example.test", username="user", password="password",
    ))


def test_context_isolation_and_four_day_window():
    inventory = [
        *(row(100 + offset, offset) for offset in range(5)),
        row(200, 0, team=469, season="2025/2026"),
        row(300, 0, team=443, season="2024/2025"),
    ]
    plan = plan_daily_sync(inventory, today=TODAY, now=NOW)
    assert WINDOW_DAYS == 4
    assert [item.team_session_id for item in plan.candidates] == [100, 101, 102, 103, 104]
    assert all(item.team_id == 543 and item.season == "2026/2027" for item in plan.candidates)


def test_unseen_outside_window_is_bounded_and_never_becomes_backfill():
    inventory = [row(1000 + offset, 10 + offset) for offset in range(30)]
    plan = plan_daily_sync(inventory, today=TODAY, now=NOW)
    assert len(plan.candidates) == 1
    assert plan.candidates[0].team_session_id == 1000
    assert plan.candidates[0].action is DailySyncAction.FETCH_UNSEEN_OUTSIDE_WINDOW


def test_priority_full_training_then_canonical_retry_technical_and_deferred():
    inventory = [
        row(1, 1, "RECOVERY"),
        row(2, 2, "FULL TRAINING"),
        row(3, 0, "RETURN TO PLAY", sync_status="FAILED", last_attempt=NOW.isoformat()),
        row(4, 0, "EXERCISE"),
        row(5, 0, "FULL TRAINING", deferred_202=1,
            sync_status="PARTIAL", last_attempt=(NOW - timedelta(hours=3)).isoformat()),
    ]
    history = [{
        "team_id": 543, "sync_season": DAILY_SEASON, "provider_session_id": 5,
        "diagnostics_json": json.dumps([{"processing": True}]),
    }]
    plan = plan_daily_sync(inventory, history, today=TODAY, now=NOW)
    assert [item.team_session_id for item in plan.candidates] == [2, 1, 3, 4, 5]
    assert [item.priority for item in plan.candidates] == [0, 1, 2, 3, 4]


def test_same_priority_orders_newest_date_then_highest_id():
    plan = plan_daily_sync(
        [row(10, 1), row(12, 0), row(11, 0)], today=TODAY, now=NOW,
    )
    assert [item.team_session_id for item in plan.candidates] == [12, 11, 10]


def test_budget_is_never_more_than_ten():
    plan = plan_daily_sync(
        [row(100 + offset, 0) for offset in range(20)],
        today=TODAY, now=NOW, max_attempts=100,
    )
    assert MAX_DAILY_ATTEMPTS == 10
    assert len(plan.candidates) == 10


def test_ready_or_performance_complete_is_skipped():
    plan = plan_daily_sync([
        row(1, 0, performance_usable=1),
        row(2, 0, readiness="READY", sync_status="SUCCESS"),
        row(3, 0),
    ], today=TODAY, now=NOW)
    assert plan.already_complete == 2
    assert [item.team_session_id for item in plan.candidates] == [3]


@pytest.mark.parametrize(("attempts", "minutes"), [(1, 15), (2, 30), (3, 60), (4, 120), (8, 120)])
def test_202_cooldown_progression(attempts, minutes):
    assert next_retry_at(NOW, attempts) == NOW + timedelta(minutes=minutes)


def test_retry_after_has_precedence_and_maturity_is_pure():
    retry_at = next_retry_at(NOW, 4, retry_after_seconds=42)
    assert retry_at == NOW + timedelta(seconds=42)
    assert retry_is_mature(retry_at, NOW + timedelta(seconds=41)) is False
    assert retry_is_mature(retry_at, NOW + timedelta(seconds=42)) is True


def test_deferred_before_cooldown_is_skipped_then_becomes_candidate():
    inventory = [row(
        7, 0, deferred_202=1, sync_status="PARTIAL",
        last_attempt=(NOW - timedelta(minutes=10)).isoformat(),
    )]
    history = [{
        "team_id": 543, "sync_season": DAILY_SEASON, "provider_session_id": 7,
        "diagnostics_json": json.dumps([{"processing": True, "http_status": 202}]),
    }]
    early = plan_daily_sync(inventory, history, today=TODAY, now=NOW)
    mature = plan_daily_sync(inventory, history, today=TODAY, now=NOW + timedelta(minutes=6))
    assert early.candidates == () and early.deferred_cooldown == 1
    assert mature.candidates[0].action is DailySyncAction.RETRY_DEFERRED


def test_public_catalog_discovery_is_scoped_metadata_only_and_idempotent(tmp_path, monkeypatch):
    db = database(tmp_path)
    rest = client()
    calls = []

    def page(*, page, page_size):
        calls.append((page, page_size))
        if page == 1:
            return [
                {"id": 10, "team": 543, "name": "FULL TRAINING", "start_timestamp": "2026-08-20"},
                {"id": 11, "team": 469, "name": "FULL TRAINING", "start_timestamp": "2025-08-20"},
            ]
        return []

    monkeypatch.setattr(rest, "team_sessions_page", page)
    first = refresh_daily_catalog(rest, db)
    second = refresh_daily_catalog(rest, db)
    assert first.inserted == 1 and first.updated == 0
    assert second.inserted == 0 and second.updated == 1
    assert calls[:2] == [(1, 500), (2, 500)]
    with db.connect() as connection:
        assert connection.execute("select count(*) from gpexe_team_sessions").fetchone()[0] == 1
        assert connection.execute("select count(*) from gpexe_athlete_session_kpis").fetchone()[0] == 0


def test_processing_catalog_response_does_not_poll(tmp_path, monkeypatch):
    db = database(tmp_path)
    rest = client()
    calls = []
    monkeypatch.setattr(
        rest, "team_sessions_page",
        lambda **kwargs: calls.append(kwargs) or RESTProcessingResponse(),
    )
    result = refresh_daily_catalog(rest, db)
    assert result.pages_fetched == 0 and result.remote_team_sessions == 0
    assert len(calls) == 1


def test_executor_authenticates_once_shares_identity_and_continues(monkeypatch, tmp_path):
    db = database(tmp_path)
    rest = client()
    auth_calls = []
    monkeypatch.setattr(rest, "authenticate", lambda: auth_calls.append(1) or "token")
    monkeypatch.setattr(
        "pas_connect.daily_sync.refresh_daily_catalog",
        lambda client, database, max_pages: DailyCatalogResult(1, 3, 3, 0),
    )
    monkeypatch.setattr(PASConnectDatabase, "historical_session_inventory", lambda self, **kwargs: [
        row(1, 0), row(2, 0, "RECOVERY"), row(3, 0, "RETURN TO PLAY"),
    ])
    monkeypatch.setattr(PASConnectDatabase, "list_session_sync_results", lambda self, **kwargs: [])
    state = RESTIdentitySyncResult({}, set())
    monkeypatch.setattr(
        "pas_connect.daily_sync.run_rest_identity_sync",
        lambda client, database, ids: state,
    )
    calls = []

    def fake_run(service, database, request, *, identity_state):
        session_id = request.selected_session_ids[0]
        calls.append((request.team_id, request.season, session_id, identity_state))
        if session_id == 1:
            item = SessionSyncResult(1, "PARTIAL", "INCOMPLETE", processing=True)
        elif session_id == 2:
            item = SessionSyncResult(2, "FAILED", "INCOMPLETE")
        else:
            item = SessionSyncResult(3, "SUCCESS", "READY")
        return SyncRunResult(session_id, "partial", (item,), "REST")

    monkeypatch.setattr("pas_connect.daily_sync.run_rest_sync", fake_run)
    result = run_daily_sync(rest, db, today=TODAY, now=NOW)
    assert len(auth_calls) == 1
    assert [call[2] for call in calls] == [1, 3, 2]
    assert all(call[:2] == (543, "2026/2027") and call[3] is state for call in calls)
    assert result.ready_published == 1
    assert result.deferred_202 == 1
    assert result.errors == 1


def test_dashboard_contract_remains_structural_and_selection_is_not_implicit(tmp_path):
    db = database(tmp_path)
    with db.connect() as connection:
        for session_id, name in ((10, "FULL TRAINING"), (11, "EXERCISE")):
            connection.execute(
                "insert into gpexe_team_sessions(provider_session_id,team_id,session_name,"
                "start_timestamp,synced_at,raw_json) values(?,?,?,?,?,?)",
                (session_id, 543, name, "2026-08-20", "now", "{}"),
            )
            connection.execute(
                "insert or ignore into gpexe_athletes(provider_player_id,player_name,synced_at,raw_json) "
                "values(?,?,?,?)", (session_id, f"Athlete {session_id}", "now", "{}"),
            )
            connection.execute(
                "insert into gpexe_athlete_team_memberships(provider_player_id,team_id,season,"
                "first_seen_at,last_seen_at,raw_json) values(?,?,?,?,?,?)",
                (session_id, 543, DAILY_SEASON, "now", "now", "{}"),
            )
            linked, drill = (10, None) if session_id == 10 else (99, 6)
            connection.execute(
                "insert into gpexe_athlete_session_details(provider_athlete_session_id,"
                "provider_session_id,provider_player_id,drill_id,track_id,metrics_json,"
                "zones_json,synced_at,raw_json) values(?,?,?,?,?,?,?,?,?)",
                (100 + session_id, session_id, session_id, drill, str(200 + session_id),
                 "{}", "{}", "now",
                 json.dumps({"payload": {"teamsession": linked, "drill": drill}})),
            )
            connection.execute(
                "insert into gpexe_athlete_session_kpis(provider_athlete_session_id,source,"
                "position,name,value,raw_json) values(?,?,?,?,?,?)",
                (100 + session_id, "rest_v2", 0, "distance", "1000", "{}"),
            )
        connection.commit()
    dashboard = available_sessions(
        db.path, team_id=543, season=DAILY_SEASON,
        ready_only=True, dashboard_only=True,
    )
    assert [item["provider_session_id"] for item in dashboard] == [10]
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Sincronizza nuove sessioni" in source
    assert "run_daily_sync(" in source
    assert 'pas_gpexe_active_session_ids"] = []' in source
    daily_block = source.split('st.markdown("##### Daily Sync GPExe")', 1)[1].split(
        'st.markdown("##### Sincronizzazione completa")', 1,
    )[0]
    assert 'pas_gpexe_active_session_ids"] =' not in daily_block


def test_schema_and_excel_contract_are_unchanged():
    assert SCHEMA_VERSION == 12
    excel = ROOT / "Database Hellas 25-26.xlsx"
    assert hashlib.sha256(excel.read_bytes()).hexdigest().upper() == (
        "9EFA8E9CCFCB6BCFF55B5F73407FC1B9E449C3A0633EE8F5A525D5A72D63010B"
    )
