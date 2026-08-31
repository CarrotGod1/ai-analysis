import uuid
from pathlib import Path

import plotly.io as pio

from config import settings


class ChartService:
    def __init__(self):
        self.charts_path = settings.charts_path

    def save_html(self, html_content: str, filename: str | None = None) -> tuple[str, str]:
        chart_id = filename or str(uuid.uuid4())[:12]
        if not chart_id.endswith(".html"):
            chart_id += ".html"
        path = self.charts_path / chart_id
        path.write_text(html_content, encoding="utf-8")
        return chart_id, str(path)

    def get_html(self, chart_id: str) -> str | None:
        path = self.charts_path / chart_id
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def list_charts(self) -> list[str]:
        return [f.name for f in self.charts_path.glob("*.html")]

    def delete_chart(self, chart_id: str) -> bool:
        path = self.charts_path / chart_id
        if path.exists():
            path.unlink()
            return True
        return False

    def fig_to_html(self, fig) -> str:
        return pio.to_html(fig, full_html=True, include_plotlyjs="cdn")


chart_service = ChartService()
