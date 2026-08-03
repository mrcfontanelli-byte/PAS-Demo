from pathlib import Path


def test_dashboard_card_label_removed_and_report_colors_strengthened():
    root = Path(__file__).resolve().parents[1]
    app = (root / "app.py").read_text(encoding="utf-8")
    reporting = (root / "modules" / "reporting.py").read_text(encoding="utf-8")

    card_fragment = (
        "margin-top:0.35rem;'>Confronto giocatori del giorno</div>"
    )
    assert card_fragment not in app
    assert "REPORT_PLAYER_BAR_ALPHA = 0.72" in reporting
    assert "REPORT_SUMMARY_BAR_ALPHA = 0.88" in reporting
    assert "bar_alpha = (" in reporting
