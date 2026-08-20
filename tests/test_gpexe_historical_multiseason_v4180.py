from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.historical_sync import (
    HistoricalSyncAction,
    HistoricalSyncPlanItem,
    REST_RATE_LIMIT_PER_MINUTE,
    SESSION_CONCURRENCY,
    TEAM_SESSION_LIST_PAGE_SIZE,
    persist_rest_team_references,
    plan_historical_sync,
    run_historical_performance_batch,
    select_historical_batch,
    speed_profile_state,
    sync_historical_team_session_catalog,
)
from pas_connect.sync import RESTIdentitySyncResult, SessionSyncResult, SyncRunResult
from pas_connect.pas_bridge import (
    available_contexts, available_sessions, format_gpexe_context_label,
)


ROOT = Path(__file__).parents[1]


class _TeamClient:
    def teams(self):
        return [
            {"id": 443, "name": "SERIE A", "season": "2024-2025", "club": 1},
            {"id": 469, "name": "SERIE A", "season": "2025/2026", "club": 1},
            {"id": 543, "name": "SERIE B", "season": "2026/2027", "club": 1},
            {"id": 545, "name": "GK", "season": "2026/2027", "club": 1},
        ]


class _CatalogClient:
    def __init__(self):
        self.calls = []

    def _request(self, endpoint, *, query):
        self.calls.append((endpoint.path, dict(query)))
        if query["page"] == 1:
            return [
                {"id": 100, "team": 443, "name": "A", "start_timestamp": "2024-11-15"},
                {"id": 100, "team": 443, "name": "A duplicate", "start_timestamp": "2024-11-15"},
                {"id": 200, "team": 999, "name": "Other", "start_timestamp": "2024-11-15"},
            ]
        return []


def _database(tmp_path: Path) -> PASConnectDatabase:
    database = PASConnectDatabase(tmp_path / "pas.sqlite3")
    database.initialize()
    return database


def _insert_usable_session(
    database: PASConnectDatabase,
    *,
    team_id: int,
    season: str,
    session_id: int,
    session_date: str,
    athlete_session_id: int,
    athlete_id: int,
) -> None:
    with database.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_team_sessions(
            provider_session_id,team_id,session_name,start_timestamp,synced_at,raw_json)
            VALUES(?,?,?,?,?,?)""",
            (session_id, team_id, "FULL TRAINING", session_date, "now", "{}"),
        )
        connection.execute(
            """INSERT INTO gpexe_athletes(
            provider_player_id,player_name,synced_at,raw_json)
            VALUES(?,?,?,?)""",
            (athlete_id, f"GPExe Athlete {athlete_id}", "now", "{}"),
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_team_memberships(
            provider_player_id,team_id,season,first_seen_at,last_seen_at,raw_json)
            VALUES(?,?,?,?,?,?)""",
            (athlete_id, team_id, season, "now", "now", "{}"),
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_details(
            provider_athlete_session_id,provider_session_id,provider_player_id,
            track_id,metrics_json,zones_json,synced_at,raw_json)
            VALUES(?,?,?,?,?,?,?,?)""",
            (athlete_session_id, session_id, athlete_id, athlete_session_id + 1000,
             "{}", "{}", "now", "{}"),
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,raw_json)
            VALUES(?,?,?,?,?,?)""",
            (athlete_session_id, "rest_v2", 0, "distance", "1234", "{}"),
        )
        connection.commit()


def test_rest_team_reference_upsert_and_no_downgrade(tmp_path):
    database = _database(tmp_path)
    selected = persist_rest_team_references(
        _TeamClient(), database,
        target_contexts=((443, "2024/2025"), (469, "2025/2026"), (543, "2026/2027")),
    )
    assert [(row["provider_team_id"], row["team_name"]) for row in selected] == [
        (443, "SERIE A"), (469, "SERIE A"), (543, "SERIE B")
    ]
    database.upsert_team_references([{
        "provider_team_id": 443, "team_name": "", "season": None,
        "raw": {"id": 443},
    }])
    with database.connect() as connection:
        rows = connection.execute(
            "SELECT provider_team_id,team_name,season,raw_json FROM gpexe_teams ORDER BY provider_team_id"
        ).fetchall()
    assert [tuple(row)[:3] for row in rows] == [
        (443, "SERIE A", "2024/2025"),
        (469, "SERIE A", "2025/2026"),
        (543, "SERIE B", "2026/2027"),
    ]
    assert '"name": "SERIE A"' in rows[0]["raw_json"]
    contexts = available_contexts(database.path)
    assert {(item["team_id"], item["season"], item["team_name"]) for item in contexts} == {
        (443, "2024/2025", "SERIE A"),
        (469, "2025/2026", "SERIE A"),
        (543, "2026/2027", "SERIE B"),
    }


def test_context_label_uses_provider_name_and_keeps_technical_key(tmp_path):
    database = _database(tmp_path)
    database.upsert_team_references([{
        "provider_team_id": 469, "team_name": "SERIE A", "season": "2025/2026",
        "raw": {"id": 469, "name": "SERIE A", "season": "2025/2026"},
    }])
    _insert_usable_session(
        database, team_id=469, season="2025/2026", session_id=121408,
        session_date="2025-08-03", athlete_session_id=1, athlete_id=10,
    )
    contexts = available_contexts(database.path)
    assert [(item["team_id"], item["season"]) for item in contexts] == [(469, "2025/2026")]
    assert contexts[0]["team_name"] == "SERIE A"
    assert format_gpexe_context_label(469, "2025/2026", "SERIE A") == "SERIE A · 2025/2026"
    assert format_gpexe_context_label(999, "2024/2025", None) == "Team 999 · 2024/2025"
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "format_gpexe_context_label(" in app_source
    assert "context_by_key[value].get(\"team_name\")" in app_source


def test_team_469_is_performance_usable_without_sync_history(tmp_path):
    database = _database(tmp_path)
    for offset, session_id in enumerate((121188, 121317, 121408), start=1):
        _insert_usable_session(
            database, team_id=469, season="2025/2026", session_id=session_id,
            session_date=f"2025-08-0{offset}", athlete_session_id=offset, athlete_id=offset,
        )
    inventory = database.historical_session_inventory(team_id=469, season="2025/2026")
    assert [row["team_session_id"] for row in inventory] == [121188, 121317, 121408]
    assert all(row["performance_usable"] == 1 for row in inventory)
    assert all(row["sync_history_ready"] == 0 for row in inventory)
    assert all(row["local_completeness"] == "COMPLETE" for row in inventory)
    assert all(item.action is HistoricalSyncAction.SKIP_COMPLETE
               for item in plan_historical_sync(inventory))


def test_planner_is_idempotent_ordered_and_has_no_executor():
    inventory = [
        {"team_id": 443, "season": "2024/2025", "team_session_id": 5,
         "session_date": "2025-01-02", "locally_present": 0},
        {"team_id": 443, "season": "2024/2025", "team_session_id": 4,
         "session_date": "2025-01-01", "locally_present": 1},
        {"team_id": 443, "season": "2024/2025", "team_session_id": 3,
         "session_date": "2025-01-01", "deferred_202": 1},
        {"team_id": 443, "season": "2024/2025", "team_session_id": 2,
         "session_date": "2025-01-01", "sync_status": "FAILED"},
        {"team_id": 443, "season": "2024/2025", "team_session_id": 1,
         "session_date": "2025-01-01", "performance_usable": 1},
    ]
    first = plan_historical_sync(inventory)
    assert first == plan_historical_sync(inventory)
    assert [item.team_session_id for item in first] == [1, 2, 3, 4, 5]
    assert [item.action for item in first] == [
        HistoricalSyncAction.SKIP_COMPLETE,
        HistoricalSyncAction.RETRY_ERROR_ELIGIBLE,
        HistoricalSyncAction.DEFER_202,
        HistoricalSyncAction.COMPLETE_PARTIAL,
        HistoricalSyncAction.FETCH_NEW,
    ]
    assert REST_RATE_LIMIT_PER_MINUTE == 40
    assert TEAM_SESSION_LIST_PAGE_SIZE == 500
    assert SESSION_CONCURRENCY == 1


def test_team_443_speed_profile_stays_unknown_and_schema_is_12(tmp_path):
    database = _database(tmp_path)
    database.upsert_team_references([{
        "provider_team_id": 443, "team_name": "SERIE A", "season": "2024/2025",
        "raw": {"id": 443, "name": "SERIE A", "season": "2024/2025"},
    }])
    assert speed_profile_state(database, team_id=443, season="2024/2025") == "UNKNOWN"
    assert SCHEMA_VERSION == 12


def test_catalog_sync_is_scoped_idempotent_and_not_analysis_eligible(tmp_path):
    database = _database(tmp_path)
    database.upsert_team_references([{
        "provider_team_id": 443, "team_name": "SERIE A", "season": "2024/2025",
        "raw": {"id": 443, "name": "SERIE A", "season": "2024/2025"},
    }])
    client = _CatalogClient()
    first = sync_historical_team_session_catalog(
        client, database,
        contexts={443: "2024/2025"}, expected_counts={443: 1},
    )
    assert first.pages_fetched == 1
    assert first.unique_remote_sessions == 1
    assert first.inserted == 1 and first.updated == 0
    assert client.calls == [(
        "/rest/v2/session/team/", {"page": 1, "page_size": 500, "limit": 500}
    )]
    assert available_sessions(
        database.path, team_id=443, season="2024/2025", ready_only=True,
    ) == []
    inventory = database.historical_session_inventory(team_id=443, season="2024/2025")
    assert inventory[0]["remote_discovered"] == 1
    assert inventory[0]["locally_present"] == 0
    assert inventory[0]["performance_usable"] == 0
    assert plan_historical_sync(inventory)[0].action is HistoricalSyncAction.FETCH_NEW

    second = sync_historical_team_session_catalog(
        _CatalogClient(), database,
        contexts={443: "2024/2025"}, expected_counts={443: 1},
    )
    assert second.inserted == 0 and second.updated == 1
    with database.connect() as connection:
        assert connection.execute(
            "SELECT COUNT(*) FROM gpexe_team_sessions WHERE team_id=443"
        ).fetchone()[0] == 1


def test_batch_selection_enforces_priority_isolation_and_25_plus_25_budget():
    def items(team, season, action, start, count):
        return [HistoricalSyncPlanItem(
            team, season, start + offset, f"2025-01-{offset + 1:02d}", action,
        ) for offset in range(count)]

    plans = {
        (443, "2024/2025"): items(443, "2024/2025", HistoricalSyncAction.FETCH_NEW, 1, 5),
        (543, "2026/2027"): (
            items(543, "2026/2027", HistoricalSyncAction.FETCH_NEW, 100, 30)
            + items(543, "2026/2027", HistoricalSyncAction.DEFER_202, 90, 1)
            + items(543, "2026/2027", HistoricalSyncAction.SKIP_COMPLETE, 80, 1)
        ),
        (469, "2025/2026"): items(469, "2025/2026", HistoricalSyncAction.FETCH_NEW, 200, 30),
    }
    selected = select_historical_batch(
        plans,
        context_order=((543, "2026/2027"), (469, "2025/2026")),
    )
    assert len(selected) == 50
    assert sum(item.team_id == 543 for item in selected) == 25
    assert sum(item.team_id == 469 for item in selected) == 25
    assert all(item.team_id != 443 for item in selected)
    assert all(item.action is not HistoricalSyncAction.SKIP_COMPLETE for item in selected)
    assert selected[0].action is HistoricalSyncAction.DEFER_202


def test_deferred_batch_orders_oldest_attempt_then_date_and_id():
    plans = {(543, "2026/2027"): (
        HistoricalSyncPlanItem(543, "2026/2027", 3, "2026-07-10",
                               HistoricalSyncAction.DEFER_202, "2026-08-14T12:00:00Z"),
        HistoricalSyncPlanItem(543, "2026/2027", 2, "2026-07-11",
                               HistoricalSyncAction.DEFER_202, "2026-08-13T12:00:00Z"),
        HistoricalSyncPlanItem(543, "2026/2027", 1, "2026-07-10",
                               HistoricalSyncAction.DEFER_202, "2026-08-13T12:00:00Z"),
    )}
    selected = select_historical_batch(
        plans, context_order=((543, "2026/2027"),),
    )
    assert [item.team_session_id for item in selected] == [1, 2, 3]


def test_non_processing_partial_remains_resume_eligible_not_fetch_new():
    plan = plan_historical_sync([{
        "team_id": 543, "season": "2026/2027", "team_session_id": 10,
        "session_date": "2026-07-11", "sync_status": "PARTIAL",
        "locally_present": 0, "deferred_202": 0,
    }])
    assert plan[0].action is HistoricalSyncAction.COMPLETE_PARTIAL


def test_batch_executor_reuses_identity_state_and_continues_after_202(monkeypatch, tmp_path):
    database = _database(tmp_path)
    state = RESTIdentitySyncResult({}, set())
    calls = []
    monkeypatch.setattr(
        "pas_connect.historical_sync.run_rest_identity_sync",
        lambda client, db, ids: state,
    )

    def fake_run(service, db, request, *, identity_state):
        calls.append((request.team_id, request.selected_session_ids[0], identity_state))
        sid = request.selected_session_ids[0]
        processing = sid == 1
        row = SessionSyncResult(
            sid, "PARTIAL" if processing else "SUCCESS",
            "INCOMPLETE" if processing else "READY", processing=processing,
        )
        return SyncRunResult(sid, "partial" if processing else "success", (row,), "REST")

    monkeypatch.setattr("pas_connect.historical_sync.run_rest_sync", fake_run)
    plans = (
        HistoricalSyncPlanItem(543, "2026/2027", 1, "2026-01-01", HistoricalSyncAction.DEFER_202),
        HistoricalSyncPlanItem(469, "2025/2026", 2, "2025-01-01", HistoricalSyncAction.FETCH_NEW),
        HistoricalSyncPlanItem(443, "2024/2025", 3, "2024-01-01", HistoricalSyncAction.SKIP_COMPLETE),
    )
    result = run_historical_performance_batch(
        SimpleNamespace(client=object()), database, plans,
    )
    assert [(row.plan.team_id, row.result.processing) for row in result.attempts] == [
        (543, True), (469, False),
    ]
    assert len(calls) == 2 and all(call[2] is state for call in calls)
