from pathlib import Path

root = Path(__file__).resolve().parents[1]
app = (root / "app.py").read_text(encoding="utf-8")
assistant = (root / "modules" / "pas_assistant.py").read_text(encoding="utf-8")

assert "Player drill coverage" not in app
assert "drills_min_full_training" not in app
assert "normalized_available_drills.value_counts().index.tolist()" in app
assert "default_drills = available_drills[:3]" in app
assert 'key="drills_selected_v3725"' in app
assert "Nessun drill disponibile con i filtri correnti." in app
assert 'placeholder="Cosa vuoi analizzare?"' in assistant
print("DRILLS SELECTOR V3.7.24 TEST OK")
