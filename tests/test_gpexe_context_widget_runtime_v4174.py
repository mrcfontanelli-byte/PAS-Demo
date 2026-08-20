from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[1]


def test_context_switch_rebuilds_session_widget_without_implicit_all():
    script = r'''
from streamlit.testing.v1 import AppTest
from pas_connect.pas_bridge import available_athletes, available_sessions

def widget(at, collection, label):
    matches = [item for item in collection if item.label == label]
    assert len(matches) == 1
    return matches[0]

at = AppTest.from_file("app.py")
at.session_state["pas_demo_authenticated"] = True
at.session_state["pas_data_source"] = "gpexe"
at.session_state["pas_gpexe_input_mode"] = "API sincronizzata"
at.session_state["pas_gpexe_local_context"] = (543, "2026/2027")
at.session_state["pas_gpexe_active_session_ids"] = [143261]
at.run(timeout=90)
assert not at.exception

context = widget(at, at.selectbox, "Contesto GPExe locale")
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert context.value == (543, "2026/2027")
assert len(sessions.options) == len(available_sessions(
    ".pas_data/pas_connect.sqlite3", team_id=543, season="2026/2027", ready_only=True,
    dashboard_only=True,
))
assert sessions.value == ["143261"]
assert at.session_state["pas_gpexe_session_selector_543_2026_2027"] == ["143261"]
assert at.session_state["pas_gpexe_active_session_ids"] == [143261]

context.set_value((469, "2025/2026")).run(timeout=90)
assert not at.exception
context = widget(at, at.selectbox, "Contesto GPExe locale")
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert context.value == (469, "2025/2026")
assert len(sessions.options) == len(available_sessions(
    ".pas_data/pas_connect.sqlite3", team_id=469, season="2025/2026", ready_only=True,
    dashboard_only=True,
))
assert all(str(label).strip() for label in sessions.options)
assert sessions.value == []
assert at.session_state["pas_gpexe_active_session_ids"] == []
assert at.session_state["pas_gpexe_session_selector_469_2025_2026"] == []

sessions.set_value(["121408"]).run(timeout=90)
assert at.session_state["pas_gpexe_session_selector_469_2025_2026"] == ["121408"]
assert at.session_state["pas_gpexe_active_session_ids"] == [121408]
assert all(isinstance(value, int) for value in at.session_state["pas_gpexe_active_session_ids"])
context = widget(at, at.selectbox, "Contesto GPExe locale")

context.set_value((543, "2026/2027")).run(timeout=90)
assert not at.exception
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert len(sessions.options) == len(available_sessions(
    ".pas_data/pas_connect.sqlite3", team_id=543, season="2026/2027", ready_only=True,
    dashboard_only=True,
))
assert sessions.value == []
assert at.session_state["pas_gpexe_active_session_ids"] == []
assert at.session_state["pas_gpexe_session_selector_543_2026_2027"] == []

sessions.set_value(["143261"]).run(timeout=90)
assert not at.exception
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert sessions.value == ["143261"]
assert at.session_state["pas_gpexe_active_session_ids"] == [143261]
assert all(isinstance(value, int) for value in at.session_state["pas_gpexe_active_session_ids"])
'''
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=240,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_contextual_select_all_and_clear_use_all_ready_sessions():
    script = r'''
from streamlit.testing.v1 import AppTest
from pas_connect.pas_bridge import available_athletes, available_sessions

def widget(at, collection, label):
    matches = [item for item in collection if item.label == label]
    assert len(matches) == 1
    return matches[0]

at = AppTest.from_file("app.py")
at.session_state["pas_demo_authenticated"] = True
at.session_state["pas_data_source"] = "gpexe"
at.session_state["pas_gpexe_input_mode"] = "API sincronizzata"
at.session_state["pas_gpexe_local_context"] = (543, "2026/2027")
at.session_state["pas_gpexe_active_session_ids"] = []
at.run(timeout=90)
assert not at.exception

expected_543 = available_sessions(
    ".pas_data/pas_connect.sqlite3", team_id=543, season="2026/2027", ready_only=True,
    dashboard_only=True,
)
widget(at, at.button, "Seleziona tutte").click().run(timeout=90)
assert not at.exception
assert len(at.session_state["pas_gpexe_active_session_ids"]) == len(expected_543)
assert set(at.session_state["pas_gpexe_active_session_ids"]) == {
    int(row["provider_session_id"]) for row in expected_543
}
assert at.session_state["dashboard_reference_date"].year == 2026
detail = widget(at, at.multiselect, "Metriche per grafici di dettaglio")
report = widget(at, at.multiselect, "Metriche nel Professional Session Report")
detail_zones = [name for name in detail.options if name.startswith("Distance ") and "km/h" in name]
report_zones = [name for name in report.options if name.startswith("Distance ") and "km/h" in name]
assert len(detail_zones) == 5 and len(report_zones) == 5
assert {"Distance <10 km/h (m)", "Distance >25 km/h (m)"} <= set(detail_zones)
assert {"Distance <10 km/h (m)", "Distance >25 km/h (m)"} <= set(report_zones)
assert all("14.4" not in name and "25.2" not in name for name in detail_zones + report_zones)
assert "RPE" not in detail.options and "RPE" not in report.options
overview = widget(at, at.radio, "Panoramica principale")
assert overview.value == "Team Overview"
overview.set_value("Player Overview").run(timeout=90)
assert not at.exception
players = widget(at, at.selectbox, "Giocatore della panoramica")
assert len(players.options) == len(available_athletes(
    ".pas_data/pas_connect.sqlite3", team_id=543, season="2026/2027",
))

widget(at, at.button, "Azzera selezione").click().run(timeout=90)
assert at.session_state["pas_gpexe_active_session_ids"] == []
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert sessions.value == []

context = widget(at, at.selectbox, "Contesto GPExe locale")
context.set_value((469, "2025/2026")).run(timeout=90)
assert not at.exception
expected_469 = available_sessions(
    ".pas_data/pas_connect.sqlite3", team_id=469, season="2025/2026", ready_only=True,
    dashboard_only=True,
)
widget(at, at.button, "Seleziona tutte").click().run(timeout=90)
assert not at.exception
assert set(at.session_state["pas_gpexe_active_session_ids"]) == {
    int(row["provider_session_id"]) for row in expected_469
}
assert not set(at.session_state["pas_gpexe_active_session_ids"]) & {
    int(row["provider_session_id"]) for row in expected_543
}
assert at.session_state["dashboard_reference_date"].year == 2025
detail = widget(at, at.multiselect, "Metriche per grafici di dettaglio")
report = widget(at, at.multiselect, "Metriche nel Professional Session Report")
detail_zones = [name for name in detail.options if name.startswith("Distance ") and "km/h" in name]
report_zones = [name for name in report.options if name.startswith("Distance ") and "km/h" in name]
assert len(detail_zones) == 4 and len(report_zones) == 4
assert {"Distance <14.4 km/h (m)", "Distance >25.2 km/h (m)"} <= set(detail_zones)
assert {"Distance <14.4 km/h (m)", "Distance >25.2 km/h (m)"} <= set(report_zones)
assert all("<10 " not in name and ">25 " not in name for name in detail_zones + report_zones)
assert "RPE" not in detail.options and "RPE" not in report.options
overview = widget(at, at.radio, "Panoramica principale")
overview.set_value("Player Overview").run(timeout=90)
assert not at.exception
players = widget(at, at.selectbox, "Giocatore della panoramica")
assert len(players.options) == len(available_athletes(
    ".pas_data/pas_connect.sqlite3", team_id=469, season="2025/2026",
))
widget(at, at.radio, "Panoramica principale").set_value("Team Overview").run(timeout=90)
assert not at.exception
'''
    result = subprocess.run(
        [sys.executable, "-c", script], cwd=ROOT,
        capture_output=True, text=True, timeout=360, check=False,
    )
    assert result.returncode == 0, result.stderr
