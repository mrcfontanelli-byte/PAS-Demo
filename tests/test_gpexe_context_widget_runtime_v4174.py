from __future__ import annotations

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).parents[1]


def test_context_switch_rebuilds_session_widget_without_implicit_all():
    script = r'''
from streamlit.testing.v1 import AppTest

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
assert len(sessions.options) == 1
assert sessions.value == ["143261"]
assert at.session_state["pas_gpexe_session_selector_543_2026_2027"] == ["143261"]
assert at.session_state["pas_gpexe_active_session_ids"] == [143261]

context.set_value((469, "2025/2026")).run(timeout=90)
assert not at.exception
context = widget(at, at.selectbox, "Contesto GPExe locale")
sessions = widget(at, at.multiselect, "TeamSession locali attive nel PAS")
assert context.value == (469, "2025/2026")
assert len(sessions.options) == 3
assert len(set(sessions.options)) == 3
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
assert len(sessions.options) == 1
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
