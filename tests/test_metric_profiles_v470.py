from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from modules.bridge_validation import compare_distance_sources, compare_metric_profiles
from modules.data_provider import get_data_provider, resolve_data_provider
from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.metric_profiles import format_metric_threshold, normalize_metric_profile


def _profile(**overrides):
    profile = {
        "team_id": "10", "team_name": "Team A", "season": "2026-2027",
        "canonical_metric": "High Speed Running", "provider_metric_name": "Speed Zone",
        "threshold_min": 25.2, "threshold_max": None,
        "threshold_min_inclusive": False, "threshold_max_inclusive": False,
        "threshold_unit": "km/h", "source": "GPExe",
        "valid_from": "2026-07-01", "valid_to": "2027-06-30",
        "verified": True, "notes": "Verificato sul provider",
    }
    profile.update(overrides)
    return profile


def test_schema_7_migration_is_additive_and_preserves_existing_data(tmp_path):
    path = tmp_path / "pas_connect.sqlite3"
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE legacy_data(id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO legacy_data VALUES(1, 'preserved')")
    database = PASConnectDatabase(path)
    database.initialize()
    with database.connect() as connection:
        assert SCHEMA_VERSION == 7
        assert connection.execute("SELECT value FROM legacy_data WHERE id=1").fetchone()[0] == "preserved"
        assert connection.execute(
            "SELECT value FROM pas_connect_meta WHERE key='schema_version'"
        ).fetchone()[0] == "7"
        columns = {row[1] for row in connection.execute("PRAGMA table_info(pas_metric_profiles)")}
    assert {
        "id", "team_id", "team_name", "season", "canonical_metric", "provider_metric_name",
        "threshold_min", "threshold_max", "threshold_min_inclusive", "threshold_max_inclusive",
        "threshold_unit", "source", "valid_from", "valid_to", "verified", "notes",
        "created_at", "updated_at",
    } <= columns


def test_profile_creation_and_upsert_update(tmp_path):
    database = PASConnectDatabase(tmp_path / "profiles.sqlite3")
    profile_id, inserted = database.upsert_metric_profile(_profile())
    assert inserted is True
    original = database.list_metric_profiles(team_id="10")[0]
    same_id, inserted = database.upsert_metric_profile(
        _profile(id=profile_id, notes="Aggiornato", threshold_min=24.5)
    )
    assert (same_id, inserted) == (profile_id, False)
    updated = database.list_metric_profiles(team_id=10)[0]
    assert updated["threshold_min"] == 24.5
    assert updated["notes"] == "Aggiornato"
    assert updated["created_at"] == original["created_at"]
    assert len(database.list_metric_profiles()) == 1


def test_new_profiles_with_different_thresholds_remain_distinct(tmp_path):
    database = PASConnectDatabase(tmp_path / "profiles.sqlite3")
    first_id, first_inserted = database.upsert_metric_profile(_profile())
    second_id, second_inserted = database.upsert_metric_profile(_profile(
        threshold_min=19.8, threshold_max=25.2,
        threshold_min_inclusive=True, threshold_max_inclusive=False,
    ))
    assert first_inserted and second_inserted
    assert first_id != second_id
    assert len(database.list_metric_profiles(team_id="10")) == 2


def test_profiles_keep_teams_seasons_and_validity_periods_separate(tmp_path):
    database = PASConnectDatabase(tmp_path / "profiles.sqlite3")
    database.upsert_metric_profile(_profile())
    database.upsert_metric_profile(_profile(team_id="20", team_name="Team B"))
    database.upsert_metric_profile(_profile(season="2027-2028", valid_from="2027-07-01", valid_to="2028-06-30"))
    database.upsert_metric_profile(_profile(valid_from="2026-01-01", valid_to="2026-06-30"))
    assert len(database.list_metric_profiles()) == 4
    assert len(database.list_metric_profiles(team_id="10")) == 3


def test_open_closed_and_nullable_thresholds_are_supported():
    open_profile = normalize_metric_profile(_profile(threshold_min=25.2, threshold_max=None))
    interval = normalize_metric_profile(_profile(
        threshold_min=19.8, threshold_max=25.2,
        threshold_min_inclusive=True, threshold_max_inclusive=False,
    ))
    no_minimum = normalize_metric_profile(_profile(threshold_min=None, threshold_max=19.8))
    assert format_metric_threshold(open_profile) == ">25.2 km/h"
    assert format_metric_threshold(interval) == "[19.8–25.2) km/h"
    assert format_metric_threshold(no_minimum) == "<19.8 km/h"


def test_equal_verified_profiles_are_comparable_for_applicable_period():
    left = normalize_metric_profile(_profile())
    right = normalize_metric_profile(_profile(source="Excel"))
    result = compare_metric_profiles(left, right, applicable_date="2026-09-01")
    assert result.status == "CONFRONTABILE"


def test_different_threshold_unit_inclusivity_or_period_is_not_comparable():
    base = normalize_metric_profile(_profile())
    variants = [
        _profile(threshold_unit="m/s"), _profile(threshold_min=24.0),
        _profile(threshold_min_inclusive=True),
        _profile(valid_from="2026-08-01"),
    ]
    for variant in variants:
        result = compare_metric_profiles(base, normalize_metric_profile(variant))
        assert result.status == "NON CONFRONTABILE"
        assert "Nessuna differenza numerica" in result.explanation
    outside = compare_metric_profiles(base, base, applicable_date="2028-01-01")
    assert outside.status == "NON CONFRONTABILE"


def test_missing_and_unverified_profile_statuses():
    verified = normalize_metric_profile(_profile())
    assert compare_metric_profiles(verified, None).status == "CONFIGURAZIONE MANCANTE"
    unverified = normalize_metric_profile(_profile(verified=False))
    assert compare_metric_profiles(verified, unverified).status == "CONFIGURAZIONE NON VERIFICATA"


def test_distance_validation_and_excel_default_do_not_regress():
    excel = pd.DataFrame({"Date": ["2026-08-01"], "Athlete": ["A"], "Distance (m)": [1000.0]})
    gpexe = pd.DataFrame({"Date": ["2026-08-01"], "Athlete": ["A"], "Distance (m)": [1000.0]})
    result = compare_distance_sources(excel, gpexe)
    assert result.summary == {
        "sedute_confrontate": 1, "atleti_confrontati": 1,
        "atleti_coincidenti": 1, "atleti_differenti": 0,
    }
    assert resolve_data_provider(None).effective.provider_id == "excel"
    assert get_data_provider("excel").provider_id == "excel"


def test_ui_has_explicit_metric_profile_configuration_without_example_team_hardcodes():
    root = Path(__file__).parents[1]
    source = "\n".join([
        (root / "app.py").read_text(encoding="utf-8"),
        (root / "pas_connect" / "database.py").read_text(encoding="utf-8"),
        (root / "pas_connect" / "metric_profiles.py").read_text(encoding="utf-8"),
    ])
    assert "Configurazione metriche Team" in source
    assert "Salva profilo metrico" in source
    assert "Hellas 2025-2026" not in source
    assert "Serie B 2026-2027" not in source
    assert "Distance" not in (root / "pas_connect" / "metric_profiles.py").read_text(encoding="utf-8")
