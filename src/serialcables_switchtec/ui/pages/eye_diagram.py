"""Eye diagram capture and display page."""

from __future__ import annotations

import asyncio

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.eye_chart import eye_heatmap
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def eye_diagram_page() -> None:
    """Eye diagram capture controls and heatmap display."""
    from serialcables_switchtec.ui import state

    with page_layout("Eye Diagram", current_path="/eye"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Eye Diagram Capture").classes("text-h5 q-mb-md")

        # --- Capture Settings card ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Capture Settings").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end"):
                port_id_input = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                lane_id_input = ui.number(
                    label="Lane ID", value=0, min=0, max=143,
                ).classes("w-24")

            ui.separator().classes("q-my-sm")

            with ui.row().classes("q-gutter-sm items-end"):
                x_step_input = ui.number(
                    label="X Step", value=1, min=1, max=16,
                ).classes("w-24")
                y_step_input = ui.number(
                    label="Y Step", value=2, min=1, max=16,
                ).classes("w-24")
                step_interval_input = ui.number(
                    label="Step Interval (ms)", value=10, min=1, max=1000,
                ).classes("w-32")

            ui.separator().classes("q-my-sm")

            with ui.row().classes("q-gutter-sm items-end"):
                x_start_input = ui.number(
                    label="X Start", value=-64, min=-128, max=0,
                ).classes("w-24")
                x_end_input = ui.number(
                    label="X End", value=64, min=0, max=128,
                ).classes("w-24")
                y_start_input = ui.number(
                    label="Y Start", value=-255, min=-511, max=0,
                ).classes("w-24")
                y_end_input = ui.number(
                    label="Y End", value=255, min=0, max=511,
                ).classes("w-24")

            with ui.row().classes("q-mt-md q-gutter-sm"):
                start_btn = ui.button(
                    "Start Capture", icon="play_arrow",
                ).props("color=positive")
                cancel_btn = ui.button(
                    "Cancel", icon="stop",
                ).props("color=negative")
                cancel_btn.set_enabled(False)

        # --- Progress card ---
        progress_card = ui.card().classes("w-full q-pa-md q-mb-md")
        progress_card.set_visibility(False)
        with progress_card:
            progress_label = ui.label("Preparing capture...").classes(
                "text-subtitle2 q-mb-sm"
            )
            progress_bar = ui.linear_progress(value=0, show_value=False).props(
                "color=positive"
            )

        # --- Eye Diagram result card ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Eye Diagram").classes("text-h6 q-mb-sm")
            result_container = ui.column().classes("w-full")
            with result_container:
                ui.label(
                    "Start a capture to view the eye diagram."
                ).classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )

        # --- State for cancellation ---
        capture_state = {"cancelled": False}

        def _get_pixel_count(
            x_start: int, x_end: int, x_step: int,
            y_start: int, y_end: int, y_step: int,
        ) -> tuple[int, int, int]:
            """Compute x_count, y_count, and total pixel count."""
            x_count = ((x_end - x_start) // x_step) + 1
            y_count = ((y_end - y_start) // y_step) + 1
            return x_count, y_count, x_count * y_count

        async def _on_start() -> None:
            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port_id = int(port_id_input.value or 0)
            lane_id = int(lane_id_input.value or 0)
            x_step = int(x_step_input.value or 1)
            y_step = int(y_step_input.value or 2)
            step_interval = int(step_interval_input.value or 10)
            x_start = int(x_start_input.value or -64)
            x_end = int(x_end_input.value or 64)
            y_start = int(y_start_input.value or -255)
            y_end = int(y_end_input.value or 255)

            x_count, y_count, pixel_count = _get_pixel_count(
                x_start, x_end, x_step, y_start, y_end, y_step,
            )

            if pixel_count <= 0:
                ui.notify(
                    "Invalid range: pixel count must be positive",
                    type="negative", position="top",
                )
                return

            # Build the lane_mask: the API expects a list of 4 ints where
            # each int is a bitmask. For a single lane, set the bit in the
            # appropriate word.
            lane_mask = [0, 0, 0, 0]
            word_idx = lane_id // 32
            bit_idx = lane_id % 32
            if word_idx < 4:
                lane_mask[word_idx] = 1 << bit_idx

            # UI state: disable start, enable cancel
            start_btn.props("loading")
            start_btn.set_enabled(False)
            cancel_btn.set_enabled(True)
            capture_state["cancelled"] = False

            # Show progress
            progress_card.set_visibility(True)
            progress_label.set_text("Starting eye capture...")
            progress_bar.set_value(0)

            try:
                # Start the capture
                await run.io_bound(
                    dev.diagnostics.eye_start,
                    lane_mask,
                    x_start, x_end, x_step,
                    y_start, y_end, y_step,
                    step_interval,
                )
                ui.notify("Eye capture started", type="info", position="top")

                # Poll for completion with retries
                max_attempts = 600  # ~60s with 100ms sleep
                eye_data = None

                for attempt in range(max_attempts):
                    if capture_state["cancelled"]:
                        progress_label.set_text("Capture cancelled.")
                        break

                    progress_fraction = min((attempt + 1) / max_attempts, 0.95)
                    progress_bar.set_value(progress_fraction)
                    progress_label.set_text(
                        f"Fetching eye data... ({int(progress_fraction * 100)}%)"
                    )

                    try:
                        eye_data = await run.io_bound(
                            dev.diagnostics.eye_fetch, pixel_count,
                        )
                        # Successful fetch means capture is complete
                        break
                    except SwitchtecError:
                        # Not ready yet, wait and retry
                        await asyncio.sleep(0.1)

                if capture_state["cancelled"]:
                    return

                if eye_data is None:
                    ui.notify(
                        "Eye capture timed out",
                        type="warning", position="top",
                    )
                    progress_label.set_text("Capture timed out.")
                    return

                # Render the eye diagram
                progress_bar.set_value(1.0)
                progress_label.set_text("Capture complete.")

                result_container.clear()
                with result_container:
                    title = f"Eye Diagram - Port {port_id} Lane {eye_data.lane_id}"
                    eye_heatmap(
                        pixels=eye_data.pixels,
                        x_count=x_count,
                        y_count=y_count,
                        title=title,
                    )

                ui.notify("Eye diagram captured", type="positive", position="top")

            except SwitchtecError as exc:
                ui.notify(
                    f"Eye capture failed: {exc}",
                    type="negative", position="top",
                )
                progress_label.set_text(f"Capture failed: {exc}")
            finally:
                start_btn.props(remove="loading")
                start_btn.set_enabled(True)
                cancel_btn.set_enabled(False)

        async def _on_cancel() -> None:
            dev = state.get_active_device()
            if dev is None:
                return

            capture_state["cancelled"] = True
            cancel_btn.props("loading")

            try:
                await run.io_bound(dev.diagnostics.eye_cancel)
                ui.notify("Eye capture cancelled", type="info", position="top")
            except SwitchtecError as exc:
                ui.notify(
                    f"Cancel failed: {exc}",
                    type="negative", position="top",
                )
            finally:
                cancel_btn.props(remove="loading")
                cancel_btn.set_enabled(False)
                start_btn.set_enabled(True)
                start_btn.props(remove="loading")

        start_btn.on_click(_on_start)
        cancel_btn.on_click(_on_cancel)
