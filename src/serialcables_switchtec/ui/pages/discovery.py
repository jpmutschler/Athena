"""Device discovery page."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def discovery_page() -> None:
    """Device discovery and connection page."""
    with page_layout("Discovery", current_path="/"):
        ui.label("Switchtec Device Discovery").classes("text-h5 q-mb-md")

        # --- Connect to Device card ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Connect to Device").classes("text-h6 q-mb-sm")

            device_path = ui.input(
                label="Device Path",
                placeholder="/dev/switchtec0",
            ).classes("w-full q-mb-sm")

            status_label = ui.label("").classes("q-mb-sm")
            status_label.set_visibility(False)

            with ui.row():
                scan_btn = ui.button("Scan", icon="search").props(
                    "color=primary"
                )
                connect_btn = ui.button("Connect", icon="link").props(
                    "color=positive"
                )

        # --- Discovered Devices card ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Discovered Devices").classes("text-h6 q-mb-sm")
            devices_container = ui.column().classes("w-full")
            with devices_container:
                ui.label(
                    "Click 'Scan' to discover devices"
                ).classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )

        def _show_status(msg: str, is_error: bool = False) -> None:
            status_label.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            status_label.style(f"color: {color};")
            status_label.set_visibility(True)

        async def _on_scan() -> None:
            from serialcables_switchtec.ui import state

            devices_container.clear()
            _show_status("Scanning...")
            scan_btn.props("loading")

            try:
                devices = await run.io_bound(state.scan_devices)
            finally:
                scan_btn.props(remove="loading")

            if not devices:
                _show_status("No devices found", is_error=True)
                with devices_container:
                    ui.label("No Switchtec devices found on this system.").style(
                        f"color: {COLORS.text_secondary};"
                    )
                return

            _show_status(f"Found {len(devices)} device(s)")
            with devices_container:
                for dev_info in devices:
                    with ui.card().classes("w-full q-pa-sm q-mb-sm").style(
                        f"border: 1px solid {COLORS.text_muted};"
                    ):
                        with ui.row().classes("items-center w-full"):
                            ui.icon("memory").classes("text-h6").style(
                                f"color: {COLORS.accent};"
                            )
                            with ui.column().classes("q-ml-sm"):
                                ui.label(dev_info.name).classes(
                                    "text-subtitle1 text-bold"
                                )
                                ui.label(
                                    f"{dev_info.description} | {dev_info.pci_dev}"
                                ).style(
                                    f"color: {COLORS.text_secondary}; font-size: 0.85em;"
                                )
                                ui.label(
                                    f"FW: {dev_info.fw_version} | Path: {dev_info.path}"
                                ).style(
                                    f"color: {COLORS.text_muted}; font-size: 0.8em;"
                                )
                            ui.space()
                            ui.button(
                                "Connect",
                                icon="link",
                                on_click=lambda _, p=dev_info.path: _on_connect(p),
                            ).props("color=positive dense")

        async def _on_connect(path: str | None = None) -> None:
            from serialcables_switchtec.ui import state

            connect_path = (path or device_path.value or "").strip()
            if not connect_path:
                _show_status("Enter a device path", is_error=True)
                return
            if len(connect_path) > 256:
                _show_status("Device path too long", is_error=True)
                return

            connect_btn.props("loading")
            try:
                summary = await run.io_bound(state.connect_device, connect_path)
                _show_status(
                    f"Connected to {summary.name} ({summary.generation})"
                )
                ui.notify(
                    f"Connected to {summary.name}",
                    type="positive",
                    position="top",
                )
                ui.navigate.to("/dashboard")
            except SwitchtecError as e:
                _show_status(f"Connection failed: {e}", is_error=True)
                ui.notify(
                    f"Connection failed: {e}",
                    type="negative",
                    position="top",
                )
            finally:
                connect_btn.props(remove="loading")

        scan_btn.on_click(_on_scan)
        connect_btn.on_click(lambda: _on_connect())
