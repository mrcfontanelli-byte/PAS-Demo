from pathlib import Path
from modules.data_provider import DEFAULT_PROVIDER_ID, ExcelProvider, GPExeProvider, get_data_provider

def test_excel_is_default_provider():
    assert DEFAULT_PROVIDER_ID == "excel"
    assert isinstance(get_data_provider(), ExcelProvider)

def test_excel_provider_resolves_included_database():
    source = ExcelProvider().resolve_default_source(Path(__file__).resolve().parents[1])
    assert source.name == "Database Hellas 25-26.xlsx"

def test_gpexe_provider_is_registered_and_operational():
    assert isinstance(get_data_provider("gpexe"), GPExeProvider)
