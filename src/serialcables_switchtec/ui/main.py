"""NiceGUI page registration."""

from __future__ import annotations

from pathlib import Path

from nicegui import app, ui

from serialcables_switchtec.ui.pages.dashboard import dashboard_page
from serialcables_switchtec.ui.pages.discovery import discovery_page
from serialcables_switchtec.ui.pages.evcntr import evcntr_page
from serialcables_switchtec.ui.pages.events import events_page
from serialcables_switchtec.ui.pages.eye_diagram import eye_diagram_page
from serialcables_switchtec.ui.pages.fabric import fabric_page
from serialcables_switchtec.ui.pages.firmware import firmware_page
from serialcables_switchtec.ui.pages.injection import injection_page
from serialcables_switchtec.ui.pages.ltssm_trace import ltssm_trace_page
from serialcables_switchtec.ui.pages.osa import osa_page
from serialcables_switchtec.ui.pages.performance import performance_page
from serialcables_switchtec.ui.pages.ports import ports_page
from serialcables_switchtec.ui.pages.ber_testing import ber_testing_page
from serialcables_switchtec.ui.pages.equalization import equalization_page
from serialcables_switchtec.ui.pages.fabric_view import fabric_view_page
from serialcables_switchtec.ui.pages.margin_testing import margin_testing_page
from serialcables_switchtec.ui.pages.workflow_builder import workflow_builder_page
from serialcables_switchtec.ui.pages.workflows import workflows_page

_STATIC_DIR = Path(__file__).parent / "static"


def register_pages() -> None:
    """Register all NiceGUI pages and static assets."""
    app.add_static_files("/static", str(_STATIC_DIR))

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

    @ui.page("/firmware")
    def firmware() -> None:
        firmware_page()

    @ui.page("/events")
    def events() -> None:
        events_page()

    @ui.page("/evcntr")
    def evcntr() -> None:
        evcntr_page()

    @ui.page("/performance")
    def perf() -> None:
        performance_page()

    @ui.page("/workflows")
    def workflows() -> None:
        workflows_page()

    @ui.page("/fabric")
    def fabric() -> None:
        fabric_page()

    @ui.page("/injection")
    def injection() -> None:
        injection_page()

    @ui.page("/ber")
    def ber() -> None:
        ber_testing_page()

    @ui.page("/equalization")
    def equalization() -> None:
        equalization_page()

    @ui.page("/osa")
    def osa() -> None:
        osa_page()

    @ui.page("/margin")
    def margin() -> None:
        margin_testing_page()

    @ui.page("/fabric-view")
    def fabric_view() -> None:
        fabric_view_page()

    @ui.page("/workflow-builder")
    def workflow_builder() -> None:
        workflow_builder_page()
