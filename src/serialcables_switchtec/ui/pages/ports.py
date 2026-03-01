"""Port status page."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.components.disconnected import show_disconnected
from serialcables_switchtec.ui.layout import page_layout
from serialcables_switchtec.ui.theme import COLORS, GEN_COLORS


def ports_page() -> None:
    """Port grid with link status and detail view."""
    from serialcables_switchtec.ui import state

    with page_layout("Ports", current_path="/ports"):
        if not state.is_connected():
            show_disconnected()
            return

        ports = state.get_port_status()
        if not ports:
            _show_no_ports()
            return

        summary = state.get_summary()
        device_name = summary.name if summary else "Unknown"
        ports_up = sum(1 for p in ports if p.link_up)

        ui.label("Port Status").classes("text-h5 q-mb-sm")
        ui.label(
            f"{device_name} \u2014 {ports_up} of {len(ports)} ports linked up"
        ).classes("text-subtitle2 q-mb-md").style(
            f"color: {COLORS.text_secondary};"
        )

        # --- Port table ---
        columns = [
            {
                "name": "phys_id",
                "label": "Phys Port",
                "field": "phys_id",
                "sortable": True,
                "align": "center",
            },
            {
                "name": "log_id",
                "label": "Log Port",
                "field": "log_id",
                "sortable": True,
                "align": "center",
            },
            {
                "name": "link_status",
                "label": "Link",
                "field": "link_status",
                "align": "center",
            },
            {
                "name": "width",
                "label": "Width",
                "field": "width",
                "sortable": True,
                "align": "center",
            },
            {
                "name": "rate",
                "label": "Gen",
                "field": "rate",
                "sortable": True,
                "align": "center",
            },
            {
                "name": "ltssm",
                "label": "LTSSM State",
                "field": "ltssm",
                "align": "left",
            },
            {
                "name": "cfg_width",
                "label": "Cfg Width",
                "field": "cfg_width",
                "sortable": True,
                "align": "center",
            },
            {
                "name": "lane_rev",
                "label": "Lane Reversal",
                "field": "lane_rev",
                "align": "center",
            },
            {
                "name": "pci_bdf",
                "label": "BDF",
                "field": "pci_bdf",
                "align": "left",
            },
        ]

        rows = []
        for p in ports:
            gen_num = p.link_rate if p.link_up else 0
            gen_color = GEN_COLORS.get(gen_num, COLORS.text_muted)

            rows.append(
                {
                    "phys_id": p.port.phys_id,
                    "log_id": p.port.log_id,
                    "link_status": "UP" if p.link_up else "DOWN",
                    "link_quasar_color": "green" if p.link_up else "red",
                    "width": f"x{p.neg_lnk_width}" if p.link_up else "--",
                    "rate": f"Gen{p.link_rate}" if p.link_up else "--",
                    "gen_color": gen_color,
                    "ltssm": p.ltssm_str,
                    "cfg_width": f"x{p.cfg_lnk_width}",
                    "lane_rev": p.lane_reversal_str or "None",
                    "pci_bdf": p.pci_bdf or "--",
                }
            )

        table = ui.table(
            columns=columns,
            rows=rows,
            row_key="phys_id",
        ).classes("w-full")

        # Color-coded link status badge
        table.add_slot(
            "body-cell-link_status",
            '''
            <q-td :props="props">
                <q-badge
                    :color="props.row.link_quasar_color"
                    :label="props.row.link_status"
                />
            </q-td>
            ''',
        )

        # Color-coded gen column
        table.add_slot(
            "body-cell-rate",
            '''
            <q-td :props="props">
                <span :style="{color: props.row.gen_color, fontWeight: 'bold'}">
                    {{ props.row.rate }}
                </span>
            </q-td>
            ''',
        )

        # --- Refresh button ---
        ui.button(
            "Refresh",
            icon="refresh",
            on_click=lambda: ui.navigate.to("/ports"),
        ).props("color=primary outline").classes("q-mt-md")


def _show_no_ports() -> None:
    """Show empty state when no ports are found."""
    with ui.column().classes("w-full items-center q-mt-xl"):
        ui.icon("device_hub").classes("text-h1").style(
            f"color: {COLORS.text_muted};"
        )
        ui.label("No Ports Found").classes("text-h5 q-mt-md").style(
            f"color: {COLORS.text_secondary};"
        )
        ui.label(
            "The connected device reported no port status data."
        ).style(f"color: {COLORS.text_muted};")
