"""Ordered Set Analyzer (OSA) page."""

from __future__ import annotations

from dataclasses import dataclass

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS


@dataclass
class _OsaInputs:
    """Mutable container for shared OSA input widgets."""

    stack: ui.number | None = None
    lane: ui.number | None = None
    direction: ui.select | None = None
    lane_mask: ui.input | None = None
    link_rate: ui.number | None = None


def osa_page() -> None:
    """Ordered Set Analyzer page for capture and analysis."""
    from serialcables_switchtec.ui import state

    with page_layout("OSA", current_path="/osa"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Ordered Set Analyzer").classes("text-h5 q-mb-md")

        inputs = _OsaInputs()
        _osa_config_section(inputs)
        _capture_section(inputs)
        _dump_section(inputs)


# ── OSA Configuration ──────────────────────────────────────────────


def _osa_config_section(inputs: _OsaInputs) -> None:
    """OSA configuration inputs and config type/pattern setup."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("OSA Configuration").classes("text-h6 q-mb-sm")

        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            inputs.stack = ui.number(
                label="Stack ID", value=0, min=0, step=1,
            ).classes("w-32")
            inputs.lane = ui.number(
                label="Lane ID", value=0, min=0, step=1,
            ).classes("w-32")
            inputs.direction = ui.select(
                label="Direction",
                options={0: "RX", 1: "TX"},
                value=0,
            ).classes("w-32")
            inputs.lane_mask = ui.input(
                label="Lane Mask (hex)",
                placeholder="0x1",
                value="0x1",
            ).classes("w-32")
            inputs.link_rate = ui.number(
                label="Link Rate", value=0, min=0, step=1,
            ).classes("w-32")

        # ── Config Type ──
        ui.separator().classes("q-my-md")
        ui.label("Configure Type Filter").classes("text-subtitle1 text-bold q-mb-xs")

        with ui.row().classes("items-end q-gutter-md"):
            os_types_input = ui.input(
                label="OS Types (hex bitmask)",
                placeholder="0xFFFF",
                value="0xFFFF",
            ).classes("w-40")

            config_type_btn = ui.button(
                "Apply Type Config", icon="tune"
            ).props("color=primary")

        # ── Config Pattern ──
        ui.separator().classes("q-my-md")
        ui.label("Configure Pattern Match").classes("text-subtitle1 text-bold q-mb-xs")

        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            pattern_value_input = ui.input(
                label="Pattern Value (4 hex DWORDs, comma-sep)",
                placeholder="0,0,0,0",
                value="0,0,0,0",
            ).classes("w-64")
            pattern_mask_input = ui.input(
                label="Pattern Mask (4 hex DWORDs, comma-sep)",
                placeholder="0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF",
                value="0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF",
            ).classes("w-64")

        config_pattern_btn = ui.button(
            "Apply Pattern Config", icon="tune"
        ).props("color=primary").classes("q-mt-sm")

        status_label = ui.label("").classes("q-mt-sm")
        status_label.set_visibility(False)

        def _show_status(msg: str, is_error: bool = False) -> None:
            status_label.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            status_label.style(f"color: {color};")
            status_label.set_visibility(True)

        def _parse_hex(val: str) -> int:
            return int(val.strip(), 0)

        def _parse_dword_list(val: str) -> list[int]:
            parts = [x.strip() for x in val.split(",") if x.strip()]
            result = [int(x, 0) for x in parts]
            while len(result) < 4:
                result.append(0)
            return result[:4]

        async def _on_config_type() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)
            direction = int(inputs.direction.value or 0)
            try:
                lane_mask = _parse_hex(inputs.lane_mask.value or "0x1")
            except ValueError:
                ui.notify("Invalid lane mask", type="negative", position="top")
                return
            link_rate = int(inputs.link_rate.value or 0)
            try:
                os_types = _parse_hex(os_types_input.value or "0xFFFF")
            except ValueError:
                ui.notify("Invalid OS types", type="negative", position="top")
                return

            config_type_btn.props("loading")
            try:
                await run.io_bound(
                    dev.osa.configure_type,
                    stack, direction, lane_mask, link_rate, os_types,
                )
                _show_status("Type config applied")
                ui.notify("Type config applied", type="positive", position="top")
            except SwitchtecError as exc:
                _show_status(f"Config failed: {exc}", is_error=True)
                ui.notify(f"Config failed: {exc}", type="negative", position="top")
            finally:
                config_type_btn.props(remove="loading")

        async def _on_config_pattern() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)
            direction = int(inputs.direction.value or 0)
            try:
                lane_mask = _parse_hex(inputs.lane_mask.value or "0x1")
            except ValueError:
                ui.notify("Invalid lane mask", type="negative", position="top")
                return
            link_rate = int(inputs.link_rate.value or 0)
            try:
                val_data = _parse_dword_list(pattern_value_input.value or "0,0,0,0")
            except ValueError:
                ui.notify("Invalid pattern value", type="negative", position="top")
                return
            try:
                msk_data = _parse_dword_list(
                    pattern_mask_input.value
                    or "0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF,0xFFFFFFFF"
                )
            except ValueError:
                ui.notify("Invalid pattern mask", type="negative", position="top")
                return

            config_pattern_btn.props("loading")
            try:
                await run.io_bound(
                    dev.osa.configure_pattern,
                    stack, direction, lane_mask, link_rate, val_data, msk_data,
                )
                _show_status("Pattern config applied")
                ui.notify("Pattern config applied", type="positive", position="top")
            except SwitchtecError as exc:
                _show_status(f"Config failed: {exc}", is_error=True)
                ui.notify(f"Config failed: {exc}", type="negative", position="top")
            finally:
                config_pattern_btn.props(remove="loading")

        config_type_btn.on_click(_on_config_type)
        config_pattern_btn.on_click(_on_config_pattern)


# ── Capture Controls ───────────────────────────────────────────────


def _capture_section(inputs: _OsaInputs) -> None:
    """Capture start/stop and data display."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Capture Controls").classes("text-h6 q-mb-sm")

        with ui.row().classes("q-gutter-md"):
            start_btn = ui.button("Start Capture", icon="play_arrow").props(
                "color=positive"
            )
            stop_btn = ui.button("Stop Capture", icon="stop").props(
                "color=negative"
            )

        # Capture control parameters
        ui.separator().classes("q-my-md")
        ui.label("Capture Control Parameters").classes(
            "text-subtitle1 text-bold q-mb-xs"
        )
        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            drop_single_input = ui.number(
                label="Drop Single OS", value=0, min=0, max=1, step=1,
            ).classes("w-32")
            stop_mode_input = ui.number(
                label="Stop Mode", value=0, min=0, step=1,
            ).classes("w-32")
            snapshot_mode_input = ui.number(
                label="Snapshot Mode", value=0, min=0, step=1,
            ).classes("w-32")
            post_trigger_input = ui.number(
                label="Post Trigger", value=0, min=0, step=1,
            ).classes("w-32")
            cc_os_types_input = ui.input(
                label="OS Types (hex)",
                placeholder="0x0",
                value="0x0",
            ).classes("w-32")

        apply_cc_btn = ui.button(
            "Apply Capture Control", icon="settings"
        ).props("color=primary").classes("q-mt-sm")

        # Captured data display
        ui.separator().classes("q-my-md")
        ui.label("Captured Data").classes("text-subtitle1 text-bold q-mb-xs")

        data_display = ui.label("No data captured yet.").style(
            f"color: {COLORS.text_secondary};"
        )

        fetch_btn = ui.button("Fetch Capture Data", icon="download").props(
            "color=primary"
        ).classes("q-mt-sm")

        async def _on_start() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)

            start_btn.props("loading")
            try:
                await run.io_bound(dev.osa.start, stack)
                ui.notify(
                    f"OSA capture started (stack {stack})",
                    type="positive",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Start failed: {exc}", type="negative", position="top")
            finally:
                start_btn.props(remove="loading")

        async def _on_stop() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)

            stop_btn.props("loading")
            try:
                await run.io_bound(dev.osa.stop, stack)
                ui.notify(
                    f"OSA capture stopped (stack {stack})",
                    type="info",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Stop failed: {exc}", type="negative", position="top")
            finally:
                stop_btn.props(remove="loading")

        async def _on_apply_cc() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)
            direction = int(inputs.direction.value or 0)
            try:
                lane_mask = int(
                    (inputs.lane_mask.value or "0x1").strip(), 0
                )
            except ValueError:
                ui.notify("Invalid lane mask", type="negative", position="top")
                return
            try:
                cc_os = int((cc_os_types_input.value or "0x0").strip(), 0)
            except ValueError:
                ui.notify("Invalid OS types", type="negative", position="top")
                return

            apply_cc_btn.props("loading")
            try:
                await run.io_bound(
                    dev.osa.capture_control,
                    stack,
                    lane_mask,
                    direction,
                    int(drop_single_input.value or 0),
                    int(stop_mode_input.value or 0),
                    int(snapshot_mode_input.value or 0),
                    int(post_trigger_input.value or 0),
                    cc_os,
                )
                ui.notify("Capture control applied", type="positive", position="top")
            except SwitchtecError as exc:
                ui.notify(f"Apply failed: {exc}", type="negative", position="top")
            finally:
                apply_cc_btn.props(remove="loading")

        async def _on_fetch() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)
            lane = int(inputs.lane.value or 0)
            direction = int(inputs.direction.value or 0)

            fetch_btn.props("loading")
            try:
                result = await run.io_bound(
                    dev.osa.capture_data, stack, lane, direction
                )
                data_display.set_text(f"Capture data result: {result}")
                data_display.style(f"color: {COLORS.accent};")
                ui.notify("Data fetched", type="positive", position="top")
            except SwitchtecError as exc:
                data_display.set_text(f"Fetch error: {exc}")
                data_display.style(f"color: {COLORS.error};")
                ui.notify(f"Fetch failed: {exc}", type="negative", position="top")
            finally:
                fetch_btn.props(remove="loading")

        start_btn.on_click(_on_start)
        stop_btn.on_click(_on_stop)
        apply_cc_btn.on_click(_on_apply_cc)
        fetch_btn.on_click(_on_fetch)


# ── Dump Config ────────────────────────────────────────────────────


def _dump_section(inputs: _OsaInputs) -> None:
    """Dump current OSA configuration."""
    with ui.card().classes("w-full q-pa-md"):
        ui.label("Configuration Dump").classes("text-h6 q-mb-sm")

        dump_display = ui.label("No config dumped yet.").style(
            f"color: {COLORS.text_secondary};"
        )

        dump_btn = ui.button("Dump Config", icon="description").props(
            "color=primary"
        ).classes("q-mt-sm")

        async def _on_dump() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            stack = int(inputs.stack.value or 0)

            dump_btn.props("loading")
            try:
                result = await run.io_bound(dev.osa.dump_config, stack)
                dump_display.set_text(f"Config dump result (stack {stack}): {result}")
                dump_display.style(f"color: {COLORS.accent};")
                ui.notify("Config dumped", type="positive", position="top")
            except SwitchtecError as exc:
                dump_display.set_text(f"Dump error: {exc}")
                dump_display.style(f"color: {COLORS.error};")
                ui.notify(f"Dump failed: {exc}", type="negative", position="top")
            finally:
                dump_btn.props(remove="loading")

        dump_btn.on_click(_on_dump)
