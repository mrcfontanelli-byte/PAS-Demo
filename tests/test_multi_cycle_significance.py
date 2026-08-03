from pathlib import Path


def test_multi_cycle_pairwise_rows_are_treated_as_lists():
    source = Path(__file__).resolve().parents[1].joinpath("app.py").read_text(encoding="utf-8")
    assert 'level_rows = test_by_level.get(str(level), [])' in source
    assert 'significant_level_rows = [' in source
    assert 'row = test_by_level.get(level)' not in source
