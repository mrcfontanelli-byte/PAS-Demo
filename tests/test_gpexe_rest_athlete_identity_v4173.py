from __future__ import annotations

import json

from pas_connect import GPExeConfig, GPExeRESTClient
from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.rest_mapper import (
    index_rest_athlete_identities,
    map_rest_athlete_identity,
)
from pas_connect.rest_persistence import GPExeRESTIdentityPersistence, GPExeRESTPersistenceGate
from pas_connect.rest_service import GPExeRESTService, RESTBundleResult
from pas_connect.sync import SyncRequest, run_rest_identity_sync, run_rest_sync


def _json(payload: object) -> bytes:
    return json.dumps(payload).encode("utf-8")


def _identity(athlete_id: int, suffix: str = "ONE") -> dict[str, object]:
    return {
        "id": athlete_id,
        "first_name": f"FIRST_{suffix}",
        "last_name": f"LAST_{suffix}",
        "short_name": f"SHORT_{suffix}",
        "name": f"DISPLAY_{suffix}",
    }


def _ready(
    session_id: int,
    athlete_id: int,
    athlete_session_id: int,
) -> RESTBundleResult:
    detail = {
        "provider_athlete_session_id": athlete_session_id,
        "provider_session_id": session_id,
        "athlete": {"provider_player_id": athlete_id},
        "track": {"provider_track_id": str(athlete_session_id + 1000)},
        "state": "READY",
        "starter": False,
        "is_stats_valid": True,
        "total_time": 60,
        "kpis": [{
            "provider_name": "distance",
            "canonical_metric": "Distance",
            "value": 100.0,
            "unit": "m",
            "active": True,
            "provenance": "rest_detail",
            "raw": {},
        }],
        "zones": {"speed_zones": []},
        "raw": {"id": athlete_session_id},
        "provenance": "rest_detail",
    }
    return RESTBundleResult("READY", False, {
        "provider_contract": "rest_v2",
        "provider_session_id": session_id,
        "team_session": {
            "provider_session_id": session_id,
            "team_id": 543,
            "category": {"id": 1, "name": "TRAINING"},
            "nature": "training",
            "start_timestamp": "2026-08-01T10:00:00Z",
            "total_time": 60,
            "is_stats_valid": True,
            "drill": {},
            "raw": {"id": session_id},
        },
        "athlete_session_ids": (athlete_session_id,),
        "athlete_sessions": (detail,),
    }, ())


class _RunClient:
    def __init__(self, roster: object, details: dict[int, object] | None = None):
        self.roster = roster
        self.details = details or {}
        self.roster_calls = 0
        self.detail_calls: list[int] = []

    def athletes(self):
        self.roster_calls += 1
        if isinstance(self.roster, Exception):
            raise self.roster
        return self.roster

    def athlete(self, athlete_id: int):
        self.detail_calls.append(athlete_id)
        result = self.details.get(athlete_id, RuntimeError("detail unavailable"))
        if isinstance(result, Exception):
            raise result
        return result

    @staticmethod
    def redact(value):
        return str(value).replace("PRIVATE", "[redacted]")


def _service(client: _RunClient, bundles: dict[int, RESTBundleResult]):
    service = GPExeRESTService(client)
    service.build_team_session_bundle = lambda session_id, **_: bundles[session_id]
    return service


def _request(*session_ids: int) -> SyncRequest:
    return SyncRequest(
        543,
        "2026/2027",
        selected_session_ids=session_ids,
        force_refresh=True,
        transport="REST",
    )


def test_rest_client_exposes_read_only_bulk_athletes_endpoint():
    calls = []

    def transport(request, *_):
        calls.append(request)
        return 200, _json([_identity(1)]), {}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="safe-token"),
        transport=transport,
    )
    assert len(client.athletes()) == 1
    assert len(calls) == 1
    assert calls[0].get_method() == "GET"
    assert calls[0].full_url == "https://example.test/rest/v2/athlete/"


def test_rest_client_exposes_read_only_athlete_detail_endpoint():
    calls = []

    def transport(request, *_):
        calls.append(request)
        return 200, _json(_identity(7)), {}

    client = GPExeRESTClient(
        GPExeConfig(base_url="https://example.test", token="safe-token"),
        transport=transport,
    )
    assert client.athlete(7)["id"] == 7
    assert len(calls) == 1
    assert calls[0].get_method() == "GET"
    assert calls[0].full_url == "https://example.test/rest/v2/athlete/7/"


def test_roster_mapper_normalizes_empty_values_and_derives_player_name():
    mapped = map_rest_athlete_identity({
        "id": 7,
        "first_name": " FIRST ",
        "last_name": "LAST",
        "short_name": " ",
        "name": "",
    })
    assert mapped["first_name"] == "FIRST"
    assert mapped["last_name"] == "LAST"
    assert mapped["short_name"] is None
    assert mapped["provider_name"] is None
    assert mapped["player_name"] == "FIRST LAST"
    assert mapped["identity_source"] == "rest_v2"


def test_100_roster_rows_are_indexed_and_duplicate_ids_are_merged():
    roster = [_identity(index, str(index)) for index in range(1, 101)]
    roster.append({
        "id": 1,
        "first_name": None,
        "last_name": "LAST_UPDATED",
        "short_name": None,
        "name": None,
    })
    indexed = index_rest_athlete_identities(roster)
    assert len(indexed) == 100
    assert indexed[1]["first_name"] == "FIRST_1"
    assert indexed[1]["last_name"] == "LAST_UPDATED"
    assert indexed[1]["player_name"] == "DISPLAY_1"


def test_roster_is_fetched_once_and_reused_across_team_sessions(tmp_path):
    client = _RunClient([_identity(70)])
    service = _service(client, {
        1: _ready(1, 70, 101),
        2: _ready(2, 70, 102),
    })
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(service, db, _request(1, 2))
    assert client.roster_calls == 1
    assert [row.status for row in result.sessions] == ["SUCCESS", "SUCCESS"]
    with db.connect() as connection:
        athlete = connection.execute(
            "SELECT first_name,last_name,short_name,player_name FROM gpexe_athletes"
        ).fetchone()
        sessions = connection.execute(
            "SELECT COUNT(*) FROM gpexe_athlete_session_details"
        ).fetchone()[0]
    assert tuple(athlete) == ("FIRST_ONE", "LAST_ONE", "SHORT_ONE", "DISPLAY_ONE")
    assert sessions == 2


def test_identity_only_persistence_changes_only_athletes(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    db.initialize()
    protected = (
        "gpexe_team_sessions", "gpexe_athlete_session_details", "gpexe_tracks",
        "gpexe_athlete_session_kpis",
    )
    with db.connect() as connection:
        before = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in protected
        }
    result = GPExeRESTIdentityPersistence(db).persist(
        index_rest_athlete_identities([_identity(70)])
    )
    with db.connect() as connection:
        after = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in protected
        }
        athletes = connection.execute("SELECT COUNT(*) FROM gpexe_athletes").fetchone()[0]
    assert (result.inserted, result.updated, athletes) == (1, 0, 1)
    assert after == before


def test_processing_team_session_still_persists_roster_identity_only(tmp_path):
    client = _RunClient([_identity(70)])
    processing = RESTBundleResult("INCOMPLETE", True, None, ())
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(_service(client, {1: processing}), db, _request(1))
    assert result.sessions[0].processing is True
    with db.connect() as connection:
        counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "gpexe_athletes", "gpexe_team_sessions",
                "gpexe_athlete_session_details", "gpexe_tracks",
                "gpexe_athlete_session_kpis",
            )
        }
    assert counts == {
        "gpexe_athletes": 1, "gpexe_team_sessions": 0,
        "gpexe_athlete_session_details": 0, "gpexe_tracks": 0,
        "gpexe_athlete_session_kpis": 0,
    }


def test_roster_subset_uses_one_detail_per_missing_unique_athlete(tmp_path):
    client = _RunClient([_identity(70)], {71: _identity(71, "DETAIL")})
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(
        _service(client, {1: _ready(1, 71, 101), 2: _ready(2, 71, 102)}),
        db,
        _request(1, 2),
    )
    assert [row.status for row in result.sessions] == ["SUCCESS", "SUCCESS"]
    assert client.roster_calls == 1
    assert client.detail_calls == [71]
    with db.connect() as connection:
        row = connection.execute(
            "SELECT first_name,player_name,raw_json FROM gpexe_athletes "
            "WHERE provider_player_id=71"
        ).fetchone()
    assert tuple(row[:2]) == ("FIRST_DETAIL", "DISPLAY_DETAIL")
    raw = json.loads(row[2])
    assert set(raw["identity_sources"]) == {"rest_v2"}


def test_existing_real_identity_skips_detail_lookup(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    GPExeRESTIdentityPersistence(db).persist(
        index_rest_athlete_identities([_identity(71, "LOCAL")])
    )
    client = _RunClient([])
    state = run_rest_identity_sync(client, db, {71})
    assert state.detail_failures == 0
    assert client.roster_calls == 1
    assert client.detail_calls == []


def test_detail_failure_is_private_non_blocking_and_not_retried(tmp_path):
    client = _RunClient([], {71: RuntimeError("PRIVATE athlete payload")})
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(
        _service(client, {1: _ready(1, 71, 101), 2: _ready(2, 71, 102)}),
        db,
        _request(1, 2),
    )
    assert [row.status for row in result.sessions] == ["SUCCESS", "SUCCESS"]
    assert client.detail_calls == [71]
    assert "PRIVATE" not in json.dumps(result, default=lambda item: item.__dict__)
    with db.connect() as connection:
        player_name = connection.execute(
            "SELECT player_name FROM gpexe_athletes WHERE provider_player_id=71"
        ).fetchone()[0]
    assert player_name == "GPExe Athlete 71"


def test_roster_failure_does_not_block_sync_or_repeat_lookup(tmp_path):
    client = _RunClient(RuntimeError("PRIVATE roster failure"))
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    result = run_rest_sync(
        _service(client, {1: _ready(1, 70, 101), 2: _ready(2, 70, 102)}),
        db,
        _request(1, 2),
    )
    assert client.roster_calls == 1
    assert [row.status for row in result.sessions] == ["SUCCESS", "SUCCESS"]
    assert "PRIVATE" not in json.dumps([row.diagnostics for row in result.sessions])
    with db.connect() as connection:
        player_name = connection.execute(
            "SELECT player_name FROM gpexe_athletes"
        ).fetchone()[0]
    assert player_name == "GPExe Athlete 70"


def test_cross_source_identity_merge_never_downgrades_real_names(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    gate = GPExeRESTPersistenceGate(db)
    rest_identity = index_rest_athlete_identities([_identity(70)])[70]
    gate.publish(
        _ready(1, 70, 101),
        season="2026/2027",
        identity_index={70: rest_identity},
    )
    db.upsert_graphql_athletes([{
        "provider_player_id": 70,
        "first_name": None,
        "last_name": "",
        "short_name": None,
        "player_name": "GPExe Athlete 70",
        "raw": {"provider": "graphql"},
    }])
    with db.connect() as connection:
        row = connection.execute(
            "SELECT first_name,last_name,short_name,player_name,raw_json "
            "FROM gpexe_athletes WHERE provider_player_id=70"
        ).fetchone()
    assert tuple(row[:4]) == ("FIRST_ONE", "LAST_ONE", "SHORT_ONE", "DISPLAY_ONE")
    raw = json.loads(row[4])
    assert set(raw["identity_sources"]) == {"rest_v2", "graphql"}
    assert raw["identity_provenance"] == ["graphql", "rest_v2"]


def test_partial_real_updates_complete_existing_and_raw_is_bounded(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas.sqlite3")
    db.upsert_graphql_athletes([{
        "provider_player_id": 70,
        "first_name": "OLD_FIRST",
        "last_name": "OLD_LAST",
        "short_name": "OLD_SHORT",
        "player_name": "OLD_DISPLAY",
        "raw": {"version": 1},
    }])
    gate = GPExeRESTPersistenceGate(db)
    partial = map_rest_athlete_identity({
        "id": 70,
        "first_name": "NEW_FIRST",
        "last_name": None,
        "short_name": "",
        "name": "NEW_DISPLAY",
    })
    for session_id in (1, 2):
        gate.publish(
            _ready(session_id, 70, 100 + session_id),
            season="2026/2027",
            identity_index={70: partial},
        )
    with db.connect() as connection:
        row = connection.execute(
            "SELECT first_name,last_name,short_name,player_name,raw_json "
            "FROM gpexe_athletes WHERE provider_player_id=70"
        ).fetchone()
        schema = connection.execute(
            "SELECT value FROM pas_connect_meta WHERE key='schema_version'"
        ).fetchone()[0]
    assert tuple(row[:4]) == ("NEW_FIRST", "OLD_LAST", "OLD_SHORT", "NEW_DISPLAY")
    raw = json.loads(row[4])
    assert set(raw["identity_sources"]) == {"graphql", "rest_v2"}
    assert len(raw["identity_sources"]) == 2
    assert schema == "12"
    assert SCHEMA_VERSION == 12
