"""Port status grid component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.models.device import PortStatus
from serialcables_switchtec.ui.theme import LINK_DOWN_COLOR, LINK_UP_COLOR


def port_grid(ports: list[PortStatus]) -> None:
    """Render a grid of port status indicators."""
    columns = [
        {"name": "phys_id", "label": "Phys Port", "field": "phys_id", "sortable": True},
        {"name": "log_id", "label": "Log Port", "field": "log_id", "sortable": True},
        {"name": "link_up", "label": "Link", "field": "link_up"},
        {"name": "neg_width", "label": "Width", "field": "neg_width"},
        {"name": "link_rate", "label": "Gen", "field": "link_rate"},
        {"name": "ltssm", "label": "LTSSM", "field": "ltssm"},
    ]

    rows = []
    for p in ports:
        rows.append({
            "phys_id": p.port.phys_id,
            "log_id": p.port.log_id,
            "link_up": "UP" if p.link_up else "DOWN",
            "neg_width": f"x{p.neg_lnk_width}",
            "link_rate": f"Gen{p.link_rate}",
            "ltssm": p.ltssm_str,
        })

    ui.table(columns=columns, rows=rows, row_key="phys_id").classes("w-full")
