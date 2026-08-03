from pathlib import Path

app = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")
version = (Path(__file__).resolve().parents[1] / "modules" / "version.py").read_text(encoding="utf-8")

assert 'APP_BUILD_VERSION = "4.1.' in version
assert "DRILL_BOXPLOT_PALETTE = [" in app
assert app.count("#2F80ED") >= 1
assert app.count("#BDBDBD") >= 1
assert "drill_color = _drill_box_color(drill_index)" in app
assert "fillcolor=drill_color" in app
assert 'title_text=(\n                "Drill · colore box plot"' in app
assert "max_selections=10" in app
assert 'key="drills_selected_v3725"' in app
assert "showlegend=False" in app
assert "if drill_has_data:" in app

print("DRILLS BOXPLOT COLORS V3.7.25 TEST OK")
