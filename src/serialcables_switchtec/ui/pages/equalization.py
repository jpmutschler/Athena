"""Equalization & margin page — TX coefficients, FOM table, receiver cal, cross-hair."""

from __future__ import annotations

from nicegui import run, ui

from serialcables_switchtec.bindings.constants import (
    DiagCrossHairState,
    DiagEnd,
    DiagLink,
)
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.components.margin_diamond import margin_diamond
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults

_END_OPTIONS = {e.value: e.name.replace("_", " ").title() for e in DiagEnd}
_LINK_OPTIONS = {lk.value: lk.name.title() for lk in DiagLink}


def equalization_page() -> None:
    """Equalization and cross-hair margin page."""
    from serialcables_switchtec.ui import state

    with page_layout("Equalization", current_path="/equalization"):
        if not state.is_connected():
            show_disconnected()
            return

        ui.label("Equalization & Margin").classes("text-h5 q-mb-md")

        # ── Section 1: TX Equalization Coefficients ──────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("TX Equalization Coefficients").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                coeff_port = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                coeff_end = ui.select(
                    options=_END_OPTIONS, label="End", value=DiagEnd.LOCAL.value,
                ).classes("w-36")
                coeff_link = ui.select(
                    options=_LINK_OPTIONS, label="Link", value=DiagLink.CURRENT.value,
                ).classes("w-32")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                coeff_btn = ui.button(
                    "Read Coefficients", icon="download",
                ).props("color=primary")
                fslf_btn = ui.button(
                    "Read FS/LF", icon="straighten",
                ).props("flat")

            coeff_container = ui.column().classes("w-full q-mt-sm")
            fslf_container = ui.column().classes("w-full q-mt-sm")

            async def _on_read_coeff() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(coeff_port.value or 0)
                end = DiagEnd(int(coeff_end.value or 0))
                link = DiagLink(int(coeff_link.value or 0))
                coeff_btn.props("loading")
                try:
                    result = await run.io_bound(
                        dev.diagnostics.port_eq_tx_coeff,
                        port, 0, end, link,
                    )
                    coeff_container.clear()
                    with coeff_container:
                        lanes = list(range(result.lane_count))
                        pre_vals = [c.pre for c in result.cursors]
                        post_vals = [c.post for c in result.cursors]

                        fig = {
                            "data": [
                                {
                                    "type": "bar",
                                    "x": lanes,
                                    "y": pre_vals,
                                    "name": "Pre-Cursor",
                                    "marker": {"color": COLORS.blue},
                                },
                                {
                                    "type": "bar",
                                    "x": lanes,
                                    "y": post_vals,
                                    "name": "Post-Cursor",
                                    "marker": {"color": COLORS.accent},
                                },
                            ],
                            "layout": {
                                **plotly_layout_defaults(),
                                "title": f"TX Coefficients - Port {port} ({end.name}, {link.name})",
                                "barmode": "group",
                                "xaxis": {
                                    **plotly_layout_defaults()["xaxis"],
                                    "title": "Lane",
                                    "dtick": 1,
                                },
                                "yaxis": {
                                    **plotly_layout_defaults()["yaxis"],
                                    "title": "Cursor Value",
                                },
                                "legend": {
                                    "font": {"color": COLORS.text_secondary},
                                    "bgcolor": "rgba(0,0,0,0)",
                                },
                            },
                        }
                        ui.plotly(fig).classes("w-full").style("height: 350px")
                    ui.notify(
                        f"Read {result.lane_count} lane coefficients",
                        type="positive", position="top",
                    )
                except SwitchtecError as exc:
                    ui.notify(f"Read coefficients failed: {exc}", type="negative", position="top")
                finally:
                    coeff_btn.props(remove="loading")

            async def _on_read_fslf() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(coeff_port.value or 0)
                end = DiagEnd(int(coeff_end.value or 0))
                link = DiagLink(int(coeff_link.value or 0))
                fslf_btn.props("loading")
                try:
                    result = await run.io_bound(
                        dev.diagnostics.port_eq_tx_fslf,
                        port, 0, 0, end, link,
                    )
                    fslf_container.clear()
                    with fslf_container:
                        with ui.row().classes("q-gutter-md"):
                            with ui.card().classes("q-pa-sm").style(
                                f"border: 1px solid {COLORS.text_muted};"
                                f" background: {COLORS.bg_secondary};"
                            ):
                                ui.label("FS").classes("text-subtitle2").style(
                                    f"color: {COLORS.text_secondary};"
                                )
                                ui.label(str(result.fs)).classes("text-h5").style(
                                    f"color: {COLORS.accent};"
                                )
                            with ui.card().classes("q-pa-sm").style(
                                f"border: 1px solid {COLORS.text_muted};"
                                f" background: {COLORS.bg_secondary};"
                            ):
                                ui.label("LF").classes("text-subtitle2").style(
                                    f"color: {COLORS.text_secondary};"
                                )
                                ui.label(str(result.lf)).classes("text-h5").style(
                                    f"color: {COLORS.blue};"
                                )
                except SwitchtecError as exc:
                    ui.notify(f"Read FS/LF failed: {exc}", type="negative", position="top")
                finally:
                    fslf_btn.props(remove="loading")

            coeff_btn.on_click(_on_read_coeff)
            fslf_btn.on_click(_on_read_fslf)

        # ── Section 2: FOM Table ─────────────────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("FOM Table").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                fom_port = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                fom_link = ui.select(
                    options=_LINK_OPTIONS, label="Link", value=DiagLink.CURRENT.value,
                ).classes("w-32")

            fom_btn = ui.button(
                "Read FOM Table", icon="table_chart",
            ).props("color=primary").classes("q-mt-sm")

            fom_container = ui.column().classes("w-full q-mt-sm")

            async def _on_read_fom() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(fom_port.value or 0)
                link = DiagLink(int(fom_link.value or 0))
                fom_btn.props("loading")
                try:
                    result = await run.io_bound(
                        dev.diagnostics.port_eq_tx_table, port, 0, link,
                    )
                    fom_container.clear()
                    with fom_container:
                        columns = [
                            {"name": "step", "label": "Step#", "field": "step", "align": "center"},
                            {"name": "pre", "label": "Pre", "field": "pre", "align": "right"},
                            {"name": "post", "label": "Post", "field": "post", "align": "right"},
                            {"name": "fom", "label": "FOM", "field": "fom", "align": "right", "sortable": True},
                            {"name": "pre_up", "label": "Pre Up", "field": "pre_up", "align": "right"},
                            {"name": "post_up", "label": "Post Up", "field": "post_up", "align": "right"},
                            {"name": "error", "label": "Error", "field": "error", "align": "center"},
                            {"name": "active", "label": "Active", "field": "active", "align": "center"},
                            {"name": "speed", "label": "Speed", "field": "speed", "align": "center"},
                        ]
                        rows = []
                        for i, step in enumerate(result.steps):
                            rows.append({
                                "step": i,
                                "pre": step.pre_cursor,
                                "post": step.post_cursor,
                                "fom": step.fom,
                                "pre_up": step.pre_cursor_up,
                                "post_up": step.post_cursor_up,
                                "error": step.error_status,
                                "active": step.active_status,
                                "speed": step.speed,
                            })
                        ui.table(
                            columns=columns, rows=rows, row_key="step",
                            pagination={"rowsPerPage": 20},
                        ).classes("w-full")
                    ui.notify(
                        f"Read {result.step_count} FOM table steps",
                        type="positive", position="top",
                    )
                except SwitchtecError as exc:
                    ui.notify(f"Read FOM table failed: {exc}", type="negative", position="top")
                finally:
                    fom_btn.props(remove="loading")

            fom_btn.on_click(_on_read_fom)

        # ── Section 3: Receiver Calibration ──────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Receiver Calibration").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                rcvr_port = ui.number(
                    label="Port ID", value=0, min=0, max=59,
                ).classes("w-24")
                rcvr_lane = ui.number(
                    label="Lane ID", value=0, min=0, max=143,
                ).classes("w-24")
                rcvr_link = ui.select(
                    options=_LINK_OPTIONS, label="Link", value=DiagLink.CURRENT.value,
                ).classes("w-32")

            rcvr_btn = ui.button(
                "Read Receiver", icon="sensors",
            ).props("color=primary").classes("q-mt-sm")

            rcvr_container = ui.column().classes("w-full q-mt-sm")

            async def _on_read_rcvr() -> None:
                dev = state.get_active_device()
                if dev is None:
                    return
                port = int(rcvr_port.value or 0)
                lane = int(rcvr_lane.value or 0)
                link = DiagLink(int(rcvr_link.value or 0))
                rcvr_btn.props("loading")
                try:
                    obj, ext = await run.io_bound(
                        lambda: (
                            dev.diagnostics.rcvr_obj(port, lane, link),
                            dev.diagnostics.rcvr_ext(port, lane, link),
                        ),
                    )
                    rcvr_container.clear()
                    with rcvr_container:
                        # Stat cards for scalar values
                        with ui.row().classes("q-gutter-md q-mb-md flex-wrap"):
                            for label, value, color in [
                                ("CTLE", obj.ctle, COLORS.accent),
                                ("Target Amplitude", obj.target_amplitude, COLORS.blue),
                                ("Speculative DFE", obj.speculative_dfe, COLORS.purple),
                                ("CTLE2 RX Mode", ext.ctle2_rx_mode, COLORS.warning),
                            ]:
                                with ui.card().classes("q-pa-sm").style(
                                    f"border: 1px solid {COLORS.text_muted};"
                                    f" background: {COLORS.bg_secondary};"
                                ):
                                    ui.label(label).classes("text-subtitle2").style(
                                        f"color: {COLORS.text_secondary};"
                                    )
                                    ui.label(str(value)).classes("text-h5").style(
                                        f"color: {color};"
                                    )

                        # DTCLK values
                        with ui.row().classes("q-gutter-md q-mb-md flex-wrap"):
                            for label, value in [
                                ("DTCLK[5]", ext.dtclk_5),
                                ("DTCLK[8:6]", ext.dtclk_8_6),
                                ("DTCLK[9]", ext.dtclk_9),
                            ]:
                                with ui.card().classes("q-pa-sm").style(
                                    f"border: 1px solid {COLORS.text_muted};"
                                    f" background: {COLORS.bg_secondary};"
                                ):
                                    ui.label(label).classes("text-subtitle2").style(
                                        f"color: {COLORS.text_secondary};"
                                    )
                                    ui.label(str(value)).classes("text-h6").style(
                                        f"color: {COLORS.text_primary};"
                                    )

                        # DFE taps bar chart
                        fig = {
                            "data": [{
                                "type": "bar",
                                "x": [f"Tap {i}" for i in range(len(obj.dynamic_dfe))],
                                "y": obj.dynamic_dfe,
                                "marker": {"color": COLORS.accent},
                            }],
                            "layout": {
                                **plotly_layout_defaults(),
                                "title": f"DFE Taps - Port {port} Lane {lane}",
                                "xaxis": {
                                    **plotly_layout_defaults()["xaxis"],
                                    "title": "Tap",
                                },
                                "yaxis": {
                                    **plotly_layout_defaults()["yaxis"],
                                    "title": "Value",
                                },
                            },
                        }
                        ui.plotly(fig).classes("w-full").style("height: 300px")

                    ui.notify("Receiver data read", type="positive", position="top")
                except SwitchtecError as exc:
                    ui.notify(f"Read receiver failed: {exc}", type="negative", position="top")
                finally:
                    rcvr_btn.props(remove="loading")

            rcvr_btn.on_click(_on_read_rcvr)

        # ── Section 4: Cross-Hair Margin ─────────────────────────────
        with ui.card().classes("w-full q-pa-md q-mb-md").style(
            f"border: 2px solid {COLORS.warning}; background: rgba(255, 167, 38, 0.05);"
        ):
            with ui.row().classes("items-center q-gutter-sm q-mb-sm"):
                ui.icon("warning").style(f"color: {COLORS.warning};")
                ui.label(
                    "Cross-hair measurement temporarily affects the lane under test."
                ).style(f"color: {COLORS.warning}; font-size: 0.9em;")

        with ui.card().classes("w-full q-pa-md q-mb-md"):
            ui.label("Cross-Hair Margin").classes("text-h6 q-mb-sm")

            with ui.row().classes("q-gutter-sm items-end flex-wrap"):
                ch_start_lane = ui.number(
                    label="Start Lane ID", value=0, min=0, max=143,
                ).classes("w-28")
                ch_num_lanes = ui.number(
                    label="Number of Lanes", value=1, min=1, max=16,
                ).classes("w-28")

            with ui.row().classes("q-mt-sm q-gutter-sm"):
                ch_start_btn = ui.button(
                    "Start Measurement", icon="play_arrow",
                ).props("color=positive")
                ch_stop_btn = ui.button(
                    "Stop", icon="stop",
                ).props("color=negative")
                ch_stop_btn.set_enabled(False)

            ch_progress_label = ui.label("").classes("text-subtitle2 q-mt-sm").style(
                f"color: {COLORS.text_secondary};"
            )

            ch_results_container = ui.column().classes("w-full q-mt-sm")
            ch_diamond_container = ui.column().classes("w-full q-mt-sm")

        ch_state: dict = {"timer": None, "measuring": False}

        async def _on_ch_start() -> None:
            dev = state.get_active_device()
            if dev is None:
                return
            start_lane = int(ch_start_lane.value or 0)

            ch_start_btn.props("loading")
            try:
                await run.io_bound(dev.diagnostics.cross_hair_enable, start_lane)
            except SwitchtecError as exc:
                ui.notify(f"Cross-hair enable failed: {exc}", type="negative", position="top")
                ch_start_btn.props(remove="loading")
                return

            ch_state["measuring"] = True
            ch_start_btn.set_enabled(False)
            ch_stop_btn.set_enabled(True)
            ch_start_lane.set_enabled(False)
            ch_num_lanes.set_enabled(False)
            ch_progress_label.set_text("Measurement in progress...")

            async def _poll_ch() -> None:
                if not ch_state["measuring"]:
                    return
                dev_inner = state.get_active_device()
                if dev_inner is None:
                    return
                start = int(ch_start_lane.value or 0)
                num = int(ch_num_lanes.value or 1)
                try:
                    results = await run.io_bound(
                        dev_inner.diagnostics.cross_hair_get, start, num,
                    )
                except SwitchtecError:
                    return

                # Check states
                all_done = all(
                    r.state == DiagCrossHairState.DONE for r in results
                )
                any_error = any(
                    r.state == DiagCrossHairState.ERROR for r in results
                )

                # Update progress
                state_names = [r.state_name for r in results]
                ch_progress_label.set_text(f"States: {', '.join(state_names)}")

                if all_done or any_error:
                    # Stop polling
                    timer = ch_state.get("timer")
                    if timer is not None:
                        timer.cancel()
                        ch_state["timer"] = None

                    ch_state["measuring"] = False

                    # Disable cross-hair
                    try:
                        await run.io_bound(dev_inner.diagnostics.cross_hair_disable)
                    except SwitchtecError:
                        pass

                    ch_start_btn.set_enabled(True)
                    ch_start_btn.props(remove="loading")
                    ch_stop_btn.set_enabled(False)
                    ch_start_lane.set_enabled(True)
                    ch_num_lanes.set_enabled(True)

                    status_text = "DONE" if all_done else "ERROR"
                    ch_progress_label.set_text(f"Measurement {status_text}")

                    # Render results table
                    ch_results_container.clear()
                    with ch_results_container:
                        columns = [
                            {"name": "lane", "label": "Lane", "field": "lane", "align": "center"},
                            {"name": "state", "label": "State", "field": "state", "align": "center"},
                            {"name": "left", "label": "Left", "field": "left", "align": "right"},
                            {"name": "right", "label": "Right", "field": "right", "align": "right"},
                            {"name": "bot_left", "label": "Bot-Left", "field": "bot_left", "align": "right"},
                            {"name": "bot_right", "label": "Bot-Right", "field": "bot_right", "align": "right"},
                            {"name": "top_left", "label": "Top-Left", "field": "top_left", "align": "right"},
                            {"name": "top_right", "label": "Top-Right", "field": "top_right", "align": "right"},
                        ]
                        rows = [
                            {
                                "lane": r.lane_id,
                                "state": r.state_name,
                                "left": r.eye_left_lim,
                                "right": r.eye_right_lim,
                                "bot_left": r.eye_bot_left_lim,
                                "bot_right": r.eye_bot_right_lim,
                                "top_left": r.eye_top_left_lim,
                                "top_right": r.eye_top_right_lim,
                            }
                            for r in results
                        ]
                        ui.table(columns=columns, rows=rows, row_key="lane").classes("w-full")

                    # Render margin diamond
                    done_results = [r for r in results if r.state == DiagCrossHairState.DONE]
                    if done_results:
                        ch_diamond_container.clear()
                        with ch_diamond_container:
                            margin_diamond(done_results)

                    ui.notify(f"Cross-hair measurement {status_text}", type="positive" if all_done else "warning", position="top")

            ch_state["timer"] = ui.timer(1.0, _poll_ch)

        async def _on_ch_stop() -> None:
            dev = state.get_active_device()
            ch_state["measuring"] = False
            timer = ch_state.get("timer")
            if timer is not None:
                timer.cancel()
                ch_state["timer"] = None

            if dev is not None:
                try:
                    await run.io_bound(dev.diagnostics.cross_hair_disable)
                except SwitchtecError:
                    pass

            ch_start_btn.set_enabled(True)
            ch_start_btn.props(remove="loading")
            ch_stop_btn.set_enabled(False)
            ch_start_lane.set_enabled(True)
            ch_num_lanes.set_enabled(True)
            ch_progress_label.set_text("Measurement stopped.")
            ui.notify("Cross-hair measurement stopped", type="info", position="top")

        ch_start_btn.on_click(_on_ch_start)
        ch_stop_btn.on_click(_on_ch_stop)
