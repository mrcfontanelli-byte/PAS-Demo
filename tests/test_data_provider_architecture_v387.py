from modules.data_provider import (
    ExcelProvider,
    get_available_data_providers,
    normalize_provider_id,
    resolve_data_provider,
)


def test_provider_catalog_is_centralized_and_ordered():
    catalog = get_available_data_providers()
    assert [item.provider_id for item in catalog] == ["excel", "gpexe"]
    assert catalog[0].operational is True
    assert catalog[1].operational is False


def test_excel_selection_is_effective_without_fallback():
    selection = resolve_data_provider("Excel")
    assert selection.requested.provider_id == "excel"
    assert selection.effective.provider_id == "excel"
    assert selection.fallback_applied is False
    assert isinstance(selection.provider, ExcelProvider)


def test_gpexe_selection_falls_back_to_excel():
    selection = resolve_data_provider("GPExe")
    assert selection.requested.provider_id == "gpexe"
    assert selection.effective.provider_id == "excel"
    assert selection.fallback_applied is True
    assert isinstance(selection.provider, ExcelProvider)


def test_provider_ids_and_display_names_are_normalized():
    assert normalize_provider_id(" GPExe ") == "gpexe"
    assert normalize_provider_id(None) == "excel"
