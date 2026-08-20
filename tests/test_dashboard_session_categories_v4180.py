from __future__ import annotations

import pandas as pd

from modules.data_loader import (
    aggregate_player_day,
    normalize_dashboard_session_categories,
)
from modules.session_categories import (
    DASHBOARD_SESSION_CATEGORIES,
    canonical_session_category,
)
from pas_connect.mapper import map_category, map_team_session
from pas_connect.rest_mapper import map_rest_team_session
from pas_connect.dashboard_sessions import (
    canonical_gpexe_dashboard_category,
    classify_gpexe_team_session,
)


def test_historical_typo_maps_to_single_dashboard_category():
    values = pd.Series(["Different Training", "Different Traning"])
    normalized = values.map(canonical_session_category)
    assert normalized.tolist() == ["Different Training", "Different Training"]
    assert normalized.nunique() == 1
    assert DASHBOARD_SESSION_CATEGORIES == (
        "Full Training", "Individual Training", "Return to Play",
        "Active Recovery", "Different Training", "Match", "Recovery",
    )


def test_alias_rows_share_one_logical_category_without_double_category_count():
    frame = pd.DataFrame({
        "Date": pd.to_datetime(["2026-01-01", "2026-01-01"]),
        "Athlete": ["ANON", "ANON"],
        "Drill": ["Different Training", "Different Traning"],
        "distance (m)": [100.0, 100.0],
    })
    normalized = normalize_dashboard_session_categories(frame)
    assert frame["Drill"].tolist() == ["Different Training", "Different Traning"]
    assert normalized["Drill"].unique().tolist() == ["Different Training"]
    assert len(normalized) == 1
    assert aggregate_player_day(normalized)["distance (m)"].tolist() == [100.0]


def test_alias_normalization_preserves_distinct_performance_records():
    frame = pd.DataFrame({
        "Drill": ["Different Training", "Different Traning"],
        "distance (m)": [100.0, 50.0],
    })
    normalized = normalize_dashboard_session_categories(frame)
    assert normalized["Drill"].unique().tolist() == ["Different Training"]
    assert normalized["distance (m)"].sum() == 150.0


def test_gpexe_mappers_emit_only_canonical_label_and_preserve_rest_raw():
    assert map_category({"id": 1, "name": "Different Traning"})["category_name"] == (
        "Different Training"
    )
    mapped = map_team_session({
        "id": 2, "team": 543, "name": "Different Traning",
        "category": {"id": 1, "name": "Different Traning"},
    })
    assert mapped["session_name"] == "Different Training"

    raw = {
        "general": {"id": 2, "team": 543, "nature": "S"},
        "header": {"start_timestamp": "2026-01-01", "match": {}},
        "timing": {}, "category": {"id": 1, "name": "Different Traning"},
        "drill": {}, "status": {},
    }
    rest = map_rest_team_session(raw)
    assert rest["category"]["name"] == "Different Training"
    assert rest["raw"]["category"]["name"] == "Different Traning"


def _session(session_id=1, name="FULL TRAINING"):
    return {"provider_session_id": session_id, "session_name": name}


def _athlete_row(requested, linked, drill=None):
    import json
    return {
        "provider_session_id": requested, "drill_id": drill,
        "raw_json": json.dumps({"payload": {"teamsession": linked, "drill": drill}}),
    }


def test_full_training_main_is_dashboard_eligible_and_casing_is_controlled():
    result = classify_gpexe_team_session(
        _session(144742, "  full   training "),
        [_athlete_row(144742, 144742)],
    )
    assert result.technical_level == "MAIN_SESSION"
    assert result.canonical_dashboard_category == "Full Training"
    assert result.dashboard_eligible is True


def test_exercise_container_and_drill_child_are_excluded():
    container = classify_gpexe_team_session(
        _session(144761, "EXERCISE"), [], structurally_referenced_by_child=True,
    )
    child = classify_gpexe_team_session(
        _session(144769, "EXERCISE"), [_athlete_row(144769, 144761, 6)],
    )
    assert container.technical_level == "EXERCISE_CONTAINER"
    assert child.technical_level == "DRILL_CHILD"
    assert not container.dashboard_eligible and not child.dashboard_eligible


def test_ambiguous_and_unknown_main_are_excluded_without_semantic_mapping():
    ambiguous = classify_gpexe_team_session(_session(name="EXERCISE"), [])
    unknown_main = classify_gpexe_team_session(
        _session(name="EXERCISE"), [_athlete_row(1, 1)],
    )
    assert ambiguous.technical_level == "AMBIGUOUS"
    assert unknown_main.technical_level == "MAIN_SESSION"
    assert ambiguous.dashboard_eligible is False
    assert unknown_main.canonical_dashboard_category is None
    assert canonical_gpexe_dashboard_category("Different Traning") == "Different Training"
    assert canonical_gpexe_dashboard_category("[FULL TRAINING] 20 AUG 2026") == "Full Training"
    assert canonical_gpexe_dashboard_category(" [RETURN TO PLAY] note ") == "Return to Play"
    assert canonical_gpexe_dashboard_category("[DIFFERENT TRANING] note") == "Different Training"
    assert canonical_gpexe_dashboard_category("prefix [FULL TRAINING]") is None
    assert canonical_gpexe_dashboard_category("[EXERCISE] Full Training") is None
    assert canonical_gpexe_dashboard_category("[FULL TRAINING note") is None
    assert canonical_gpexe_dashboard_category("EXERCISE") is None
