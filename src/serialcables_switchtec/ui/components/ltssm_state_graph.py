"""LTSSM state graph visualization component.

Renders a directed graph of LTSSM state transitions using Plotly scatter
plots.  Nodes are sized by visit count and colored by category; edges
show transition frequency and average duration on hover.
"""

from __future__ import annotations

from html import escape

from nicegui import ui

from serialcables_switchtec.core.ltssm_graph import LtssmStateGraph
from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults

# Predefined positions for major LTSSM states
_STATE_POSITIONS: dict[str, tuple[float, float]] = {
    "Detect": (0.0, 0.8),
    "Polling": (0.2, 0.8),
    "Config": (0.4, 0.8),
    "L0": (0.6, 0.8),
    "Recovery": (0.8, 0.8),
    "L0s": (0.6, 0.5),
    "L1": (0.4, 0.5),
    "L2": (0.2, 0.5),
    "Disabled": (0.0, 0.2),
    "Hot Reset": (0.2, 0.2),
    "Loopback": (0.4, 0.2),
    "Compliance": (0.8, 0.2),
}

# State category colors
_CATEGORY_COLORS: dict[str, str] = {
    "training": COLORS.blue,
    "active": COLORS.success,
    "power": COLORS.purple,
    "error": COLORS.error,
}

_STATE_CATEGORIES: dict[str, str] = {
    "Detect": "training",
    "Polling": "training",
    "Config": "training",
    "L0": "active",
    "Recovery": "training",
    "L0s": "power",
    "L1": "power",
    "L2": "power",
    "Disabled": "error",
    "Hot Reset": "error",
    "Loopback": "training",
    "Compliance": "error",
}


def _find_position(state: str) -> tuple[float, float]:
    """Find the best position for a state, using fuzzy matching."""
    for key, pos in _STATE_POSITIONS.items():
        if key in state:
            return pos
    # Unknown state: deterministic grid placement (not using hash()
    # which is randomized per Python process via PYTHONHASHSEED)
    idx = sum(ord(c) for c in state) % 12
    row = idx // 4
    col = idx % 4
    return (col * 0.3, -0.2 - row * 0.3)


def _find_color(state: str) -> str:
    """Find the color for a state based on its category."""
    for key, cat in _STATE_CATEGORIES.items():
        if key in state:
            return _CATEGORY_COLORS[cat]
    return COLORS.text_secondary


def ltssm_state_graph(graph: LtssmStateGraph) -> None:
    """Render an LTSSM state transition graph using Plotly."""
    if not graph.states:
        ui.label("No state transitions to display.").classes("text-subtitle2").style(
            f"color: {COLORS.text_secondary};"
        )
        return

    # Compute positions and sizes
    positions = {s: _find_position(s) for s in graph.states}
    max_count = max(graph.state_counts.values()) if graph.state_counts else 1

    # Build edge traces
    edge_traces = []
    annotations = []

    for transition in graph.transitions:
        x0, y0 = positions.get(transition.from_state, (0, 0))
        x1, y1 = positions.get(transition.to_state, (0, 0))

        # Line width proportional to count
        width = max(1, min(8, transition.count))

        edge_traces.append({
            "type": "scatter",
            "x": [x0, x1, None],
            "y": [y0, y1, None],
            "mode": "lines",
            "line": {"color": COLORS.text_muted, "width": width},
            "hoverinfo": "text",
            "text": (
                f"{escape(transition.from_state)} → {escape(transition.to_state)}<br>"
                f"Count: {transition.count}<br>"
                f"Avg duration: {transition.avg_duration:.1f}"
            ),
            "showlegend": False,
        })

        # Arrow annotation at midpoint
        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2
        annotations.append({
            "x": mid_x,
            "y": mid_y,
            "text": str(transition.count),
            "showarrow": False,
            "font": {"size": 10, "color": COLORS.text_secondary},
        })

    # Build node trace
    node_x = [positions[s][0] for s in graph.states]
    node_y = [positions[s][1] for s in graph.states]
    node_sizes = [
        max(15, 40 * (graph.state_counts.get(s, 0) / max_count))
        for s in graph.states
    ]
    node_colors = [_find_color(s) for s in graph.states]
    node_text = [
        f"{escape(s)}<br>Visits: {graph.state_counts.get(s, 0)}"
        for s in graph.states
    ]

    node_trace = {
        "type": "scatter",
        "x": node_x,
        "y": node_y,
        "mode": "markers+text",
        "marker": {
            "size": node_sizes,
            "color": node_colors,
            "line": {"width": 2, "color": COLORS.text_primary},
        },
        "text": [s for s in graph.states],
        "textposition": "top center",
        "textfont": {"size": 11, "color": COLORS.text_primary},
        "hovertext": node_text,
        "hoverinfo": "text",
        "showlegend": False,
    }

    layout = {
        **plotly_layout_defaults(),
        "title": "LTSSM State Graph",
        "xaxis": {
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
        },
        "yaxis": {
            "showgrid": False,
            "zeroline": False,
            "showticklabels": False,
        },
        "annotations": annotations,
        "hovermode": "closest",
    }

    fig = {
        "data": [*edge_traces, node_trace],
        "layout": layout,
    }

    ui.plotly(fig).classes("w-full").style("height: 500px")
