from pathlib import Path

source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

assert '[data-testid="stMainBlockContainer"]' in source
assert '.main .block-container' in source
assert 'padding-top: 3.5rem !important;' in source
assert 'padding-top: 1rem !important;' not in source
print("TOP SPACING TEST OK")
