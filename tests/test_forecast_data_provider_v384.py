from pathlib import Path

from modules.data_provider import ExcelProvider, GPExeProvider, DataProviderNotReadyError


def test_excel_provider_exposes_forecast_contract():
    source = Path(__file__).parents[1] / "modules" / "data_provider.py"
    text = source.read_text(encoding="utf-8")
    assert "def load_forecast_data(" in text
    assert '("Esercitazioni Avg",)' in text


def test_forecast_ui_uses_dedicated_provider_dataset():
    app = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    assert "forecast_exercises_avg = load_forecast_sheet(" in app
    forecast = app.split('if page == "🔮 Forecast":', 1)[1]
    assert "forecast_exercises_avg" in forecast
    assert "exercises_avg" not in forecast.replace("forecast_exercises_avg", "")


def test_gpexe_forecast_contract_is_not_operational():
    try:
        GPExeProvider().load_forecast_data(None)
    except DataProviderNotReadyError:
        pass
    else:
        raise AssertionError("GPExe Forecast must remain disabled in v3.8.4")
