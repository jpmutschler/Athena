"""Error injection page."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.confirm_dialog import confirm_action
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.ltssm_timeline import ltssm_timeline
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

_INJECTION_TYPES = {
    "dllp_crc": "DLLP CRC",
    "tlp_lcrc": "TLP LCRC",
    "seq_num": "Sequence Number",
    "ack_nack": "ACK/NACK",
    "cto": "Completion Timeout",
    "raw_dllp": "Raw DLLP",
}


def injection_page() -> None:
    """Error injection page for PCIe link testing."""
    from serialcables_switchtec.ui import state

    with page_layout("Injection", current_path="/injection"):
        if not state.is_connected():
            show_disconnected()
            return

        # Shared mutable containers for cross-section updates
        history: list[dict[str, str]] = []
        table_ref: list[ui.table | None] = [None]

        _warning_banner()

        ui.label("Error Injection").classes("text-h5 q-mb-md")

        _injection_section(history, table_ref)
        _aer_section(history, table_ref)
        _verification_section()
        _history_section(history, table_ref)


# ── Warning Banner ──────────────────────────────────────────────────


def _warning_banner() -> None:
    """Display a prominent warning banner."""
    with ui.card().classes("w-full q-pa-md q-mb-md").style(
        f"border: 2px solid {COLORS.error}; background: rgba(239, 83, 80, 0.08);"
    ):
        with ui.row().classes("items-center q-gutter-md"):
            ui.icon("warning").classes("text-h4").style(
                f"color: {COLORS.error};"
            )
            with ui.column():
                ui.label("Error Injection - Use With Caution").classes(
                    "text-h6 text-bold"
                ).style(f"color: {COLORS.error};")
                ui.label(
                    "Error injection can cause link failures, data corruption, "
                    "and system instability. Only use in controlled test environments."
                ).style(f"color: {COLORS.warning}; font-size: 0.9em;")


# ── Helpers ─────────────────────────────────────────────────────────


def _append_history(
    history: list[dict[str, str]],
    table_ref: list[ui.table | None],
    inj_type: str,
    port: int,
    detail: str,
) -> None:
    """Append an entry to the injection history and refresh the table."""
    entry_id = len(history) + 1
    timestamp = datetime.now(tz=timezone.utc).strftime("%H:%M:%S")
    history.append({
        "id": str(entry_id),
        "time": timestamp,
        "type": inj_type,
        "port": str(port),
        "detail": detail,
    })
    tbl = table_ref[0]
    if tbl is not None:
        tbl.rows = list(history)
        tbl.update()


# ── Injection Controls ──────────────────────────────────────────────


def _injection_section(
    history: list[dict[str, str]],
    table_ref: list[ui.table | None],
) -> None:
    """Main injection controls section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Inject Error").classes("text-h6 q-mb-sm")

        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            port_input = ui.number(
                label="Physical Port ID",
                value=0,
                min=0,
                max=59,
                step=1,
            ).classes("w-32")

            type_select = ui.select(
                label="Injection Type",
                options=_INJECTION_TYPES,
                value="dllp_crc",
            ).classes("w-48")

        # Parameters for each injection type
        enable_toggle = ui.switch("Enable", value=True)
        enable_toggle.set_visibility(False)

        rate_input = ui.number(label="Rate", value=1, min=0, step=1)
        rate_input.classes("w-32")
        rate_input.set_visibility(False)

        seq_num_input = ui.number(label="Sequence Number", value=0, min=0, step=1)
        seq_num_input.classes("w-32")
        seq_num_input.set_visibility(False)

        count_input = ui.number(label="Count", value=1, min=1, step=1)
        count_input.classes("w-32")
        count_input.set_visibility(False)

        dllp_data_input = ui.input(label="DLLP Data (hex)", placeholder="0x00")
        dllp_data_input.classes("w-48")
        dllp_data_input.set_visibility(False)

        def _update_params() -> None:
            """Show/hide parameters based on selected injection type."""
            inj_type = type_select.value
            enable_toggle.set_visibility(inj_type in ("dllp_crc", "tlp_lcrc"))
            rate_input.set_visibility(inj_type in ("dllp_crc", "tlp_lcrc"))
            seq_num_input.set_visibility(inj_type == "ack_nack")
            count_input.set_visibility(inj_type == "ack_nack")
            dllp_data_input.set_visibility(inj_type == "raw_dllp")

        type_select.on_value_change(lambda _: _update_params())
        _update_params()

        inject_btn = ui.button("Inject", icon="bolt").props(
            "color=negative"
        ).classes("q-mt-md")

        async def _do_inject() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(port_input.value or 0)
            inj_type = type_select.value

            inject_btn.props("loading")
            try:
                if inj_type == "dllp_crc":
                    enable = bool(enable_toggle.value)
                    rate = int(rate_input.value or 1)
                    await run.io_bound(
                        dev.injector.inject_dllp_crc, port, enable, rate
                    )
                    detail = f"enable={enable}, rate={rate}"

                elif inj_type == "tlp_lcrc":
                    enable = bool(enable_toggle.value)
                    rate = int(rate_input.value or 1)
                    await run.io_bound(
                        dev.injector.inject_tlp_lcrc, port, enable, rate
                    )
                    detail = f"enable={enable}, rate={rate}"

                elif inj_type == "seq_num":
                    await run.io_bound(dev.injector.inject_tlp_seq_num, port)
                    detail = "single injection"

                elif inj_type == "ack_nack":
                    seq = int(seq_num_input.value or 0)
                    cnt = int(count_input.value or 1)
                    await run.io_bound(
                        dev.injector.inject_ack_nack, port, seq, cnt
                    )
                    detail = f"seq={seq}, count={cnt}"

                elif inj_type == "cto":
                    await run.io_bound(dev.injector.inject_cto, port)
                    detail = "single injection"

                elif inj_type == "raw_dllp":
                    data_str = (dllp_data_input.value or "0").strip()
                    try:
                        data_int = int(data_str, 0)
                    except ValueError:
                        ui.notify(
                            f"Invalid DLLP data: {data_str}",
                            type="negative",
                            position="top",
                        )
                        return
                    await run.io_bound(dev.injector.inject_dllp, port, data_int)
                    detail = f"data=0x{data_int:x}"

                else:
                    ui.notify("Unknown injection type", type="negative", position="top")
                    return

                type_label = _INJECTION_TYPES.get(inj_type, inj_type)
                _append_history(history, table_ref, type_label, port, detail)
                ui.notify(
                    f"Injected {type_label} on port {port}",
                    type="warning",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"Injection failed: {exc}", type="negative", position="top")
            finally:
                inject_btn.props(remove="loading")

        async def _on_inject() -> None:
            inj_type = type_select.value
            port = int(port_input.value or 0)
            type_label = _INJECTION_TYPES.get(inj_type, inj_type)
            confirmed = await confirm_action(
                title="Confirm Error Injection",
                message=(
                    f"Inject {type_label} error on port {port}?\n"
                    "This may cause link degradation or failure."
                ),
                confirm_text="Inject",
                dangerous=True,
            )
            if confirmed:
                await _do_inject()

        inject_btn.on_click(_on_inject)


# ── AER Event Generation ───────────────────────────────────────────


def _aer_section(
    history: list[dict[str, str]],
    table_ref: list[ui.table | None],
) -> None:
    """AER event generation section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("AER Event Generation").classes("text-h6 q-mb-sm")

        with ui.row().classes("items-end q-gutter-md flex-wrap"):
            aer_port = ui.number(
                label="Port ID", value=0, min=0, max=59, step=1,
            ).classes("w-32")
            aer_error_id = ui.number(
                label="Error ID", value=0, min=0, step=1,
            ).classes("w-32")
            aer_trigger = ui.number(
                label="Trigger", value=0, min=0, step=1,
            ).classes("w-32")

        aer_btn = ui.button("Generate AER Event", icon="error_outline").props(
            "color=negative"
        ).classes("q-mt-sm")

        async def _do_aer() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(aer_port.value or 0)
            error_id = int(aer_error_id.value or 0)
            trigger = int(aer_trigger.value or 0)

            aer_btn.props("loading")
            try:
                await run.io_bound(
                    dev.diagnostics.aer_event_gen, port, error_id, trigger
                )
                _append_history(
                    history,
                    table_ref,
                    "AER Event",
                    port,
                    f"error_id={error_id}, trigger={trigger}",
                )
                ui.notify(
                    f"AER event generated on port {port}",
                    type="warning",
                    position="top",
                )
            except SwitchtecError as exc:
                ui.notify(f"AER generation failed: {exc}", type="negative", position="top")
            finally:
                aer_btn.props(remove="loading")

        async def _on_aer() -> None:
            port = int(aer_port.value or 0)
            error_id = int(aer_error_id.value or 0)
            confirmed = await confirm_action(
                title="Confirm AER Event Generation",
                message=(
                    f"Generate AER event (error_id={error_id}) on port {port}?\n"
                    "AER events may trigger system-level error handling."
                ),
                confirm_text="Generate",
                dangerous=True,
            )
            if confirmed:
                await _do_aer()

        aer_btn.on_click(_on_aer)


# ── Post-Injection Link Verification ───────────────────────────────


def _verification_section() -> None:
    """Post-injection link verification section."""
    with ui.card().classes("w-full q-pa-md q-mb-md"):
        ui.label("Post-Injection Link Verification").classes("text-h6 q-mb-sm")

        ui.label(
            "Verify link status after injection: captures pre/post link state "
            "and LTSSM transitions to assess impact."
        ).style(f"color: {COLORS.text_secondary}; font-size: 0.85em;")

        with ui.row().classes("q-gutter-sm items-end flex-wrap q-mt-sm"):
            verify_port = ui.number(
                label="Port ID", value=0, min=0, max=59, step=1,
            ).classes("w-24")
            verify_duration = ui.number(
                label="Duration (s)", value=5, min=1, max=30, step=1,
            ).classes("w-28")

        verify_btn = ui.button(
            "Run Verification", icon="verified",
        ).props("color=primary").classes("q-mt-sm")

        verify_container = ui.column().classes("w-full q-mt-sm")

        async def _on_verify() -> None:
            from serialcables_switchtec.ui import state

            dev = state.get_active_device()
            if dev is None:
                ui.notify("No device connected", type="negative", position="top")
                return

            port = int(verify_port.value or 0)
            duration = int(verify_duration.value or 5)

            verify_btn.props("loading")
            verify_container.clear()

            try:
                # 1. Capture pre-state
                pre_ports = await run.io_bound(state.get_port_status)
                pre_link_up = False
                for p in pre_ports:
                    if p.port.phys_id == port:
                        pre_link_up = p.link_up
                        break

                # Clear LTSSM log
                await run.io_bound(dev.diagnostics.ltssm_clear, port)

                # 2. Poll link status for duration
                with verify_container:
                    poll_label = ui.label("Monitoring link status...").classes(
                        "text-subtitle2"
                    ).style(f"color: {COLORS.text_secondary};")

                link_went_down = False
                link_recovered = False
                down_time: float | None = None
                recovery_time: float | None = None
                start_t = time.monotonic()

                poll_count = int(duration / 0.5)
                for _ in range(poll_count):
                    elapsed = time.monotonic() - start_t
                    if elapsed >= duration:
                        break

                    try:
                        ports_now = await run.io_bound(state.get_port_status)
                    except SwitchtecError:
                        await _async_sleep(0.5)
                        continue

                    current_up = False
                    for p in ports_now:
                        if p.port.phys_id == port:
                            current_up = p.link_up
                            break

                    if not current_up and pre_link_up and not link_went_down:
                        link_went_down = True
                        down_time = elapsed

                    if current_up and link_went_down and not link_recovered:
                        link_recovered = True
                        recovery_time = elapsed - (down_time or 0)

                    poll_label.set_text(
                        f"Monitoring... {elapsed:.1f}s / {duration}s"
                    )
                    await _async_sleep(0.5)

                # 3. Capture post-state
                post_ports = await run.io_bound(state.get_port_status)
                post_link_up = False
                for p in post_ports:
                    if p.port.phys_id == port:
                        post_link_up = p.link_up
                        break

                # 4. Read LTSSM log
                try:
                    ltssm_entries = await run.io_bound(
                        dev.diagnostics.ltssm_log, port,
                    )
                except SwitchtecError:
                    ltssm_entries = []

                # 5. Render results
                verify_container.clear()
                with verify_container:
                    # Pre/post link status badges
                    with ui.row().classes("q-gutter-md q-mb-md items-center"):
                        ui.label("Pre:").classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )
                        _link_badge(pre_link_up)
                        ui.label("Post:").classes("text-subtitle2").style(
                            f"color: {COLORS.text_secondary};"
                        )
                        _link_badge(post_link_up)

                    # Verdict banner
                    if post_link_up and not link_went_down:
                        _verdict_banner("Link Stable", COLORS.success, "check_circle")
                    elif post_link_up and link_recovered:
                        recovery_str = f" ({recovery_time:.1f}s)" if recovery_time else ""
                        _verdict_banner(
                            f"Link Recovered{recovery_str}",
                            COLORS.warning, "replay",
                        )
                    else:
                        _verdict_banner("Link Down", COLORS.error, "error")

                    # LTSSM transitions
                    if ltssm_entries:
                        ui.label(
                            f"{len(ltssm_entries)} LTSSM transitions detected"
                        ).classes("text-subtitle2 q-mt-md q-mb-sm").style(
                            f"color: {COLORS.text_secondary};"
                        )
                        ltssm_timeline(ltssm_entries)
                    else:
                        ui.label("No LTSSM transitions detected.").classes(
                            "text-subtitle2 q-mt-sm"
                        ).style(f"color: {COLORS.text_secondary};")

                ui.notify("Verification complete", type="positive", position="top")

            except SwitchtecError as exc:
                ui.notify(f"Verification failed: {exc}", type="negative", position="top")
            finally:
                verify_btn.props(remove="loading")

        verify_btn.on_click(_on_verify)


async def _async_sleep(seconds: float) -> None:
    """Async sleep helper."""
    import asyncio
    await asyncio.sleep(seconds)


def _link_badge(link_up: bool) -> None:
    """Render a link UP/DOWN badge."""
    text = "UP" if link_up else "DOWN"
    color = COLORS.success if link_up else COLORS.error
    ui.badge(text).style(f"background-color: {color};")


def _verdict_banner(text: str, color: str, icon_name: str) -> None:
    """Render a colored verdict banner."""
    with ui.card().classes("w-full q-pa-md q-mb-md").style(
        f"border: 2px solid {color}; background: {color}15;"
    ):
        with ui.row().classes("items-center q-gutter-sm"):
            ui.icon(icon_name).classes("text-h4").style(f"color: {color};")
            ui.label(text).classes("text-h6 text-bold").style(f"color: {color};")


# ── Injection History ───────────────────────────────────────────────


def _history_section(
    history: list[dict[str, str]],
    table_ref: list[ui.table | None],
) -> None:
    """Injection history log section."""
    with ui.card().classes("w-full q-pa-md"):
        ui.label("Injection History").classes("text-h6 q-mb-sm")

        ui.label(
            "Recent injections for this session (in-memory, not persisted)."
        ).style(f"color: {COLORS.text_secondary}; font-size: 0.85em;")

        columns = [
            {"name": "time", "label": "Time (UTC)", "field": "time", "align": "left"},
            {"name": "type", "label": "Type", "field": "type", "align": "left"},
            {"name": "port", "label": "Port", "field": "port", "align": "center"},
            {"name": "detail", "label": "Details", "field": "detail", "align": "left"},
        ]

        history_table = ui.table(
            columns=columns,
            rows=list(history),
            row_key="id",
        ).classes("w-full")

        # Store table reference so other sections can update rows
        table_ref[0] = history_table
