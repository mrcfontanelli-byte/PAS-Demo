from pathlib import Path

import pandas as pd
import pytest

from modules.data_provider import ExcelProvider, GPExeProvider, DataProviderNotReadyError


def test_excel_provider_loads_drills_tables(tmp_path: Path) -> None:
    source = tmp_path / "drills.xlsx"
    exercises = pd.DataFrame({"Drill": ["Full Training"], "Distance": [1000]})
    averages = pd.DataFrame({"Drill": ["Full Training"], "Distance": [950]})
    with pd.ExcelWriter(source) as writer:
        exercises.to_excel(writer, sheet_name="Esercitazioni", index=False)
        averages.to_excel(writer, sheet_name="Esercitazioni Avg", index=False)

    loaded_exercises, loaded_averages = ExcelProvider().load_drills_data(source)

    pd.testing.assert_frame_equal(loaded_exercises, exercises)
    pd.testing.assert_frame_equal(loaded_averages, averages)


def test_gpexe_provider_keeps_drills_disabled() -> None:
    with pytest.raises(DataProviderNotReadyError):
        GPExeProvider().load_drills_data(None)


def test_app_routes_drills_through_dedicated_provider_contract() -> None:
    app_source = Path("app.py").read_text(encoding="utf-8")
    assert "data_provider.load_drills_data" in app_source
    assert 'data_provider.load_named_tables(\n        excel_source' not in app_source
