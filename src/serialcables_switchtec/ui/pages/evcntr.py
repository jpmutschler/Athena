"""Event counters page for BER testing and error monitoring."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS

_MAX_STACK_ID = 7
_MAX_COUNTER_ID = 63
_MAX_NR_COUNTERS = 64

_COUNTER_COLUMNS = [
    {"name": "counter_id", "label": "Counter ID", "field": "counter_id", "align": "center"},
    {"name": "count", "label": "Count", "field": "count", "align": "right"},
    {"name": "port_mask", "label": "Port Mask", "field": "port_mask", "align": "center"},
    {"name": "type_mask", "label": "Type Mask", "field": "type_mask", "align": "center"},
    {"name": "egress", "label": "Egress", "field": "egress", "align": "center"},
    {"name": "threshold", "label": "Threshold", "field": "threshold", "align": "right"},
]


def evcntr_page() -> None:
    """Event counters page with setup, read, and clear controls."""
    from serialcables_switchtec.ui import state

    with page_layout("Event Counters", current_path="/evcntr"):
        if not state.is_connected():
            show_disconnected()
            return

        summary = state.get_summary()
        if summary is None:
            show_disconnected()
            return

        ui.label("Event Counters").classes("text-h5 q-mb-md")

        # --- Read controls ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Counter Selection").classes("text-h6 q-mb-sm")

            with ui.row().classes("w-full q-gutter-md items-end"):
                stack_id_input = ui.number(
                    label="Stack ID",
                    value=0,
                    min=0,
                    max=_MAX_STACK_ID,
                    step=1,
                ).classes("col").props("dense")

                counter_id_input = ui.number(
                    label="Counter ID",
                    value=0,
                    min=0,
                    max=_MAX_COUNTER_ID,
                    step=1,
                ).classes("col").props("dense")

                nr_counters_input = ui.number(
                    label="Number of Counters",
                    value=1,
                    min=1,
                    max=_MAX_NR_COUNTERS,
                    step=1,
                ).classes("col").props("dense")

                clear_on_read = ui.switch("Clear on Read").classes("col")

            read_status = ui.label("").classes("q-mt-sm")
            read_status.set_visibility(False)

            with ui.row().classes("q-mt-md q-gutter-sm"):
                read_btn = ui.button("Read Counts", icon="analytics").props(
                    "color=primary"
                )
                read_setup_btn = ui.button(
                    "Read Setup", icon="settings",
                ).props("color=secondary")

        # --- Setup controls ---
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Counter Setup").classes("text-h6 q-mb-sm")
            ui.label(
                "Configure an event counter on the selected stack and counter ID."
            ).style(f"color: {COLORS.text_secondary}; font-size: 0.9em;")

            with ui.row().classes("w-full q-gutter-md items-end q-mt-sm"):
                setup_port_mask = ui.number(
                    label="Port Mask (hex)",
                    value=0,
                    min=0,
                    format="%.0f",
                ).classes("col").props("dense")

                setup_type_mask = ui.number(
                    label="Type Mask (hex)",
                    value=0,
                    min=0,
                    format="%.0f",
                ).classes("col").props("dense")

                setup_threshold = ui.number(
                    label="Threshold",
                    value=0,
                    min=0,
                    format="%.0f",
                ).classes("col").props("dense")

                setup_egress = ui.switch("Egress").classes("col")

            setup_status = ui.label("").classes("q-mt-sm")
            setup_status.set_visibility(False)

            with ui.row().classes("q-mt-md q-gutter-sm"):
                setup_btn = ui.button(
                    "Apply Setup", icon="save",
                ).props("color=positive")

        # --- Counter values table ---
        with ui.card().classes("w-full q-pa-md"):
            ui.label("Counter Values").classes("text-h6 q-mb-sm")
            counter_table = ui.table(
                columns=_COUNTER_COLUMNS,
                rows=[],
                row_key="counter_id",
            ).classes("w-full")
            no_data_label = ui.label(
                "Click 'Read Counts' to load counter values."
            ).classes("text-subtitle2").style(
                f"color: {COLORS.text_secondary};"
            )

        def _get_input_values() -> tuple[int, int, int]:
            """Read and validate the stack/counter/nr inputs."""
            sid = int(stack_id_input.value or 0)
            cid = int(counter_id_input.value or 0)
            nr = int(nr_counters_input.value or 1)
            sid = max(0, min(sid, _MAX_STACK_ID))
            cid = max(0, min(cid, _MAX_COUNTER_ID))
            nr = max(1, min(nr, _MAX_NR_COUNTERS))
            if cid + nr > _MAX_NR_COUNTERS:
                nr = _MAX_NR_COUNTERS - cid
            return sid, cid, nr

        def _show_read_status(msg: str, is_error: bool = False) -> None:
            read_status.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            read_status.style(f"color: {color};")
            read_status.set_visibility(True)

        def _show_setup_status(msg: str, is_error: bool = False) -> None:
            setup_status.set_text(msg)
            color = COLORS.error if is_error else COLORS.success
            setup_status.style(f"color: {color};")
            setup_status.set_visibility(True)

        async def _on_read_counts() -> None:
            dev = state.get_active_device()
            if dev is None:
                _show_read_status("No device connected", is_error=True)
                return

            sid, cid, nr = _get_input_values()
            do_clear = bool(clear_on_read.value)

            read_btn.props("loading")
            try:
                results = await run.io_bound(
                    lambda: dev.evcntr.get_both(sid, cid, nr, clear=do_clear),
                )
                rows = [
                    {
                        "counter_id": val.counter_id,
                        "count": val.count,
                        "port_mask": (
                            f"0x{val.setup.port_mask:X}" if val.setup else "-"
                        ),
                        "type_mask": (
                            f"0x{val.setup.type_mask:X}" if val.setup else "-"
                        ),
                        "egress": (
                            "Yes" if val.setup and val.setup.egress else "No"
                        ),
                        "threshold": (
                            val.setup.threshold if val.setup else 0
                        ),
                    }
                    for val in results
                ]
                counter_table.rows = rows
                counter_table.update()
                no_data_label.set_visibility(False)

                total = sum(val.count for val in results)
                suffix = " (cleared)" if do_clear else ""
                _show_read_status(
                    f"Read {len(results)} counter(s), total count: {total}{suffix}"
                )
                ui.notify(
                    f"Read {len(results)} counter(s)",
                    type="positive",
                    position="top",
                )
            except (SwitchtecError, ValueError) as exc:
                _show_read_status(f"Read failed: {exc}", is_error=True)
                ui.notify(f"Read failed: {exc}", type="negative", position="top")
            finally:
                read_btn.props(remove="loading")

        async def _on_read_setup() -> None:
            dev = state.get_active_device()
            if dev is None:
                _show_read_status("No device connected", is_error=True)
                return

            sid, cid, nr = _get_input_values()

            read_setup_btn.props("loading")
            try:
                setups = await run.io_bound(
                    dev.evcntr.get_setup, sid, cid, nr,
                )
                rows = [
                    {
                        "counter_id": cid + i,
                        "count": "-",
                        "port_mask": f"0x{s.port_mask:X}",
                        "type_mask": f"0x{s.type_mask:X}",
                        "egress": "Yes" if s.egress else "No",
                        "threshold": s.threshold,
                    }
                    for i, s in enumerate(setups)
                ]
                counter_table.rows = rows
                counter_table.update()
                no_data_label.set_visibility(False)

                _show_read_status(f"Read setup for {len(setups)} counter(s)")
                ui.notify(
                    f"Read setup for {len(setups)} counter(s)",
                    type="positive",
                    position="top",
                )
            except (SwitchtecError, ValueError) as exc:
                _show_read_status(f"Read setup failed: {exc}", is_error=True)
                ui.notify(
                    f"Read setup failed: {exc}", type="negative", position="top",
                )
            finally:
                read_setup_btn.props(remove="loading")

        async def _on_setup() -> None:
            dev = state.get_active_device()
            if dev is None:
                _show_setup_status("No device connected", is_error=True)
                return

            sid, cid, _nr = _get_input_values()
            port_mask = int(setup_port_mask.value or 0)
            type_mask = int(setup_type_mask.value or 0)
            threshold = int(setup_threshold.value or 0)
            egress = bool(setup_egress.value)

            if port_mask < 0 or type_mask < 0 or threshold < 0:
                _show_setup_status(
                    "Port mask, type mask, and threshold must be non-negative",
                    is_error=True,
                )
                return

            setup_btn.props("loading")
            try:
                await run.io_bound(
                    lambda: dev.evcntr.setup(
                        sid, cid, port_mask, type_mask,
                        egress=egress, threshold=threshold,
                    ),
                )
                _show_setup_status(
                    f"Counter {cid} on stack {sid} configured"
                )
                ui.notify(
                    f"Counter {cid} configured on stack {sid}",
                    type="positive",
                    position="top",
                )
            except (SwitchtecError, ValueError) as exc:
                _show_setup_status(f"Setup failed: {exc}", is_error=True)
                ui.notify(f"Setup failed: {exc}", type="negative", position="top")
            finally:
                setup_btn.props(remove="loading")

        # Wire button handlers
        read_btn.on_click(_on_read_counts)
        read_setup_btn.on_click(_on_read_setup)
        setup_btn.on_click(_on_setup)
