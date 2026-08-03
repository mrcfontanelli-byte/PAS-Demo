from pathlib import Path

source = (Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8")

assert 'st.sidebar.columns(2, gap="small")' in source
assert 'with st.popover(' in source
assert 'key="match_analysis_mode"' in source
assert 'selected_match_label = st.sidebar.selectbox' in source
assert 'selected_match_players = st.sidebar.multiselect' in source
assert 'selected_match_metrics = st.sidebar.multiselect' in source
assert 'comparison_matches = st.sidebar.multiselect' in source
assert 'comparison_subject = st.sidebar.selectbox' in source
assert 'comparison_metrics = st.sidebar.multiselect' in source
assert 'match_tab, comparison_tab = st.tabs' not in source
print("SIDEBAR LAYOUT TEST OK")
