"""Fabric topology management page."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.fabric import (
    GfmsBindRequest,
    GfmsUnbindRequest,
)
from serialcables_switchtec.ui.components.confirm_dialog import confirm_action
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


def fabric_page() -> None:
    """Fabric topology management page for PAX devices."""
    from serialcables_switchtec.ui import state

    with page_layout("Fabric", current_path="/fabric"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Fabric / Topology Management").classes("text-h5 q-mb-md")

        _port_config_section()
        _csr_section()
        _bind_unbind_section()
        _gfms_events_section()


# ── Port Configuration ──────────────────────────────────────────────


def _port_config_section() -> None:
    """Port configuration read/write section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Port Configuration").classes("text-h6 q-mb-sm")

        with ui.row().classes("items-end q-gutter-md"):
            port_id_input = ui.number(
                label="Physical Port ID",
                value=0,
                min=0,
                max=59,
                step=1,
            ).classes("w-32")

            get_btn = ui.button("Get Config", icon="download").props(
                "color=primary"
            )

        config_display = ui.column().classes("w-full q-mt-md")
        config_display.set_visibility(False)

        async def _on_get_config() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(port_id_input.value or 0)
            get_btn.props("loading")
            try:
                config = await run.io_bound(dev.fabric.get_port_config, port)
                config_display.clear()
                with config_display:
                    with ui.card().classes("w-full q-pa-sm").style(
                        f"border: 1px solid {COLORS.text_muted};"
                    ):
                        ui.label(f"Port {config.phys_port_id}").classes(
                            "text-subtitle1 text-bold"
                        )
                        _kv_row("Port Type", str(config.port_type))
                        _kv_row("Clock Source", str(config.clock_source))
                        _kv_row("Clock SRIS", str(config.clock_sris))
                        _kv_row("HVD Instance", str(config.hvd_inst))
                config_display.set_visibility(True)
                ui.notify("Config loaded", type="positive", position="top")
            except SwitchtecError as exc:
                ui.notify(f"Failed: {exc}", type="negative", position="top")
            finally:
                get_btn.props(remove="loading")

        get_btn.on_click(_on_get_config)


# ── CSR Read / Write ────────────────────────────────────────────────


def _csr_section() -> None:
    """CSR read/write section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("CSR Read / Write").classes("text-h6 q-mb-sm")

        with ui.row().classes("items-end q-gutter-md"):
            pdfid_input = ui.number(
                label="PDFID",
                value=0,
                min=0,
                max=0xFFFF,
                step=1,
            ).classes("w-32")

            addr_input = ui.input(
                label="Address (hex)",
                placeholder="0x00",
            ).classes("w-32")

            width_select = ui.select(
                label="Width",
                options={8: "8-bit", 16: "16-bit", 32: "32-bit"},
                value=32,
            ).classes("w-32")

        read_result_label = ui.label("").classes("q-mt-sm")
        read_result_label.set_visibility(False)

        with ui.row().classes("q-gutter-md q-mt-sm"):
            read_btn = ui.button("Read CSR", icon="search").props(
                "color=primary"
            )

        ui.separator().classes("q-my-md")

        with ui.row().classes("items-end q-gutter-md"):
            write_value_input = ui.input(
                label="Write Value (hex)",
                placeholder="0x00",
            ).classes("w-32")

            write_btn = ui.button("Write CSR", icon="edit").props(
                "color=warning"
            )

        async def _on_csr_read() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            pdfid = int(pdfid_input.value or 0)
            width = int(width_select.value or 32)
            addr_str = (addr_input.value or "0").strip()
            try:
                addr_int = int(addr_str, 0)
            except ValueError:
                ui.notify(f"Invalid address: {addr_str}", type="negative", position="top")
                return

            read_btn.props("loading")
            try:
                value = await run.io_bound(dev.fabric.csr_read, pdfid, addr_int, width)
                read_result_label.set_text(
                    f"CSR[0x{addr_int:03x}] (w{width}) = 0x{value:x}"
                )
                read_result_label.style(f"color: {COLORS.accent};")
                read_result_label.set_visibility(True)
                ui.notify("CSR read OK", type="positive", position="top")
            except SwitchtecError as exc:
                ui.notify(f"Read failed: {exc}", type="negative", position="top")
            finally:
                read_btn.props(remove="loading")

        async def _do_csr_write() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            pdfid = int(pdfid_input.value or 0)
            width = int(width_select.value or 32)
            addr_str = (addr_input.value or "0").strip()
            val_str = (write_value_input.value or "0").strip()
            try:
                addr_int = int(addr_str, 0)
            except ValueError:
                ui.notify(f"Invalid address: {addr_str}", type="negative", position="top")
                return
            try:
                val_int = int(val_str, 0)
            except ValueError:
                ui.notify(f"Invalid value: {val_str}", type="negative", position="top")
                return

            write_btn.props("loading")
            try:
                await run.io_bound(dev.fabric.csr_write, pdfid, addr_int, val_int, width)
                ui.notify(
                    f"CSR[0x{addr_int:03x}] <- 0x{val_int:x}",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Write failed: {exc}", type="negative", position="top")
            finally:
                write_btn.props(remove="loading")

        async def _on_csr_write() -> None:
            addr_str = (addr_input.value or "0").strip()
            val_str = (write_value_input.value or "0").strip()
            width = int(width_select.value or 32)
            confirmed = await confirm_action(
                title="Confirm CSR Write",
                message=(
                    f"Write 0x{val_str} to CSR address {addr_str} (w{width})?\n"
                    "Writing to config space registers can cause hardware malfunction."
                ),
                confirm_text="Write",
                dangerous=True,
            )
            if confirmed:
                await _do_csr_write()

        read_btn.on_click(_on_csr_read)
        write_btn.on_click(_on_csr_write)


# ── Bind / Unbind ───────────────────────────────────────────────────


def _bind_unbind_section() -> None:
    """GFMS bind/unbind section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("GFMS Bind / Unbind").classes("text-h6 q-mb-sm")

        # ── Bind form ──
        ui.label("Bind").classes("text-subtitle1 text-bold q-mb-xs")
        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            bind_sw_idx = ui.number(
                label="Host SW Index", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            bind_phys_port = ui.number(
                label="Phys Port", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            bind_log_port = ui.number(
                label="Log Port", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            bind_ep_number = ui.number(
                label="EP Number", value=0, min=0, step=1,
            ).classes("w-32")
            bind_ep_pdfid = ui.input(
                label="EP PDFIDs (comma-sep)",
                placeholder="0,1,2",
            ).classes("w-48")

        bind_btn = ui.button("Bind", icon="link").props(
            "color=primary"
        ).classes("q-mt-sm")

        ui.separator().classes("q-my-md")

        # ── Unbind form ──
        ui.label("Unbind").classes("text-subtitle1 text-bold q-mb-xs")
        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            unbind_sw_idx = ui.number(
                label="Host SW Index", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            unbind_phys_port = ui.number(
                label="Phys Port", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            unbind_log_port = ui.number(
                label="Log Port", value=0, min=0, max=255, step=1,
            ).classes("w-32")
            unbind_pdfid = ui.number(
                label="PDFID", value=0, min=0, max=65535, step=1,
            ).classes("w-32")
            unbind_option = ui.number(
                label="Option", value=0, min=0, max=255, step=1,
            ).classes("w-32")

        unbind_btn = ui.button("Unbind", icon="link_off").props(
            "color=warning"
        ).classes("q-mt-sm")

        # ── Port Control ──
        ui.separator().classes("q-my-md")
        ui.label("Port Control").classes("text-subtitle1 text-bold q-mb-xs")
        with ui.row().classes("items-end q-gutter-md"):
            pc_port = ui.number(
                label="Physical Port ID", value=0, min=0, max=59, step=1,
            ).classes("w-32")
            pc_action = ui.select(
                label="Action",
                options={
                    "enable": "Enable",
                    "disable": "Disable",
                    "hot_reset": "Hot Reset",
                },
                value="enable",
            ).classes("w-40")
            pc_btn = ui.button("Execute", icon="play_arrow").props(
                "color=warning"
            )

        async def _do_bind() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            pdfid_str = (bind_ep_pdfid.value or "").strip()
            pdfid_list: list[int] = []
            if pdfid_str:
                try:
                    pdfid_list = [int(x.strip(), 0) for x in pdfid_str.split(",") if x.strip()]
                except ValueError:
                    ui.notify("Invalid PDFID list", type="negative", position="top")
                    return

            request = GfmsBindRequest(
                host_sw_idx=int(bind_sw_idx.value or 0),
                host_phys_port_id=int(bind_phys_port.value or 0),
                host_log_port_id=int(bind_log_port.value or 0),
                ep_number=int(bind_ep_number.value or 0),
                ep_pdfid=pdfid_list,
            )

            bind_btn.props("loading")
            try:
                await run.io_bound(dev.fabric.bind, request)
                ui.notify(
                    f"Bound host port {request.host_phys_port_id}",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Bind failed: {exc}", type="negative", position="top")
            finally:
                bind_btn.props(remove="loading")

        async def _on_bind() -> None:
            confirmed = await confirm_action(
                title="Confirm Bind",
                message="Binding changes fabric topology. This may disrupt active connections.",
                confirm_text="Bind",
                dangerous=True,
            )
            if confirmed:
                await _do_bind()

        async def _do_unbind() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            request = GfmsUnbindRequest(
                host_sw_idx=int(unbind_sw_idx.value or 0),
                host_phys_port_id=int(unbind_phys_port.value or 0),
                host_log_port_id=int(unbind_log_port.value or 0),
                pdfid=int(unbind_pdfid.value or 0),
                option=int(unbind_option.value or 0),
            )

            unbind_btn.props("loading")
            try:
                await run.io_bound(dev.fabric.unbind, request)
                ui.notify(
                    f"Unbound host port {request.host_phys_port_id}",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Unbind failed: {exc}", type="negative", position="top")
            finally:
                unbind_btn.props(remove="loading")

        async def _on_unbind() -> None:
            confirmed = await confirm_action(
                title="Confirm Unbind",
                message="Unbinding removes fabric connections. Active traffic will be disrupted.",
                confirm_text="Unbind",
                dangerous=True,
            )
            if confirmed:
                await _do_unbind()

        _ACTION_MAP = {
            "enable": FabPortControlType.ENABLE,
            "disable": FabPortControlType.DISABLE,
            "hot_reset": FabPortControlType.HOT_RESET,
        }

        async def _do_port_control() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(pc_port.value or 0)
            action_key = pc_action.value or "enable"
            control_type = _ACTION_MAP[action_key]
            hr_flag = FabHotResetFlag.NONE

            pc_btn.props("loading")
            try:
                await run.io_bound(dev.fabric.port_control, port, control_type, hr_flag)
                ui.notify(
                    f"Port {port}: {action_key} complete",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Port control failed: {exc}", type="negative", position="top")
            finally:
                pc_btn.props(remove="loading")

        async def _on_port_control() -> None:
            action_key = pc_action.value or "enable"
            port = int(pc_port.value or 0)
            confirmed = await confirm_action(
                title="Confirm Port Control",
                message=(
                    f"Execute '{action_key}' on port {port}?\n"
                    "Port control operations can disrupt active links."
                ),
                confirm_text="Execute",
                dangerous=True,
            )
            if confirmed:
                await _do_port_control()

        bind_btn.on_click(_on_bind)
        unbind_btn.on_click(_on_unbind)
        pc_btn.on_click(_on_port_control)


# ── GFMS Events ────────────────────────────────────────────────────


def _gfms_events_section() -> None:
    """GFMS events display and clear section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("GFMS Events").classes("text-h6 q-mb-sm")

        ui.label(
            "Event retrieval requires GFMS event struct support. "
            "Use the clear button to reset the event log on the device."
        ).style(f"color: {COLORS.text_secondary}; font-size: 0.85em;")

        clear_btn = ui.button("Clear GFMS Events", icon="delete_sweep").props(
            "color=warning"
        ).classes("q-mt-sm")

        async def _do_clear() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            clear_btn.props("loading")
            try:
                await run.io_bound(dev.fabric.clear_gfms_events)
                ui.notify("GFMS events cleared", type="positive", position="top")
            except SwitchtecError as exc:
                ui.notify(f"Clear failed: {exc}", type="negative", position="top")
            finally:
                clear_btn.props(remove="loading")

        async def _on_clear() -> None:
            confirmed = await confirm_action(
                title="Confirm Clear Events",
                message="Clear all GFMS events on the device?",
                confirm_text="Clear",
                dangerous=True,
            )
            if confirmed:
                await _do_clear()

        clear_btn.on_click(_on_clear)


# ── Helpers ─────────────────────────────────────────────────────────


def _kv_row(label: str, value: str) -> None:
    """Render a key-value row."""
    with ui.row().classes("q-gutter-sm items-center"):
        ui.label(f"{label}:").style(
            f"color: {COLORS.text_secondary}; font-size: 0.85em; min-width: 120px;"
        )
        ui.label(value).style(
            f"color: {COLORS.text_primary}; font-size: 0.85em;"
        )
