"""Recipe stepper component for live step-by-step progress display."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.core.workflows.models import RecipeResult, RecipeSummary, StepStatus
from serialcables_switchtec.ui.theme import COLORS

_STATUS_ICONS: dict[StepStatus, tuple[str, str]] = {
    StepStatus.RUNNING: ("hourglass_empty", COLORS.blue),
    StepStatus.PASS: ("check_circle", COLORS.success),
    StepStatus.FAIL: ("cancel", COLORS.error),
    StepStatus.WARN: ("warning", COLORS.warning),
    StepStatus.INFO: ("info", COLORS.text_secondary),
    StepStatus.SKIP: ("skip_next", COLORS.text_muted),
}


class RecipeStepper:
    """Renders recipe step results as they stream in."""

    def __init__(self, container: ui.column) -> None:
        self._container = container

    def render_results(self, results: list[RecipeResult]) -> None:
        """Render all results accumulated so far."""
        self._container.clear()
        with self._container:
            for result in results:
                icon_name, color = _STATUS_ICONS.get(
                    result.status, ("help", COLORS.text_muted)
                )
                with ui.row().classes("items-center q-gutter-sm q-mb-xs"):
                    if result.status == StepStatus.RUNNING:
                        ui.spinner(size="sm").style(f"color: {color};")
                    else:
                        ui.icon(icon_name).style(f"color: {color}; font-size: 1.3em;")

                    step_label = f"[{result.step_index + 1}/{result.total_steps}] {result.step}"
                    ui.label(step_label).classes("text-subtitle2").style(
                        f"color: {COLORS.text_primary};"
                    )

                    if result.detail:
                        ui.label(result.detail).classes("text-caption").style(
                            f"color: {COLORS.text_secondary};"
                        )

    def render_summary(self, summary: RecipeSummary) -> None:
        """Render the final summary banner."""
        with self._container:
            ui.separator().classes("q-my-sm")

            # Determine overall verdict
            if summary.aborted:
                banner_color = COLORS.warning
                banner_icon = "cancel"
                banner_text = "Aborted"
            elif summary.failed > 0:
                banner_color = COLORS.error
                banner_icon = "error"
                banner_text = "Failed"
            elif summary.warnings > 0:
                banner_color = COLORS.warning
                banner_icon = "warning"
                banner_text = "Passed with Warnings"
            else:
                banner_color = COLORS.success
                banner_icon = "check_circle"
                banner_text = "Passed"

            with ui.card().classes("w-full q-pa-md").style(
                f"border: 2px solid {banner_color}; background: {banner_color}15;"
            ):
                with ui.row().classes("items-center q-gutter-md"):
                    ui.icon(banner_icon).classes("text-h4").style(
                        f"color: {banner_color};"
                    )
                    with ui.column():
                        ui.label(f"{summary.recipe_name}: {banner_text}").classes(
                            "text-h6 text-bold"
                        ).style(f"color: {banner_color};")
                        with ui.row().classes("q-gutter-md"):
                            ui.label(f"Passed: {summary.passed}").style(
                                f"color: {COLORS.success};"
                            )
                            ui.label(f"Failed: {summary.failed}").style(
                                f"color: {COLORS.error};"
                            )
                            ui.label(f"Warnings: {summary.warnings}").style(
                                f"color: {COLORS.warning};"
                            )
                            ui.label(f"Skipped: {summary.skipped}").style(
                                f"color: {COLORS.text_muted};"
                            )
                            ui.label(f"Time: {summary.elapsed_s:.1f}s").style(
                                f"color: {COLORS.text_secondary};"
                            )
