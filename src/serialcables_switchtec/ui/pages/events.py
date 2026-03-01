"""Events page for viewing and managing Switchtec device events."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def _event_color(count: int) -> str:
    """Return a color based on event count."""
    if count == 0:
        return COLORS.success
    if count < 10:
        return COLORS.warning
    return COLORS.error


def events_page() -> None:
    """Events page showing event summary with refresh and clear controls."""
    from serialcables_switchtec.ui import state

    with page_layout("Events", current_path="/events"):
        if not state.is_connected():
            show_disconnected()
            return

        summary = state.get_summary()
        if summary is None:
            show_disconnected()
            return

        ui.label("Event Management").classes("text-h5 q-mb-md")

        # --- Summary cards ---
        with ui.row().classes("w-full q-gutter-md q-mb-lg"):
            with ui.card().classes("col q-pa-md"):
                ui.label("Total Events").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                total_label = ui.label("--").classes("text-h4").style(
                    f"color: {COLORS.text_muted};"
                )

            with ui.card().classes("col q-pa-md"):
                ui.label("Global Events").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                global_label = ui.label("--").classes("text-h4").style(
                    f"color: {COLORS.text_muted};"
                )

            with ui.card().classes("col q-pa-md"):
                ui.label("Partition Events").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                partition_label = ui.label("--").classes("text-h4").style(
                    f"color: {COLORS.text_muted};"
                )

            with ui.card().classes("col q-pa-md"):
                ui.label("PFF Events").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                pff_label = ui.label("--").classes("text-h4").style(
                    f"color: {COLORS.text_muted};"
                )

        # --- Action buttons ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Actions").classes("text-h6 q-mb-sm")
            status_label = ui.label("").classes("q-mb-sm")
            status_label.set_visibility(False)

            with ui.row().classes("q-gutter-sm"):
                refresh_btn = ui.button("Refresh", icon="refresh").props(
                    "color=primary"
                )
                clear_btn = ui.button(
                    "Clear All Events", icon="delete_sweep",
                ).props("color=negative")

        # --- Event breakdown table ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Event Breakdown").classes("text-h6 q-mb-sm")
            event_table = ui.table(
                columns=[
                    {"name": "category", "label": "Category", "field": "category", "align": "left"},
                    {"name": "count", "label": "Count", "field": "count", "align": "right"},
                    {"name": "status", "label": "Status", "field": "status", "align": "center"},
                ],
                rows=[],
                row_key="category",
            ).classes("w-full")

        # --- Clear confirmation dialog ---
        clear_dialog = ui.dialog()
        with clear_dialog, ui.card().classes("q-pa-md"):
            ui.label("Confirm Clear All Events").classes("text-h6 q-mb-sm")
            ui.label(
                "This will clear all event counters on the device. "
                "This action cannot be undone."
            ).style(f"color: {COLORS.text_secondary};")
            with ui.row().classes("q-mt-md q-gutter-sm justify-end"):
                ui.button("Cancel", on_click=clear_dialog.close).props(
                    "flat color=grey"
                )
                confirm_clear_btn = ui.button(
                    "Clear All", icon="delete_sweep",
                ).props("color=negative")

        def _show_status(msg: str, is_error: bool = False) -> None:
            status_label.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            status_label.style(f"color: {color};")
            status_label.set_visibility(True)

        def _update_summary_display(
            total: int,
            global_count: int,
            partition_count: int,
            pff_count: int,
        ) -> None:
            total_color = _event_color(total)
            total_label.set_text(str(total))
            total_label.style(f"color: {total_color};")

            global_color = _event_color(global_count)
            global_label.set_text(str(global_count))
            global_label.style(f"color: {global_color};")

            part_color = _event_color(partition_count)
            partition_label.set_text(str(partition_count))
            partition_label.style(f"color: {part_color};")

            pff_color = _event_color(pff_count)
            pff_label.set_text(str(pff_count))
            pff_label.style(f"color: {pff_color};")

            event_table.rows = [
                {
                    "category": "Global Events",
                    "count": global_count,
                    "status": "Clean" if global_count == 0 else "Active",
                },
                {
                    "category": "Partition Events",
                    "count": partition_count,
                    "status": "Clean" if partition_count == 0 else "Active",
                },
                {
                    "category": "PFF Events",
                    "count": pff_count,
                    "status": "Clean" if pff_count == 0 else "Active",
                },
            ]
            event_table.update()

        async def _load_event_summary() -> None:
            dev = state.get_active_device()
            if dev is None:
                return
            try:
                result = await run.io_bound(dev.events.get_summary)
                _update_summary_display(
                    result.total_count,
                    result.global_events,
                    result.partition_events,
                    result.pff_events,
                )
            except SwitchtecError as exc:
                _show_status(f"Failed to load events: {exc}", is_error=True)

        async def _on_refresh() -> None:
            refresh_btn.props("loading")
            try:
                await _load_event_summary()
                _show_status("Event summary refreshed")
                ui.notify("Event summary refreshed", type="positive", position="top")
            except SwitchtecError as exc:
                _show_status(f"Refresh failed: {exc}", is_error=True)
                ui.notify(f"Refresh failed: {exc}", type="negative", position="top")
            finally:
                refresh_btn.props(remove="loading")

        async def _on_clear_all() -> None:
            clear_dialog.close()
            clear_btn.props("loading")
            try:
                dev = state.get_active_device()
                if dev is None:
                    _show_status("No device connected", is_error=True)
                    return
                await run.io_bound(dev.events.clear_all)
                _show_status("All events cleared")
                ui.notify("All events cleared", type="positive", position="top")
                await _load_event_summary()
            except SwitchtecError as exc:
                _show_status(f"Clear failed: {exc}", is_error=True)
                ui.notify(f"Clear failed: {exc}", type="negative", position="top")
            finally:
                clear_btn.props(remove="loading")

        def _open_clear_dialog() -> None:
            clear_dialog.open()

        # Wire button handlers
        refresh_btn.on_click(_on_refresh)
        clear_btn.on_click(_open_clear_dialog)
        confirm_clear_btn.on_click(_on_clear_all)

        # Load initial data
        ui.timer(0.1, _load_event_summary, once=True)
