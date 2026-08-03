from pathlib import Path

from modules.data_provider import GPExeProvider, resolve_data_provider
from modules.gpexe_import import import_gpexe_file

FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'gpexe_full_training_sample.csv'


def test_gpexe_is_operational():
    selection = resolve_data_provider('gpexe')
    assert selection.effective.provider_id == 'gpexe'
    assert selection.fallback_applied is False


def test_real_gpexe_semicolon_export_maps_to_pas_schema():
    result = import_gpexe_file(FIXTURE)
    assert result.rows_read == 26
    assert result.rows_imported == 26
    assert result.rows_rejected == 0
    required = {
        'Date', 'Athlete', 'Drill', 'Season Phase', 'Cycle', 'Length Cycle',
        'Match Day +/-', 'Role', 'Duration (dec)', 'distance (m)',
        'relative distance (m/min)', 'distance/speed Z3 (m)',
        'distance/speed Z4 (m)', 'speed events', 'max speed (km/h)',
        'acc events', 'dec events',
    }
    assert required.issubset(result.data.columns)
    assert result.data['Drill'].eq('Full Training').all()
    assert result.data['Match Day +/-'].eq('MD-5').all()


def test_provider_loads_real_export_in_memory():
    frame = GPExeProvider().load_performance_data(FIXTURE, filter_configured_roster=False)
    assert len(frame) == 26
    assert frame.attrs['sheet_name'] == 'GPExe Export'
