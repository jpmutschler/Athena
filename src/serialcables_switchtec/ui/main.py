"""NiceGUI page registration."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.pages.dashboard import dashboard_page
from serialcables_switchtec.ui.pages.discovery import discovery_page
from serialcables_switchtec.ui.pages.eye_diagram import eye_diagram_page
from serialcables_switchtec.ui.pages.ltssm_trace import ltssm_trace_page
from serialcables_switchtec.ui.pages.performance import performance_page
from serialcables_switchtec.ui.pages.ports import ports_page


def register_pages() -> None:
    """Register all NiceGUI pages."""

    @ui.page("/")
    def index() -> None:
        discovery_page()

    @ui.page("/dashboard")
    def dashboard() -> None:
        dashboard_page()

    @ui.page("/ports")
    def ports() -> None:
        ports_page()

    @ui.page("/eye")
    def eye() -> None:
        eye_diagram_page()

    @ui.page("/ltssm")
    def ltssm() -> None:
        ltssm_trace_page()

    @ui.page("/performance")
    def perf() -> None:
        performance_page()
