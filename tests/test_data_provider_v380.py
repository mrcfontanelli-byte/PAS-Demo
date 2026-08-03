from pathlib import Path

import pytest

from modules.data_provider import (
    DEFAULT_PROVIDER_ID,
    DataProviderNotReadyError,
    ExcelProvider,
    GPExeProvider,
    get_data_provider,
)


def test_excel_is_default_provider():
    provider = get_data_provider()
    assert DEFAULT_PROVIDER_ID == "excel"
    assert isinstance(provider, ExcelProvider)


def test_excel_provider_resolves_included_database():
    provider = ExcelProvider()
    source = provider.resolve_default_source(Path(__file__).resolve().parents[1])
    assert source.name == "Database Hellas 25-26.xlsx"


def test_gpexe_provider_is_prepared_but_not_operational():
    provider = GPExeProvider()
    with pytest.raises(DataProviderNotReadyError):
        provider.load_performance_data(None)
