from modules.data_provider import get_available_data_providers, resolve_data_provider

def test_provider_catalog_is_centralized_and_ordered():
    catalog = get_available_data_providers()
    assert [item.provider_id for item in catalog] == ["excel", "gpexe"]
    assert catalog[0].operational is True
    assert catalog[1].operational is True

def test_excel_selection_remains_default():
    selection = resolve_data_provider("excel")
    assert selection.effective.provider_id == "excel"
    assert selection.fallback_applied is False

def test_gpexe_selection_is_operational():
    selection = resolve_data_provider("gpexe")
    assert selection.effective.provider_id == "gpexe"
    assert selection.fallback_applied is False
