import json
from pathlib import Path
import sqlite3

import pandas as pd
import pytest

from modules.data_provider import DEFAULT_PROVIDER_ID, ExcelProvider, GPExeProvider
from modules.day_overview_provider import (
    OVERVIEW_METRICS, coverage_percentage, duration_seconds, overview_coverage,
    resolve_threshold_metric_profile,
)
from modules.day_overview_validation import compare_overview_metric
from modules.session_distance import SessionDistanceError
from pas_connect.database import PASConnectDatabase
from pas_connect.mapper import map_athlete_session_detail
from pas_connect.metric_catalog import classify_header


def _database(path: Path) -> Path:
    db = PASConnectDatabase(path); db.initialize()
    with db.connect() as c:
        c.execute("""INSERT INTO gpexe_teams(provider_team_id,team_name,season,synced_at,raw_json)
          VALUES(469,'SERIE A','2025-2026','now','{}')""")
        for canonical, provider_name in (
            ("Duration", "duration (mm:ss)"), ("Distance", "distance (m)"),
            ("Acc Events", "acc events"), ("Dec Events", "dec events"),
            ("Max Speed", "max speed (km/h)"), ("Speed Events", "speed events"),
        ):
            c.execute("""INSERT INTO pas_metric_catalog(canonical_metric,display_name,provider,
              acquisition_mode,provider_metric_name,category,metric_type,canonical_unit,
              provider_unit,value_type,requires_profile,active,is_contextual,created_at,updated_at)
              VALUES(?,?, 'GPExe','GRAPHQL',?,'GPS','direct','', '', 'numeric',0,1,0,'now','now')""",
              (canonical, canonical, provider_name))
        c.execute("""INSERT INTO gpexe_team_sessions(provider_session_id,team_id,session_name,
          start_timestamp,is_stats_valid,drill_enabled,synced_at,raw_json)
          VALUES(10,469,'Training','2025-08-01T10:00:00',1,1,'now','{}')""")
        c.execute("INSERT INTO gpexe_athletes(provider_player_id,player_name,synced_at,raw_json) VALUES(7,'MARIO ROSSI','now','{}')")
        raw = json.dumps({"totalTime":{"value":4800,"uom":"s"}})
        c.execute("""INSERT INTO gpexe_athlete_session_details(provider_athlete_session_id,
          provider_session_id,provider_player_id,metrics_json,zones_json,synced_at,raw_json)
          VALUES(20,10,7,'{}','{}','now',?)""", (raw,))
        for position, name, value, uom in (
            (0,"total_distance",6000,"m"),(1,"acceleration_events",20,""),
            (2,"deceleration_events",15,""),(3,"max_values_speed",31.2,"km/h"),
            (4,"speed_events",8,""),
        ):
            c.execute("""INSERT INTO gpexe_athlete_session_kpis(provider_athlete_session_id,
              source,position,name,value,kpi_group,uom,unit,raw_json)
              VALUES(20,'identifierKpi',?,?,?,'GPS',?,'number','{}')""",
              (position,name,value,uom))
        c.commit()
    return db.path


def test_excel_default_and_manual_source_contract():
    assert DEFAULT_PROVIDER_ID == "excel"
    source = pd.DataFrame({"Date":["2025-08-01"],"Athlete":["A"],"Duration (dec)":[80]})
    assert len(ExcelProvider().load_day_overview_data(source,"2025-08-01")) == 1


@pytest.mark.parametrize(("value","unit","expected"), [
    (60,"s",60),(2,"min",120),("01:30",None,90),("01:01:01",None,3661),
])
def test_duration_normalization(value, unit, expected):
    assert duration_seconds(value, unit) == expected


def test_duration_catalog_and_mapper_use_verified_total_time():
    assert classify_header("duration (mm:ss)")["canonical_unit"] == "s"
    mapped = map_athlete_session_detail(
        {"id":"20","totalTime":{"value":4800,"uom":"s"}},
        provider_athlete_session_id=20, provider_session_id=10,
    )
    assert mapped["duration"] == 4800


def test_gpexe_overview_metrics_and_filters(tmp_path):
    frame = GPExeProvider().load_day_overview_data(
        _database(tmp_path/"pas.sqlite3"), "2025-08-01", team_id="469",
        session_ids=[10], athlete_ids=[7], drill="Full Training",
    )
    row = frame.iloc[0]
    assert row["Duration (s)"] == 4800 and row["Duration (dec)"] == 80
    assert row["distance (m)"] == 6000
    assert row["acc events"] == 20 and row["dec events"] == 15
    assert row["max speed (km/h)"] == 31.2 and row["speed events"] == 8


def test_missing_day_drill_and_no_excel_fallback(tmp_path):
    path = _database(tmp_path/"pas.sqlite3")
    with pytest.raises(SessionDistanceError, match="giornata selezionata"):
        GPExeProvider().load_day_overview_data(path,"2025-07-01")
    with pytest.raises(SessionDistanceError, match="filtro Drill"):
        GPExeProvider().load_day_overview_data(path,"2025-08-01",drill="Unverified")
    with pytest.raises(Exception, match="esclusivamente"):
        GPExeProvider().load_day_overview_data(tmp_path/"export.csv","2025-08-01")


def test_firstbeat_coverage_and_percentage(tmp_path):
    rows = overview_coverage(
        _database(tmp_path/"pas.sqlite3"), team_id=469,
        season="2025-2026", valid_on="2025-08-01",
    )
    by_name = {row["Metrica"]:row for row in rows}
    assert by_name["Anaerobic Threshold Zone (mm:ss)"]["Stato"] == "EXTERNAL_PROVIDER"
    assert by_name["High Intensity Training (mm:ss)"]["Provider richiesto"] == "Firstbeat"
    assert by_name["RPE"]["Stato"] == "MISSING"
    assert 0 < coverage_percentage(rows) < 100


def test_z3_profile_alias_resolves_real_provider_kpi_without_duplicate(tmp_path):
    path = _database(tmp_path/"pas.sqlite3")
    db = PASConnectDatabase(path)
    with db.connect() as c:
        c.execute("""INSERT INTO pas_metric_catalog(canonical_metric,display_name,provider,
          acquisition_mode,provider_metric_name,category,metric_type,canonical_unit,
          provider_unit,value_type,requires_profile,active,is_contextual,created_at,updated_at)
          VALUES('Distance/Speed Z3','Distance/Speed Z3','GPExe','GRAPHQL',
          'distance/speed Z3 (m)','GPS','threshold_distance','m','m','numeric',1,1,0,'now','now')""")
        c.execute("""INSERT INTO gpexe_athlete_session_kpis(provider_athlete_session_id,
          source,position,name,value,kpi_group,uom,unit,raw_json)
          VALUES(20,'identifierKpi',9,'athletesessionspeedzone_distance_3',321,
          'GPS','m','distance','{}')""")
        c.commit()
    profile = {"team_id":"469","team_name":"SERIE A","season":"2025-2026",
        "canonical_metric":"Distance 19.8-25.2 km/h",
        "provider_metric_name":"athletesessionspeedzone_distance_3",
        "threshold_min":19.8,"threshold_max":25.2,
        "threshold_min_inclusive":True,"threshold_max_inclusive":False,
        "threshold_unit":"km/h","source":"GPExe","valid_from":None,"valid_to":None,
        "verified":True,"notes":"test"}
    first_id, inserted = db.upsert_metric_profile(profile)
    second_id, inserted_again = db.upsert_metric_profile(profile)
    assert inserted and not inserted_again and first_id == second_id
    assert db.metric_profile_catalog_status(profile["canonical_metric"]) == "VALID"
    rows = overview_coverage(path,team_id=469,season="2025-2026",valid_on="2025-08-01")
    assert next(r for r in rows if r["Metrica"].startswith("Distance 19.8"))["Stato"] == "VERIFIED"
    frame = GPExeProvider().load_day_overview_data(path,"2025-08-01",team_id=469)
    assert frame.iloc[0]["distance/speed Z3 (m)"] == 321


@pytest.mark.parametrize(("stored_name","requested_name"), [
    ("Distance 19.8-25.2 km/h", "Distance 19.8–25.2 km/h"),
    ("Distance Z3", "Distance 19.8-25.2 km/h"),
    ("Distance/Speed Z3", "Distance 19.8–25.2 km/h"),
    ("Distance Z4", "Distance >25.2 km/h"),
    ("Distance/Speed Z4", "Distance >25.2 km/h"),
])
def test_threshold_profile_resolver_supports_controlled_aliases(tmp_path, stored_name, requested_name):
    path = _database(tmp_path/"pas.sqlite3")
    bounded = "Z3" in stored_name or "19.8" in stored_name
    with sqlite3.connect(path) as connection:
        connection.execute("""INSERT INTO pas_metric_profiles(team_id,team_name,season,
          canonical_metric,provider_metric_name,threshold_min,threshold_max,
          threshold_min_inclusive,threshold_max_inclusive,threshold_unit,source,
          valid_from,valid_to,verified,created_at,updated_at)
          VALUES(469,'SERIE A','2025-2026',?,?,19.8,?,1,0,'km/h','GPExe',
          '2025-07-01','2025-08-31',1,'now','now')""",
          (stored_name, "real_z3" if bounded else "real_z4", 25.2 if bounded else None))
        profile = resolve_threshold_metric_profile(
            connection, requested_name, team_id=469, season="2025-2026", valid_on="2025-08-01",
        )
    assert profile is not None
    assert profile["provider_metric_name"] == ("real_z3" if bounded else "real_z4")


@pytest.mark.parametrize(("team_id","season","verified","valid_from","valid_to"), [
    (999,"2025-2026",1,"2025-07-01","2025-08-31"),
    (469,"2024-2025",1,"2025-07-01","2025-08-31"),
    (469,"2025-2026",0,"2025-07-01","2025-08-31"),
    (469,"2025-2026",1,"2025-09-01",None),
    (469,"2025-2026",1,None,"2025-07-31"),
])
def test_threshold_profile_resolver_respects_scope_and_validity(
    tmp_path, team_id, season, verified, valid_from, valid_to,
):
    path = _database(tmp_path/"pas.sqlite3")
    with sqlite3.connect(path) as connection:
        connection.execute("""INSERT INTO pas_metric_profiles(team_id,team_name,season,
          canonical_metric,provider_metric_name,threshold_min,threshold_max,
          threshold_min_inclusive,threshold_max_inclusive,threshold_unit,source,
          valid_from,valid_to,verified,created_at,updated_at)
          VALUES(?,'SERIE A',?,'Distance Z3','real_z3',19.8,25.2,1,0,'km/h',
          'GPExe',?,?,?,'now','now')""",
          (team_id, season, valid_from, valid_to, verified))
        profile = resolve_threshold_metric_profile(
            connection, "Distance 19.8–25.2 km/h", team_id=469,
            season="2025-2026", valid_on="2025-08-01",
        )
    assert profile is None


def test_dashboard_infers_team_and_resolves_both_threshold_cards(tmp_path):
    path = _database(tmp_path/"pas.sqlite3")
    with sqlite3.connect(path) as connection:
        for name, provider, maximum, value, position in (
            ("Distance Z3", "real_z3", 25.2, 321, 9),
            ("Distance Z4", "real_z4", None, 45, 10),
        ):
            connection.execute("""INSERT INTO pas_metric_profiles(team_id,team_name,season,
              canonical_metric,provider_metric_name,threshold_min,threshold_max,
              threshold_min_inclusive,threshold_max_inclusive,threshold_unit,source,
              verified,created_at,updated_at) VALUES(469,'SERIE A','2025-2026',?,?,
              19.8,?,1,0,'km/h','GPExe',1,'now','now')""", (name,provider,maximum))
            connection.execute("""INSERT INTO gpexe_athlete_session_kpis(
              provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json)
              VALUES(20,'identifierKpi',?,?,?,'GPS','m','distance','{}')""", (position,provider,value))
        connection.commit()
    frame = GPExeProvider().load_day_overview_data(path,"2025-08-01",team_id=None)
    assert frame.iloc[0]["distance/speed Z3 (m)"] == 321
    assert frame.iloc[0]["distance/speed Z4 (m)"] == 45
    coverage = overview_coverage(path,valid_on="2025-08-01")
    threshold_rows = [row for row in coverage if row["Metrica"].startswith("Distance 19.8") or row["Metrica"].startswith("Distance >")]
    assert {row["Stato"] for row in threshold_rows} == {"VERIFIED"}


def test_multi_metric_bridge_duration_in_seconds_and_counts(tmp_path):
    gpexe = GPExeProvider().load_day_overview_data(_database(tmp_path/"pas.sqlite3"),"2025-08-01")
    excel = pd.DataFrame({"Athlete":["MARIO ROSSI","ONLY EXCEL"],"Duration (dec)":[80,10]})
    compared, summary = compare_overview_metric(excel,gpexe,"Duration (min)",tolerance=.1)
    assert compared["Stato"].tolist() == ["OK"]
    assert summary == {"atleti_confrontati":1,"atleti_coincidenti":1,"atleti_differenti":0,
                       "atleti_solo_excel":1,"atleti_solo_gpexe":0,"tolleranza":.1,"unita":"s"}


def test_dashboard_and_developer_tools_wiring_is_scoped():
    app = Path("app.py").read_text(encoding="utf-8")
    navigation = app[app.index("page = st.radio"):app.index("st.divider()",app.index("page = st.radio"))]
    assert "Distance Pilot" not in navigation and "Bridge Validation" not in navigation
    assert "load_day_overview_data" in app
    assert "Metrica disponibile tramite provider Firstbeat." in app
    assert "Relative Distance" not in app[app.index("metric_groups = {"):app.index("metric_reference_rows",app.index("metric_groups = {"))]
    assert len(OVERVIEW_METRICS) == 11
