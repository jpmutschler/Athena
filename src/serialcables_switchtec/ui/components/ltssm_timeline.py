"""LTSSM state timeline component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.models.diagnostics import LtssmLogEntry


def ltssm_timeline(entries: list[LtssmLogEntry]) -> None:
    """Render LTSSM state transitions as a timeline chart."""
    if not entries:
        ui.label("No LTSSM log entries").classes("text-subtitle1")
        return

    timestamps = [e.timestamp for e in entries]
    states = [e.link_state for e in entries]
    labels = [e.link_state_str for e in entries]

    fig = {
        "data": [{
            "type": "scatter",
            "x": timestamps,
            "y": states,
            "mode": "lines+markers",
            "text": labels,
            "hovertemplate": "%{text}<br>Time: %{x}<extra></extra>",
            "line": {"color": "#4fc3f7", "width": 2},
            "marker": {"size": 6},
        }],
        "layout": {
            "title": "LTSSM State Transitions",
            "xaxis": {"title": "Timestamp"},
            "yaxis": {"title": "State"},
            "paper_bgcolor": "#2d2d3f",
            "plot_bgcolor": "#1e1e2e",
            "font": {"color": "#e0e0e0"},
        },
    }
    ui.plotly(fig).classes("w-full").style("height: 400px")
