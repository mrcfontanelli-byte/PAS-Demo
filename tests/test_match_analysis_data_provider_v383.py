from pathlib import Path

import pandas as pd
import pytest

from modules.data_provider import DataProviderNotReadyError, ExcelProvider, GPExeProvider


def test_excel_provider_loads_match_analysis_without_roster_filter(monkeypatch) -> None:
    provider = ExcelProvider()
    expected = pd.DataFrame({"Player Name": ["Player A"], "Drill": ["Match"]})
    captured = {}

    def fake_load(source, *, source_name=None, filter_configured_roster=True):
        captured.update(source=source, source_name=source_name, filter=filter_configured_roster)
        return expected

    monkeypatch.setattr(ExcelProvider, "load_performance_data", lambda self, source, *, source_name=None, filter_configured_roster=True: fake_load(source, source_name=source_name, filter_configured_roster=filter_configured_roster))
    loaded = provider.load_match_analysis_data("match.xlsx", source_name="match.xlsx")

    assert loaded is expected
    assert captured == {"source": "match.xlsx", "source_name": "match.xlsx", "filter": False}


def test_gpexe_provider_keeps_match_analysis_disabled() -> None:
    with pytest.raises(DataProviderNotReadyError):
        GPExeProvider().load_match_analysis_data(None)


def test_app_routes_match_analysis_through_dedicated_provider_contract() -> None:
    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert source.count("data_provider.load_match_analysis_data(") == 2
    assert "match_source = data_provider.load_performance_data(" not in source
