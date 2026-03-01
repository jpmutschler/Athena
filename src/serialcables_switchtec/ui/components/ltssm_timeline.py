"""LTSSM state timeline component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.models.diagnostics import LtssmLogEntry
from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults


def ltssm_timeline(entries: list[LtssmLogEntry]) -> None:
    """Render LTSSM state transitions as a timeline chart."""
    if not entries:
        ui.label("No LTSSM log entries").classes("text-subtitle1")
        return

    timestamps = [e.timestamp for e in entries]
    states = [e.link_state for e in entries]
    labels = [e.link_state_str for e in entries]

    layout = {
        **plotly_layout_defaults(),
        "title": "LTSSM State Transitions",
        "xaxis": {
            **plotly_layout_defaults()["xaxis"],
            "title": "Timestamp",
        },
        "yaxis": {
            **plotly_layout_defaults()["yaxis"],
            "title": "State",
        },
    }

    fig = {
        "data": [{
            "type": "scatter",
            "x": timestamps,
            "y": states,
            "mode": "lines+markers",
            "text": labels,
            "hovertemplate": "%{text}<br>Time: %{x}<extra></extra>",
            "line": {"color": COLORS.blue, "width": 2},
            "marker": {"size": 6},
        }],
        "layout": layout,
    }
    ui.plotly(fig).classes("w-full").style("height: 400px")
