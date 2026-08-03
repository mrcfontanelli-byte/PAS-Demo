from modules.data_provider import GPExeProvider

def test_gpexe_provider_exposes_match_analysis_contract():
    assert callable(GPExeProvider().load_match_analysis_data)

def test_app_routes_match_analysis_through_provider_contract():
    from pathlib import Path
    app=(Path(__file__).resolve().parents[1]/"app.py").read_text(encoding="utf-8")
    assert "load_match_analysis_data(" in app
