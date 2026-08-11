from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pandas as pd

from modules.bridge_validation import compare_distance_sources
from modules.data_provider import resolve_data_provider
from pas_connect.database import PASConnectDatabase, SCHEMA_VERSION
from pas_connect.metric_catalog import (
    CONTEXTUAL_FIELDS,
    PROVIDER_REGISTRY,
    catalog_preview_from_csv,
    planned_provider_entries,
    read_csv_headers,
    split_metric_name_unit,
)


HEADERS = [
    "start date/time", "category", "tags", "notes", "match cycle", "last match label",
    "next match label", "last match", "next match", "type", "athlete", "starter", "role",
    "duration (mm:ss)", "distance (m)", "avg speed (m/min)", "distance/speed Z3 (m)",
    "distance/speed Z4 (m)", "speed events", "distance/%speed Z2 (m)",
    "distance/%speed Z3 (m)", "distance/%speed Z4 (m)", "%speed events",
    "max speed (km/h)", "acc events", "dec events", "distance/acc Z2 (m)",
    "distance/dec Z2 (m)", "max acc (m/s²)", "avg MP (W/kg)", "energy (J/kg)",
    "distance/met power Z2+ (m)", "distance/met power Z2 (m)",
    "distance/met power Z3 (m)", "distance/met power Z4 (m)", "met power events",
    "MPE avg time (s)", "MPE avg met power (W/kg)", "MPE rec avg time (s)",
    "MPE rec avg met power (W/kg)", "high ext workᐩ (J/kg)", "high ext workᐨ (J/kg)",
    "bursts", "brakes", "walk distance (m)", "walk time (mm:ss)", "run distance (m)",
    "run time (mm:ss)", "time/HR Z2 (mm:ss)", "time/HR Z3 (mm:ss)",
]
CSV_NAME = "session_20260804-1734_full_training_20260522-1519.csv"


class HeaderOnlyProbe(BytesIO):
    name = CSV_NAME

    def __init__(self):
        header = (";".join(HEADERS) + "\n").encode("utf-8")
        super().__init__(header + (b"DATA_MUST_NOT_BE_READ\n" * 32))
        self.readline_calls = 0

    def readline(self, *args, **kwargs):
        self.readline_calls += 1
        if self.readline_calls > 1:
            raise AssertionError("Il parser ha tentato di leggere una riga dati.")
        return super().readline(*args, **kwargs)

    def read(self, *args, **kwargs):
        raise AssertionError("Il parser deve usare esclusivamente la prima riga.")


def _preview():
    return catalog_preview_from_csv(HeaderOnlyProbe())


def _by_provider_name(preview):
    return {row["provider_metric_name"]: row for row in preview}


def test_csv_parser_reads_only_headers_and_recognizes_real_structure():
    source = HeaderOnlyProbe()
    headers, source_name = read_csv_headers(source)
    assert source.readline_calls == 1
    assert source_name == CSV_NAME
    assert headers == HEADERS
    assert len(headers) == 50


def test_preview_distinguishes_13_contextual_and_37_performance_fields():
    preview = _preview()
    contextual = [row for row in preview if row["is_contextual"]]
    performance = [row for row in preview if not row["is_contextual"]]
    assert len(preview) == 50
    assert len(contextual) == 13
    assert len(performance) == 37
    assert {row["provider_metric_name"] for row in contextual} == CONTEXTUAL_FIELDS
    assert all(row["metric_type"] == "contextual" and not row["active"] for row in contextual)
    assert all(row["source_template"] == CSV_NAME for row in preview)


def test_units_are_extracted_from_real_headers():
    expected = {
        "distance (m)": ("distance", "m"),
        "max speed (km/h)": ("max speed", "km/h"),
        "avg speed (m/min)": ("avg speed", "m/min"),
        "max acc (m/s²)": ("max acc", "m/s²"),
        "avg MP (W/kg)": ("avg MP", "W/kg"),
        "energy (J/kg)": ("energy", "J/kg"),
        "MPE rec avg time (s)": ("MPE rec avg time", "s"),
        "duration (mm:ss)": ("duration", "mm:ss"),
    }
    for header, parts in expected.items():
        assert split_metric_name_unit(header) == parts


def test_mandatory_metric_classifications_are_conservative():
    rows = _by_provider_name(_preview())
    distance = rows["distance (m)"]
    assert (
        distance["canonical_metric"], distance["category"], distance["metric_type"],
        distance["canonical_unit"], distance["value_type"], distance["requires_profile"],
    ) == ("Distance", "GPS", "direct", "m", "numeric", False)
    for name in ("distance/speed Z3 (m)", "distance/speed Z4 (m)"):
        assert rows[name]["metric_type"] == "threshold_distance"
        assert rows[name]["requires_profile"] is True
        assert rows[name]["canonical_unit"] == "m"
    speed_events = rows["speed events"]
    assert speed_events["metric_type"] == "event_count"
    assert speed_events["value_type"] == "integer"
    assert speed_events["requires_profile"] is True
    assert "threshold" not in speed_events
    max_speed = rows["max speed (km/h)"]
    assert (max_speed["metric_type"], max_speed["canonical_unit"], max_speed["requires_profile"]) == (
        "speed", "km/h", False,
    )
    mpe = rows["MPE rec avg time (s)"]
    assert (
        mpe["canonical_metric"], mpe["category"], mpe["metric_type"],
        mpe["canonical_unit"], mpe["value_type"], mpe["requires_profile"],
    ) == ("MPE Rec Avg Time", "MPE", "duration", "s", "numeric", False)


def test_provider_registry_includes_future_providers_without_connectors():
    assert PROVIDER_REGISTRY["Excel"].acquisition_mode == "EXCEL"
    assert PROVIDER_REGISTRY["GPExe"].acquisition_mode == "GRAPHQL"
    assert PROVIDER_REGISTRY["Firstbeat"].acquisition_mode == "MANUAL"
    assert PROVIDER_REGISTRY["Firstbeat"].implemented is False
    assert PROVIDER_REGISTRY["VALD"].acquisition_mode == "CSV"
    assert PROVIDER_REGISTRY["VALD"].implemented is False
    planned = planned_provider_entries()
    assert {row["canonical_metric"] for row in planned} == {
        "Anaerobic Threshold Zone", "High Intensity Training",
    }
    assert all(
        row["provider"] == "Firstbeat" and row["provider_metric_name"] == "" and not row["active"]
        for row in planned
    )
    assert not any(
        row["provider"] == "GPExe"
        for row in planned
    )


def test_schema_8_catalog_upsert_and_manual_changes_are_preserved(tmp_path):
    database = PASConnectDatabase(tmp_path / "catalog.sqlite3")
    proposal = _by_provider_name(_preview())["distance (m)"]
    catalog_id, inserted = database.upsert_metric_catalog_entry(proposal)
    assert SCHEMA_VERSION == 12
    assert inserted is True
    edited = {**proposal, "id": catalog_id, "display_name": "Distance manuale"}
    same_id, inserted = database.upsert_metric_catalog_entry(edited)
    assert (same_id, inserted) == (catalog_id, False)
    inserted_count, preserved = database.import_metric_catalog_proposals([proposal])
    assert (inserted_count, preserved) == (0, 1)
    stored = database.list_metric_catalog()
    assert len(stored) == 1
    assert stored[0]["display_name"] == "Distance manuale"
    with database.connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(pas_metric_catalog)")}
        assert {
            "id", "canonical_metric", "display_name", "provider", "acquisition_mode",
            "provider_metric_name", "category", "metric_type", "canonical_unit",
            "provider_unit", "value_type", "requires_profile", "active", "description",
            "source_template", "created_at", "updated_at",
        } <= columns


def test_catalog_import_does_not_create_session_or_athlete_rows(tmp_path):
    database = PASConnectDatabase(tmp_path / "catalog.sqlite3")
    inserted, preserved = database.import_metric_catalog_proposals(_preview())
    assert (inserted, preserved) == (50, 0)
    with database.connect() as connection:
        assert connection.execute("SELECT COUNT(*) FROM pas_metric_catalog").fetchone()[0] == 50
        assert connection.execute("SELECT COUNT(*) FROM gpexe_team_sessions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM gpexe_athlete_session_details").fetchone()[0] == 0


def test_profile_catalog_validation_and_orphan_reporting_are_non_destructive(tmp_path):
    database = PASConnectDatabase(tmp_path / "catalog.sqlite3")
    profile = {
        "team_id": "1", "team_name": "Team", "season": "2026-2027",
        "canonical_metric": "Orphan Metric", "provider_metric_name": "provider_name",
        "threshold_min": None, "threshold_max": None,
        "threshold_min_inclusive": False, "threshold_max_inclusive": False,
        "threshold_unit": "m", "source": "GPExe", "valid_from": None, "valid_to": None,
        "verified": True, "notes": None,
    }
    profile_id, _ = database.upsert_metric_profile(profile)
    assert database.metric_profile_catalog_status("Orphan Metric") == "CATALOG_EMPTY"
    database.upsert_metric_catalog_entry(_by_provider_name(_preview())["distance (m)"])
    assert database.metric_profile_catalog_status("Distance") == "VALID"
    assert database.metric_profile_catalog_status("Orphan Metric") == "ORPHAN"
    orphans = database.orphan_metric_profiles()
    assert [row["id"] for row in orphans] == [profile_id]
    assert len(database.list_metric_profiles()) == 1


def test_distance_bridge_and_excel_default_do_not_regress():
    excel = pd.DataFrame({"Date": ["2026-05-22"], "Athlete": ["A"], "Distance (m)": [1000]})
    gpexe = pd.DataFrame({"Date": ["2026-05-22"], "Athlete": ["A"], "Distance (m)": [1000]})
    result = compare_distance_sources(excel, gpexe)
    assert result.summary["atleti_coincidenti"] == 1
    assert resolve_data_provider(None).effective.provider_id == "excel"


def test_catalog_ui_is_isolated_in_pas_connect_and_has_no_absolute_csv_path():
    root = Path(__file__).parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    ui = (root / "pas_connect" / "catalog_ui.py").read_text(encoding="utf-8")
    parser = (root / "pas_connect" / "metric_catalog.py").read_text(encoding="utf-8")
    assert "render_metric_catalog_section(" in app
    assert "pas_connect_database, embedded=True" in app
    assert "Catalogo metriche PAS" in ui
    assert "Salva preview nel catalogo" in ui
    assert "C:\\Users\\" not in parser
