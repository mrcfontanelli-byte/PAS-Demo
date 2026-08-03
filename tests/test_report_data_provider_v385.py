from modules.data_provider import GPExeProvider

def test_gpexe_provider_exposes_report_contract():
    assert callable(GPExeProvider().load_report_data)
