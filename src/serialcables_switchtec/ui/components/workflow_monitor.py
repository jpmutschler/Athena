"""Rich real-time workflow monitor UI component.

Replaces ``RecipeStepper`` in workflow context with progress bar,
elapsed time, pass/fail counters, and recipe-specific metric cards.
"""

from __future__ import annotations

import time

from nicegui import ui

from serialcables_switchtec.core.workflows.models import RecipeResult, StepStatus
from serialcables_switchtec.core.workflows.monitor_state import MonitorState, MonitorStepState
from serialcables_switchtec.core.workflows.workflow_models import WorkflowSummary
from serialcables_switchtec.ui.components.monitor_metrics import render_metrics
from serialcables_switchtec.ui.theme import COLORS

_STATUS_ICONS: dict[StepStatus, tuple[str, str]] = {
    StepStatus.RUNNING: ("hourglass_empty", COLORS.blue),
    StepStatus.PASS: ("check_circle", COLORS.success),
    StepStatus.FAIL: ("cancel", COLORS.error),
    StepStatus.WARN: ("warning", COLORS.warning),
    StepStatus.INFO: ("info", COLORS.text_secondary),
    StepStatus.SKIP: ("skip_next", COLORS.text_muted),
}


class WorkflowMonitor:
    """Real-time workflow progress component with metric cards."""

    def __init__(self, container: ui.column) -> None:
        self._container = container
        self._state = MonitorState()

        # UI references — populated in start()
        self._elapsed_label: ui.label | None = None
        self._progress_bar: ui.linear_progress | None = None
        self._progress_text: ui.label | None = None
        self._current_step_label: ui.label | None = None
        self._pass_label: ui.label | None = None
        self._fail_label: ui.label | None = None
        self._warn_label: ui.label | None = None
        self._live_metrics_container: ui.column | None = None
        self._completed_container: ui.column | None = None

    def start(
        self,
        workflow_name: str,
        total_steps: int,
        step_keys: list[tuple[int, str]],
    ) -> None:
        """Initialize the monitor with workflow metadata and build the skeleton."""
        self._state.start(workflow_name, step_keys)

        with self._container:
            # Progress row
            with ui.row().classes("items-center q-gutter-sm w-full"):
                self._elapsed_label = ui.label("0.0s").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary}; min-width: 60px;"
                )
                self._progress_bar = ui.linear_progress(
                    value=0, show_value=False,
                ).classes("flex-grow").props("instant-feedback")
                self._progress_text = ui.label(f"0/{total_steps}").classes(
                    "text-subtitle2"
                ).style(f"color: {COLORS.text_secondary};")

            # Current step label
            self._current_step_label = ui.label("Starting...").classes(
                "text-subtitle1 text-bold"
            ).style(f"color: {COLORS.accent};")

            # Pass/Fail/Warn counter row
            with ui.row().classes("q-gutter-md q-mb-sm"):
                self._pass_label = ui.label("Pass: 0").style(
                    f"color: {COLORS.success};"
                )
                self._fail_label = ui.label("Fail: 0").style(
                    f"color: {COLORS.error};"
                )
                self._warn_label = ui.label("Warn: 0").style(
                    f"color: {COLORS.warning};"
                )

            # Live metrics container
            self._live_metrics_container = ui.column().classes("w-full q-mb-sm")

            ui.separator().classes("q-my-sm")

            # Completed steps container
            self._completed_container = ui.column().classes("w-full")

    def update(self, result: RecipeResult) -> None:
        """Process a new result and update the display."""
        previous_step = self._state.ingest(result)

        # Update progress bar
        total = self._state.total_steps
        completed = self._state.completed_count
        if self._progress_bar is not None and total > 0:
            self._progress_bar.set_value(completed / total)
        if self._progress_text is not None:
            self._progress_text.set_text(f"{completed}/{total}")

        # Update elapsed
        if self._elapsed_label is not None:
            self._elapsed_label.set_text(f"{self._state.elapsed_s:.1f}s")

        # Update counters
        totals = self._state.overall_pass_fail
        if self._pass_label is not None:
            self._pass_label.set_text(f"Pass: {totals['passed']}")
        if self._fail_label is not None:
            self._fail_label.set_text(f"Fail: {totals['failed']}")
        if self._warn_label is not None:
            self._warn_label.set_text(f"Warn: {totals['warnings']}")

        # Update current step label
        step_state = self._state.steps.get(self._state.current_step_index)
        if step_state is not None and self._current_step_label is not None:
            self._current_step_label.set_text(
                f"[{step_state.step_index + 1}/{total}] {step_state.recipe_name}"
            )

        # Render completed step as expansion panel on transition
        if previous_step is not None:
            prev_state = self._state.steps.get(previous_step)
            if prev_state is not None and self._completed_container is not None:
                self._render_completed_step(prev_state)

        # Update live metrics
        if step_state is not None and self._live_metrics_container is not None:
            self._live_metrics_container.clear()
            data = step_state.extracted_data
            if data:
                render_metrics(step_state.recipe_key, data, self._live_metrics_container)

    def finish(self, summary: WorkflowSummary) -> None:
        """Finalize: render the last step and show the summary banner."""
        # Finish the current step
        current_idx = self._state.current_step_index
        if current_idx >= 0 and current_idx in self._state.steps:
            step_state = self._state.steps[current_idx]
            if step_state.finished_at == 0.0:
                step_state.finished_at = time.monotonic()
            if self._completed_container is not None:
                self._render_completed_step(step_state)

        self._state.finished = True

        # Clear live metrics
        if self._live_metrics_container is not None:
            self._live_metrics_container.clear()

        # Update current step label
        if self._current_step_label is not None:
            self._current_step_label.set_text("Completed")

        # Update progress to 100%
        if self._progress_bar is not None:
            self._progress_bar.set_value(1.0)
        total = self._state.total_steps
        if self._progress_text is not None:
            self._progress_text.set_text(f"{total}/{total}")

        # Render summary banner
        self._render_summary_banner(summary)

    # -- Internal rendering ------------------------------------------------

    def _render_completed_step(self, step_state: MonitorStepState) -> None:
        """Render a finished step as a collapsible expansion panel."""
        counts = step_state.pass_fail_counts
        if counts["failed"] > 0:
            icon = "cancel"
            color = COLORS.error
        elif counts["warnings"] > 0:
            icon = "warning"
            color = COLORS.warning
        else:
            icon = "check_circle"
            color = COLORS.success

        label = (
            f"[{step_state.step_index + 1}/{self._state.total_steps}] "
            f"{step_state.recipe_name} — "
            f"{counts['passed']}P {counts['failed']}F {counts['warnings']}W "
            f"({step_state.elapsed_s:.1f}s)"
        )

        with self._completed_container:
            with ui.expansion(label, icon=icon).classes("w-full").style(
                f"color: {color};"
            ):
                # Result detail lines
                for r in step_state.results:
                    if r.status in (StepStatus.INFO,):
                        continue
                    icon_name, icon_color = _STATUS_ICONS.get(
                        r.status, ("help", COLORS.text_muted)
                    )
                    with ui.row().classes("items-center q-gutter-xs"):
                        ui.icon(icon_name).style(
                            f"color: {icon_color}; font-size: 1.1em;"
                        )
                        step_text = r.step
                        if " > " in step_text:
                            step_text = step_text.split(" > ", 1)[1]
                        ui.label(step_text).classes("text-caption").style(
                            f"color: {COLORS.text_primary};"
                        )
                        if r.detail:
                            ui.label(r.detail).classes("text-caption").style(
                                f"color: {COLORS.text_secondary};"
                            )

                # Metric cards
                data = step_state.extracted_data
                if data:
                    metrics_col = ui.column().classes("q-mt-sm")
                    render_metrics(step_state.recipe_key, data, metrics_col)

    def _render_summary_banner(self, summary: WorkflowSummary) -> None:
        """Render the final workflow summary banner."""
        if summary.aborted:
            banner_color = COLORS.warning
            banner_icon = "cancel"
            banner_text = "Aborted"
        elif any(
            s.recipe_summary and s.recipe_summary.failed > 0
            for s in summary.step_summaries
        ):
            banner_color = COLORS.error
            banner_icon = "error"
            banner_text = "Failed"
        else:
            banner_color = COLORS.success
            banner_icon = "check_circle"
            banner_text = "Passed"

        with self._container:
            ui.separator().classes("q-my-sm")
            with ui.card().classes("w-full q-pa-md").style(
                f"border: 2px solid {banner_color}; background: {banner_color}15;"
            ):
                with ui.row().classes("items-center q-gutter-md"):
                    ui.icon(banner_icon).classes("text-h4").style(
                        f"color: {banner_color};"
                    )
                    with ui.column():
                        ui.label(
                            f"{summary.workflow_name}: {banner_text}"
                        ).classes("text-h6 text-bold").style(
                            f"color: {banner_color};"
                        )
                        with ui.row().classes("q-gutter-md"):
                            ui.label(
                                f"Recipes: {summary.completed_recipes}/{summary.total_recipes}"
                            ).style(f"color: {COLORS.text_primary};")
                            skipped = sum(
                                1 for s in summary.step_summaries if s.skipped
                            )
                            if skipped:
                                ui.label(f"Skipped: {skipped}").style(
                                    f"color: {COLORS.text_muted};"
                                )
                            ui.label(f"Time: {summary.elapsed_s:.1f}s").style(
                                f"color: {COLORS.text_secondary};"
                            )
