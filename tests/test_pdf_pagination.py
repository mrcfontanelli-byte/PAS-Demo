from pathlib import Path
import sys
import plotly.graph_objects as go

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modules.reporting import build_pdf_report


def count_pdf_pages(data: bytes) -> int:
    # Page objects are reliably emitted once per ReportLab page.
    return data.count(b"/Type /Page") - data.count(b"/Type /Pages")


def main() -> None:
    items = []
    for index in range(5):
        fig = go.Figure(go.Bar(x=["A", "B"], y=[index + 1, index + 2]))
        items.append({"title": f"Grafico {index + 1}", "figure_json": fig.to_json()})
    pdf = build_pdf_report(items, "Test paginazione", ["PAS v3.7.14"], charts_per_page=4)
    pages = count_pdf_pages(pdf)
    assert pages == 2, f"Attese 2 pagine, ottenute {pages}"
    assert pdf.startswith(b"%PDF"), "Output PDF non valido"
    print("PDF PAGINATION TEST OK: 5 grafici -> 2 pagine")


if __name__ == "__main__":
    main()
