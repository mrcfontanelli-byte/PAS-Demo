import pytest
from modules.data_mapping import MappingValidationError, map_gpexe_metrics, resolve_metric


def test_aliases_resolve_to_pas_columns():
    assert resolve_metric("Total Distance").pas_column == "distance (m)"
    assert resolve_metric("Maximum Speed").pas_column == "max speed (km/h)"


def test_mapping_and_supported_unit_conversion():
    mapped = map_gpexe_metrics(
        {"Total Distance": 10.5, "Maximum Speed": 8.0, "unknown": 99},
        units={"Total Distance": "km", "Maximum Speed": "m/s"},
        require_core=True,
    )
    assert mapped == {"distance (m)": 10500, "max speed (km/h)": 28.8}


def test_missing_required_metric_is_rejected_only_when_requested():
    assert map_gpexe_metrics({"Maximum Speed": 30}) == {"max speed (km/h)": 30}
    with pytest.raises(MappingValidationError, match="distance"):
        map_gpexe_metrics({"Maximum Speed": 30}, require_core=True)


def test_unsupported_units_do_not_silently_change_data():
    with pytest.raises(MappingValidationError, match="Unità GPExe non supportata"):
        map_gpexe_metrics({"Total Distance": 1}, units={"Total Distance": "yards"})
