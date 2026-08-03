from pathlib import Path

import pandas as pd
import pytest

from modules.data_provider import DataProviderNotReadyError, ExcelProvider, GPExeProvider


def test_excel_report_contract_matches_performance_loader(monkeypatch):
    expected = pd.DataFrame({"Athlete": ["Player"], "Date": [pd.Timestamp("2026-08-03")]})
    captured = {}

    def fake_load(self, source, *, source_name=None, filter_configured_roster=True):
        captured.update(source=source, source_name=source_name, roster=filter_configured_roster)
        return expected

    monkeypatch.setattr(ExcelProvider, "load_performance_data", fake_load)
    result = ExcelProvider().load_report_data("database.xlsx", source_name="database.xlsx")

    assert result is expected
    assert captured == {"source": "database.xlsx", "source_name": "database.xlsx", "roster": True}


def test_gpexe_report_contract_remains_disabled():
    with pytest.raises(DataProviderNotReadyError):
        GPExeProvider().load_report_data(Path("unused"))


def test_app_routes_session_report_through_report_source():
    app = Path("app.py").read_text(encoding="utf-8")
    assert "report_source = data_provider.load_report_data(" in app
    assert "session_day_raw = report_source[" in app
    assert "build_historical_max_speed_references(report_source)" in app
