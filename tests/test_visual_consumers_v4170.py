from __future__ import annotations

import json

import pandas as pd

from modules.day_overview_provider import load_gpexe_day_overview
from modules.reporting import build_session_report_pdf
from pas_connect.database import PASConnectDatabase
from pas_connect.rest_mapper import map_rest_speed_zone
from pas_connect.rest_persistence import GPExeRESTPersistenceGate
from pas_connect.rest_service import RESTBundleResult


def _zone(lower, upper, distance, number):
    return map_rest_speed_zone({
        "zone_number": number, "lower_bound": lower, "upper_bound": upper,
        "distance": distance, "time": 10,
    })


def _metric(name, canonical, value, unit=None):
    return {
        "provider_name": name, "canonical_metric": canonical, "value": value,
        "value_type": "null" if value is None else "number", "unit": unit,
        "active": True, "provenance": "gpexe_rest_athlete_session_detail",
        "raw": {"name": name, "value": value, "unit": unit},
    }


def _publish_context(db, team_id, season, team_session_id, athlete_session_id, zones):
    metrics = [
        _metric("distance", "Distance", 1200, "m"),
        _metric("duration", "Duration", 3600, "s"),
        _metric("acceleration_events", "Acc Events", 12, ""),
        _metric("deceleration_events", "Dec Events", 11, ""),
        _metric("speed_events", "Speed Events", 9, ""),
        _metric("rpe", "RPE", None, ""),
        _metric("max_values_speed", "Max Speed", 27, "km/h"),
    ]
    row = {
        "provider_athlete_session_id": athlete_session_id,
        "provider_session_id": team_session_id,
        "athlete": {"provider_player_id": athlete_session_id + 100},
        "track": {"provider_track_id": str(athlete_session_id + 200)},
        "state": "READY", "starter": True, "is_stats_valid": True,
        "total_time": 3600, "kpis": metrics, "zones": {"speed_zones": zones},
        "raw": {"id": athlete_session_id},
        "provenance": "gpexe_rest_athlete_session_detail",
    }
    bundle = {
        "provider_contract": "rest_v2", "requested_team_session_id": team_session_id,
        "team_session": {
            "provider_session_id": team_session_id, "team_id": team_id,
            "category": {"id": 1, "name": "Training"}, "nature": "training",
            "start_timestamp": f"{season[:4]}-08-01T10:00:00Z", "total_time": 3600,
            "is_stats_valid": True, "drill": {}, "raw": {"general": {"id": team_session_id}},
        },
        "athlete_session_ids": (athlete_session_id,), "athlete_sessions": (row,),
    }
    GPExeRESTPersistenceGate(db).publish(
        RESTBundleResult("READY", False, bundle, ()), season=season,
    )


def _overview(tmp_path, team_id, season, session_id, athlete_id, zones):
    db = PASConnectDatabase(tmp_path / f"pas-{team_id}.sqlite3")
    _publish_context(db, team_id, season, session_id, athlete_id, zones)
    return load_gpexe_day_overview(
        db.path, f"{season[:4]}-08-01", team_id=team_id, session_ids=[session_id],
    )


def test_team_469_and_543_dynamic_zones_are_contextual_and_ordered(tmp_path):
    en_dash = chr(0x2013)
    team_469 = _overview(tmp_path, 469, "2025/2026", 100, 1000, [
        _zone(7, None, 22, 9), _zone(5.5, 7, 111, 3),
    ])
    team_543 = _overview(tmp_path, 543, "2026/2027", 200, 2000, [
        _zone(25 / 3.6, None, 44, 1), _zone(20 / 3.6, 25 / 3.6, 333, 99),
    ])
    labels_469 = list(team_469.attrs["dynamic_metric_specs"])
    labels_543 = list(team_543.attrs["dynamic_metric_specs"])
    assert labels_469 == [f"Distance 19.8{en_dash}25.2 km/h (m)", "Distance >25.2 km/h (m)"]
    assert labels_543 == [f"Distance 20{en_dash}25 km/h (m)", "Distance >25 km/h (m)"]
    assert team_469.iloc[0][labels_469].tolist() == [111, 22]
    assert team_543.iloc[0][labels_543].tolist() == [333, 44]
    assert not set(labels_469) & set(labels_543)


def test_overview_exposes_seven_scalars_without_double_conversion(tmp_path):
    frame = _overview(tmp_path, 543, "2026/2027", 200, 2000, [])
    row = frame.iloc[0]
    assert row["distance (m)"] == 1200
    assert row["Duration (dec)"] == 60
    assert row["acc events"] == 12
    assert row["dec events"] == 11
    assert row["speed events"] == 9
    assert pd.isna(row["RPE (CR10)"])
    assert row["max speed (km/h)"] == 27


def test_overview_rest_precedence_null_ownership_and_graphql_fallback(tmp_path):
    db = PASConnectDatabase(tmp_path / "precedence.sqlite3")
    _publish_context(db, 543, "2026/2027", 200, 2000, [])
    with db.connect() as connection:
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json)
            VALUES(2000,'kpi',0,'total_distance','9999','Distance','m','m','{}')"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json)
            VALUES(2000,'kpi',1,'rpe','10','RPE','','','{}')"""
        )
        connection.execute(
            """DELETE FROM gpexe_athlete_session_kpis
            WHERE provider_athlete_session_id=2000 AND source='rest_v2' AND name='speed_events'"""
        )
        connection.execute(
            """INSERT INTO gpexe_athlete_session_kpis(
            provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json)
            VALUES(2000,'kpi',2,'speed_events','77','Speed Events','','','{}')"""
        )
        connection.commit()
    row = load_gpexe_day_overview(
        db.path, "2026-08-01", team_id=543, session_ids=[200],
    ).iloc[0]
    assert row["distance (m)"] == 1200
    assert pd.isna(row["RPE (CR10)"])
    assert row["speed events"] == 77


def test_session_pdf_accepts_unicode_dynamic_labels(tmp_path):
    en_dash = chr(0x2013)
    bounded = f"Distance 20{en_dash}25 km/h (m)"
    open_ended = "Distance >25 km/h (m)"
    specs = {
        bounded: {"column": bounded, "unit": "m", "aggregation": "sum",
                  "metric_family": "Speed Zone Distance", "threshold_lower": 20,
                  "threshold_upper": 25, "color": "#F2CF5B"},
        open_ended: {"column": open_ended, "unit": "m", "aggregation": "sum",
                     "metric_family": "Speed Zone Distance", "threshold_lower": 25,
                     "threshold_upper": None, "color": "#F2CF5B"},
    }
    data = pd.DataFrame({"Athlete": ["TECHNICAL ID"], bounded: [333], open_ended: [44]})
    pdf = build_session_report_pdf(
        data, [open_ended, bounded], specs, "SESSION REPORT",
        {"date": "01/08/2026", "match_day": "N/D", "cycle": "N/D",
         "drill": "Training", "time_of_day": "10:00"},
    )
    assert pdf.startswith(b"%PDF-")
    assert len(pdf) > 1000
    assert list(specs) == [bounded, open_ended]
