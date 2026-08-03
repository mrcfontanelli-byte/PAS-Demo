from pathlib import Path
import sqlite3

from pas_connect.database import PASConnectDatabase


def _snapshot(player_name="John Doe"):
    return {
        "schema_version": 1,
        "provider": "gpexe",
        "synced_at": "2026-08-03T12:00:00+00:00",
        "resources": {
            "teams": [{
                "provider": "gpexe", "provider_team_id": 1,
                "team_name": "FIRST TEAM", "club_id": 1,
                "season": "2025-2026", "sport": "FOOTBALL",
                "start_date": "2025-07-01", "end_date": "2026-06-30",
                "locked": False, "updated_at": None,
            }],
            "categories": [{
                "provider": "gpexe", "provider_category_id": 2,
                "category_name": "FULL TRAINING", "team_id": 1,
                "provider_color": "#fff",
            }],
            "tags": [{
                "provider": "gpexe", "provider_tag_id": 3,
                "tag_name": "ENDURANCE", "team_id": 1,
            }],
            "athletes": [{
                "provider": "gpexe", "provider_player_id": 4,
                "external_player_id": "JD001", "first_name": "John",
                "last_name": "Doe", "player_name": player_name,
                "short_name": "J. Doe", "birth_date": "1995-03-15",
                "club_id": 1, "photo_url": None, "v0": 25.8, "a0": 8.2,
            }],
        },
    }


def test_reference_database_creates_tables_and_upserts(tmp_path):
    db = PASConnectDatabase(tmp_path / "pas_connect.sqlite3")
    result = db.replace_reference_data(_snapshot())
    assert result.counts == {"teams": 1, "categories": 1, "tags": 1, "athletes": 1}
    assert db.counts() == result.counts

    db.replace_reference_data(_snapshot("John Updated"))
    assert db.counts() == result.counts
    with sqlite3.connect(db.path) as connection:
        name = connection.execute(
            "SELECT player_name FROM gpexe_athletes WHERE provider_player_id=4"
        ).fetchone()[0]
        run_count = connection.execute("SELECT COUNT(*) FROM gpexe_sync_runs").fetchone()[0]
    assert name == "John Updated"
    assert run_count == 2
    assert db.last_successful_sync()["status"] == "success"


def test_release_uses_separate_pas_connect_database():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "PASConnectDatabase.default().replace_reference_data(snapshot)" in app
    assert "Il database Excel e le analisi del PAS restano invariati" in app
    assert "Streamlit Cloud: il database locale" in app
