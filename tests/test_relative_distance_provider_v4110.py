import sqlite3
import subprocess
import sys

import pandas as pd
import pytest

from modules.relative_distance_validation import compare_relative_distance_sources
from modules.data_provider import DEFAULT_PROVIDER_ID, ExcelProvider, GPExeProvider
from modules.session_distance import SessionDistanceError
from pas_connect.database import PASConnectDatabase
from pas_connect.metric_usage import scan_metric_usage


def _database(path):
    db = PASConnectDatabase(path)
    db.initialize()
    with db.connect() as connection:
        connection.execute("""INSERT INTO pas_metric_catalog(
            canonical_metric,display_name,provider,acquisition_mode,provider_metric_name,
            category,metric_type,canonical_unit,provider_unit,value_type,requires_profile,
            active,is_contextual,created_at,updated_at)
            VALUES('Avg Speed','Relative Distance','GPExe','GRAPHQL','avg speed (m/min)',
            'GPS','speed','m/min','m/min','numeric',0,1,0,'now','now')""")
        connection.execute("""INSERT INTO gpexe_team_sessions(
            provider_session_id,team_id,session_name,start_timestamp,is_stats_valid,
            drill_enabled,synced_at,raw_json) VALUES(10,469,'Training',
            '2026-08-01T10:00:00',1,1,'now','{}')""")
        for aid, athlete_session, name, value in ((7,20,'MARIO ROSSI','101.5'),(8,21,'LUCA BIANCHI','99')):
            connection.execute("INSERT INTO gpexe_athletes(provider_player_id,player_name,synced_at,raw_json) VALUES(?,?,'now','{}')", (aid,name))
            connection.execute("""INSERT INTO gpexe_athlete_session_details(
                provider_athlete_session_id,provider_session_id,provider_player_id,
                metrics_json,zones_json,synced_at,raw_json) VALUES(?,10,?,'{}','{}','now','{}')""", (athlete_session,aid))
            connection.execute("""INSERT INTO gpexe_athlete_session_kpis(
                provider_athlete_session_id,source,position,name,value,kpi_group,uom,unit,raw_json)
                VALUES(?,'identifierKpi',0,'average_v',?,'GPS','m/min','speed','{}')""", (athlete_session,value))
        connection.commit()
    return db.path


def test_relative_distance_excel_keeps_historical_column_and_default():
    assert DEFAULT_PROVIDER_ID == "excel"
    source = pd.DataFrame({"Date":["2026-08-01"],"Athlete":["Mario Rossi"],
                           "avg speed (m/min)":[101.5]})
    result = ExcelProvider().load_session_relative_distance_data(source, "2026-08-01")
    assert result["Relative Distance (m/min)"].tolist() == [101.5]
    assert source.columns.tolist()[-1] == "avg speed (m/min)"


def test_relative_distance_gpexe_uses_catalog_ids_and_filters(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    result = GPExeProvider().load_session_relative_distance_data(
        path, "2026-08-01", team_id="469", session_ids=[10], athlete_ids=[7]
    )
    assert result[["Athlete ID", "Relative Distance (m/min)"]].values.tolist() == [[7, 101.5]]


def test_gpexe_has_no_silent_excel_fallback(tmp_path):
    path = _database(tmp_path / "pas.sqlite3")
    with sqlite3.connect(path) as connection:
        connection.execute("DELETE FROM pas_metric_catalog")
        connection.commit()
    with pytest.raises(SessionDistanceError, match="Relative Distance"):
        GPExeProvider().load_session_relative_distance_data(path, "2026-08-01")


def test_bridge_validation_relative_distance_counts_all_states():
    excel = pd.DataFrame({"Date":["2026-08-01"]*2,"Athlete":["A","B"],
        "Relative Distance (m/min)":[100,90]})
    gpexe = pd.DataFrame({"Date":["2026-08-01"]*2,"Athlete":["A","C"],
        "Relative Distance (m/min)":[100.05,80]})
    result = compare_relative_distance_sources(excel,gpexe,tolerance_m_min=.1)
    assert result.summary["atleti_coincidenti"] == 1
    assert result.summary["atleti_solo_excel"] == 1
    assert result.summary["atleti_solo_gpexe"] == 1
    assert len(result.comparisons) == 1


def test_usage_registry_and_developer_tools_are_wired():
    catalog = [{"canonical_metric":"Relative Distance","display_name":"Relative Distance",
                "provider_metric_name":"avg speed (m/min)"}]
    rows = scan_metric_usage(".", catalog)
    keys = {(r["canonical_metric"],r["module"],r["usage_type"]) for r in rows}
    assert ("Relative Distance","Dashboard","display") not in keys
    assert ("Relative Distance","Bridge Validation","comparison") in keys
    assert ("Relative Distance","Drills","display") in keys
    assert ("Relative Distance","Match","display") in keys
    assert ("Relative Distance","Session Report","report") in keys
    app = open("app.py",encoding="utf-8").read()
    navigation = app[app.index("page = st.radio"):app.index("st.divider()", app.index("page = st.radio"))]
    assert "Distance Pilot" not in navigation and "Bridge Validation" not in navigation
    tools = open("modules/developer_tools.py",encoding="utf-8").read()
    assert 'st.expander("Developer Tools"' in tools
    assert '"Data Relative Distance"' in tools
    assert "dashboard_uses_gpexe_relative_distance" not in app
    assert '"Relative Distance (m/min)": {' not in open(
        "modules/config.py", encoding="utf-8"
    ).read()


def test_distance_catalog_profiles_and_usage_code_remain_present():
    assert "load_session_distance_data" in open("modules/data_provider.py",encoding="utf-8").read()
    assert "pas_metric_catalog" in open("pas_connect/metric_catalog.py",encoding="utf-8").read()
    assert "pas_metric_profiles" in open("pas_connect/database.py",encoding="utf-8").read()
    assert "pas_metric_usage" in open("pas_connect/database.py",encoding="utf-8").read()


def test_clean_process_imports_relative_validation_and_app_without_import_error():
    completed = subprocess.run(
        [sys.executable, "-c", (
            "from modules.relative_distance_validation import "
            "compare_relative_distance_sources; import app"
        )],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    assert "ImportError" not in completed.stderr
