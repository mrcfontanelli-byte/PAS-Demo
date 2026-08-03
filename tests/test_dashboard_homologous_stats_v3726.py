from pathlib import Path

app = Path("app.py").read_text(encoding="utf-8")
version = Path("modules/version.py").read_text(encoding="utf-8")

assert 'APP_BUILD_VERSION = "3.8.1"' in version
assert 'homologous_values = historical_entity_metric[overview_column]' in app
assert 'period_stats = descriptive_statistics(homologous_values)' in app
assert 'reference_count=int(period_stats["count"])' in app
assert 'period_stats = descriptive_statistics(\n                overview_period_values' not in app
print("DASHBOARD HOMOLOGOUS STATS V3.7.32 TEST OK")
