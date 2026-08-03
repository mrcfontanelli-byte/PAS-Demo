from pathlib import Path
import pandas as pd

from modules.config import PLAYERS_HELLAS, SEASON_PHASES_2526

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "Database Hellas 25-26.xlsx"
APP = ROOT / "app.py"
LOADER = ROOT / "modules" / "data_loader.py"


def _valid_match_rows() -> pd.DataFrame:
    data = pd.read_excel(DB, sheet_name="Database")
    data.columns = data.columns.astype(str).str.strip()
    for column in ["Athlete", "Drill", "Season Phase"]:
        data[column] = data[column].astype("string").str.strip()
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    return data[
        data["Season Phase"].isin(SEASON_PHASES_2526)
        & data["Drill"].eq("Match")
        & data["Athlete"].ne("Team Average")
    ].copy()


def test_database_contains_valid_match_player_outside_static_roster():
    matches = _valid_match_rows()
    unlisted = set(matches["Athlete"].dropna().astype(str)) - set(PLAYERS_HELLAS)
    assert "KURTI ADI" in unlisted


def test_loader_supports_disabling_static_roster_filter():
    source = LOADER.read_text(encoding="utf-8")
    assert "filter_configured_roster: bool = True" in source
    assert "if filter_configured_roster:" in source


def test_match_analysis_uses_unfiltered_match_source():
    source = APP.read_text(encoding="utf-8")
    assert "match_source = data_provider.load_performance_data(" in source
    assert "filter_configured_roster=False" in source
    assert 'match_raw = match_source[' in source


def test_match_player_widget_key_depends_on_match_date():
    source = APP.read_text(encoding="utf-8")
    assert '"match_players_"' in source
    assert 'selected_match_date.strftime("%Y%m%d")' in source
