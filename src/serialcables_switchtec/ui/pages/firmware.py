"""Firmware management page."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.firmware import FwPartSummary
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def _boot_phase_color(phase: str) -> str:
    """Return a status color based on boot phase string."""
    if phase in ("Main Firmware", "FW"):
        return COLORS.success
    if phase == "BL2":
        return COLORS.warning
    return COLORS.error


def _partition_rows(summary: FwPartSummary) -> list[dict[str, str]]:
    """Build table rows from the firmware partition summary."""
    partition_names = [
        ("Boot", summary.boot),
        ("Map", summary.map),
        ("Image", summary.img),
        ("Config", summary.cfg),
        ("NVLog", summary.nvlog),
        ("SEEPROM", summary.seeprom),
        ("Key", summary.key),
        ("BL2", summary.bl2),
        ("RIoT Core", summary.riot),
    ]
    rows: list[dict[str, str]] = []
    for name, part_info in partition_names:
        for slot_label, img in [("Active", part_info.active), ("Inactive", part_info.inactive)]:
            if img is None:
                continue
            rows = [
                *rows,
                {
                    "partition": name,
                    "slot": slot_label,
                    "version": img.version or "-",
                    "generation": img.generation,
                    "valid": "Yes" if img.valid else "No",
                    "running": "Yes" if img.running else "No",
                    "read_only": "Yes" if img.read_only else "No",
                    "addr": f"0x{img.partition_addr:08X}",
                    "length": f"0x{img.partition_len:08X}",
                },
            ]
    return rows


_PARTITION_COLUMNS = [
    {"name": "partition", "label": "Partition", "field": "partition", "align": "left"},
    {"name": "slot", "label": "Slot", "field": "slot", "align": "left"},
    {"name": "version", "label": "Version", "field": "version", "align": "left"},
    {"name": "generation", "label": "Gen", "field": "generation", "align": "center"},
    {"name": "valid", "label": "Valid", "field": "valid", "align": "center"},
    {"name": "running", "label": "Running", "field": "running", "align": "center"},
    {"name": "read_only", "label": "RO", "field": "read_only", "align": "center"},
    {"name": "addr", "label": "Address", "field": "addr", "align": "right"},
    {"name": "length", "label": "Length", "field": "length", "align": "right"},
]


def firmware_page() -> None:
    """Firmware management page showing version, partitions, and boot config."""
    from serialcables_switchtec.ui import state

    with page_layout("Firmware", current_path="/firmware"):
        if not state.is_connected():
            show_disconnected()
            return

        summary = state.get_summary()
        if summary is None:
            show_disconnected()
            return

        ui.label("Firmware Management").classes("text-h5 q-mb-md")

        # --- Top summary cards ---
        with ui.row().classes("w-full q-gutter-md q-mb-lg"):
            # Firmware version (large, prominent)
            with ui.card().classes("col q-pa-md"):
                ui.label("Firmware Version").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                fw_version_label = ui.label(summary.fw_version).classes(
                    "text-h4"
                ).style(f"color: {COLORS.accent};")

            # Boot phase indicator
            phase_color = _boot_phase_color(summary.boot_phase)
            with ui.card().classes("col q-pa-md"):
                ui.label("Boot Phase").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                boot_phase_label = ui.label(summary.boot_phase).classes(
                    "text-h4"
                ).style(f"color: {phase_color};")

            # Boot RO status card
            with ui.card().classes("col q-pa-md"):
                ui.label("Boot Read-Only").classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                boot_ro_label = ui.label("Loading...").classes(
                    "text-h4"
                ).style(f"color: {COLORS.text_muted};")

        # --- Action buttons ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Actions").classes("text-h6 q-mb-sm")
            status_label = ui.label("").classes("q-mb-sm")
            status_label.set_visibility(False)

            with ui.row().classes("q-gutter-sm"):
                refresh_btn = ui.button("Refresh", icon="refresh").props(
                    "color=primary"
                )
                toggle_btn = ui.button(
                    "Toggle Active Partition", icon="swap_horiz",
                ).props("color=warning")
                boot_ro_btn = ui.button(
                    "Toggle Boot RO", icon="lock",
                ).props("color=negative")

        # --- Partition summary table ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Partition Summary").classes("text-h6 q-mb-sm")
            partition_table = ui.table(
                columns=_PARTITION_COLUMNS,
                rows=[],
                row_key="partition",
            ).classes("w-full")

        # --- Confirmation dialogs ---
        toggle_dialog = ui.dialog()
        with toggle_dialog, ui.card().classes("q-pa-md"):
            ui.label("Confirm Partition Toggle").classes("text-h6 q-mb-sm")
            ui.label(
                "This will toggle the active firmware and config partitions. "
                "The device may need to be reset for changes to take effect."
            ).style(f"color: {COLORS.text_secondary};")
            with ui.row().classes("q-mt-md q-gutter-sm justify-end"):
                ui.button("Cancel", on_click=toggle_dialog.close).props(
                    "flat color=grey"
                )
                confirm_toggle_btn = ui.button(
                    "Toggle", icon="swap_horiz",
                ).props("color=warning")

        boot_ro_dialog = ui.dialog()
        with boot_ro_dialog, ui.card().classes("q-pa-md"):
            ui.label("Confirm Boot RO Change").classes("text-h6 q-mb-sm")
            boot_ro_dialog_text = ui.label(
                "This will change the boot partition read-only state."
            ).style(f"color: {COLORS.text_secondary};")
            with ui.row().classes("q-mt-md q-gutter-sm justify-end"):
                ui.button("Cancel", on_click=boot_ro_dialog.close).props(
                    "flat color=grey"
                )
                confirm_boot_ro_btn = ui.button(
                    "Confirm", icon="lock",
                ).props("color=negative")

        # --- State for tracking boot RO ---
        current_boot_ro: dict[str, bool | None] = {"value": None}

        def _show_status(msg: str, is_error: bool = False) -> None:
            status_label.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            status_label.style(f"color: {color};")
            status_label.set_visibility(True)

        def _update_boot_ro_display(is_ro: bool) -> None:
            current_boot_ro["value"] = is_ro
            ro_text = "Enabled" if is_ro else "Disabled"
            ro_color = COLORS.warning if is_ro else COLORS.success
            boot_ro_label.set_text(ro_text)
            boot_ro_label.style(f"color: {ro_color};")
            icon = "lock" if is_ro else "lock_open"
            boot_ro_btn.props(f'icon="{icon}"')
            btn_label = "Disable Boot RO" if is_ro else "Enable Boot RO"
            boot_ro_btn.set_text(btn_label)

        async def _load_firmware_data() -> None:
            dev = state.get_active_device()
            if dev is None:
                return
            try:
                part_summary = await run.io_bound(dev.firmware.get_part_summary)
                rows = _partition_rows(part_summary)
                partition_table.rows = rows
                partition_table.update()
                _update_boot_ro_display(part_summary.is_boot_ro)
            except SwitchtecError as exc:
                _show_status(f"Failed to load firmware data: {exc}", is_error=True)

        async def _on_refresh() -> None:
            refresh_btn.props("loading")
            try:
                refreshed = await run.io_bound(state.refresh_summary)
                if refreshed is not None:
                    fw_version_label.set_text(refreshed.fw_version)
                    new_phase_color = _boot_phase_color(refreshed.boot_phase)
                    boot_phase_label.set_text(refreshed.boot_phase)
                    boot_phase_label.style(f"color: {new_phase_color};")
                await _load_firmware_data()
                _show_status("Firmware data refreshed")
                ui.notify("Firmware data refreshed", type="positive", position="top")
            except SwitchtecError as exc:
                _show_status(f"Refresh failed: {exc}", is_error=True)
                ui.notify(f"Refresh failed: {exc}", type="negative", position="top")
            finally:
                refresh_btn.props(remove="loading")

        async def _on_toggle_partition() -> None:
            toggle_dialog.close()
            toggle_btn.props("loading")
            try:
                dev = state.get_active_device()
                if dev is None:
                    _show_status("No device connected", is_error=True)
                    return
                await run.io_bound(dev.firmware.toggle_active_partition)
                _show_status("Active partition toggled successfully")
                ui.notify(
                    "Active partition toggled. Reset device to apply.",
                    type="positive",
                    position="top",
                )
                await _load_firmware_data()
            except SwitchtecError as exc:
                _show_status(f"Toggle failed: {exc}", is_error=True)
                ui.notify(f"Toggle failed: {exc}", type="negative", position="top")
            finally:
                toggle_btn.props(remove="loading")

        async def _on_toggle_boot_ro() -> None:
            boot_ro_dialog.close()
            boot_ro_btn.props("loading")
            try:
                dev = state.get_active_device()
                if dev is None:
                    _show_status("No device connected", is_error=True)
                    return
                is_currently_ro = current_boot_ro["value"]
                new_ro = not is_currently_ro if is_currently_ro is not None else True
                await run.io_bound(
                    lambda: dev.firmware.set_boot_ro(read_only=new_ro),
                )
                _update_boot_ro_display(new_ro)
                state_str = "enabled" if new_ro else "disabled"
                _show_status(f"Boot RO {state_str}")
                ui.notify(
                    f"Boot read-only {state_str}",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                _show_status(f"Boot RO change failed: {exc}", is_error=True)
                ui.notify(
                    f"Boot RO change failed: {exc}",
                    type="negative",
                    position="top",
                )
            finally:
                boot_ro_btn.props(remove="loading")

        def _open_toggle_dialog() -> None:
            toggle_dialog.open()

        def _open_boot_ro_dialog() -> None:
            is_ro = current_boot_ro["value"]
            if is_ro is not None:
                action = "disable" if is_ro else "enable"
                boot_ro_dialog_text.set_text(
                    f"This will {action} the boot partition read-only flag. "
                    "This is a destructive operation."
                )
            boot_ro_dialog.open()

        # Wire button handlers
        refresh_btn.on_click(_on_refresh)
        toggle_btn.on_click(_open_toggle_dialog)
        confirm_toggle_btn.on_click(_on_toggle_partition)
        boot_ro_btn.on_click(_open_boot_ro_dialog)
        confirm_boot_ro_btn.on_click(_on_toggle_boot_ro)

        # Load initial data
        ui.timer(0.1, _load_firmware_data, once=True)
