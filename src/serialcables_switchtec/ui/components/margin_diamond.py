"""Margin diamond visualization component for cross-hair results."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.models.diagnostics import CrossHairResult
from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults

_DIAMOND_COLORS = [
    "#4fc3f7", "#66bb6a", "#ffa726", "#ef5350",
    "#ab47bc", "#26c6da", "#ffee58", "#ec407a",
    "#8d6e63", "#78909c", "#d4e157", "#29b6f6",
    "#ff7043", "#5c6bc0", "#9ccc65", "#42a5f5",
]


def _build_diamond_traces(results: list[CrossHairResult]) -> list[dict]:
    """Build Plotly trace dicts for diamond-shaped margin polygons (pure data, no UI).

    Args:
        results: Cross-hair measurement results, one per lane.

    Returns:
        List of Plotly scatter trace dicts.
    """
    traces = []
    for idx, r in enumerate(results):
        color = _DIAMOND_COLORS[idx % len(_DIAMOND_COLORS)]
        # Average top/bottom limits for vertical, left/right for horizontal
        top = (r.eye_top_left_lim + r.eye_top_right_lim) / 2
        bot = -(r.eye_bot_left_lim + r.eye_bot_right_lim) / 2
        left = -r.eye_left_lim
        right = r.eye_right_lim

        x = [0, right, 0, left, 0]
        y = [top, 0, bot, 0, top]

        traces.append({
            "type": "scatter",
            "x": x,
            "y": y,
            "mode": "lines",
            "fill": "toself",
            "fillcolor": color.replace(")", ", 0.15)").replace("rgb", "rgba")
            if color.startswith("rgb") else f"{color}26",
            "line": {"color": color, "width": 2},
            "name": f"Lane {r.lane_id}",
            "hovertemplate": (
                f"Lane {r.lane_id}<br>"
                "X: %{x}<br>Y: %{y}<extra></extra>"
            ),
        })
    return traces


def margin_diamond(results: list[CrossHairResult]) -> None:
    """Render diamond-shaped margin polygons for cross-hair results.

    Each lane is drawn as a filled polygon:
    (0, top) -> (right, 0) -> (0, bot) -> (left, 0) -> (0, top)
    """
    if not results:
        ui.label("No margin data").classes("text-subtitle1")
        return

    traces = _build_diamond_traces(results)

    fig = {
        "data": traces,
        "layout": {
            **plotly_layout_defaults(),
            "title": "Margin Diamond",
            "xaxis": {
                **plotly_layout_defaults()["xaxis"],
                "title": "Horizontal (phase steps)",
                "zeroline": True,
                "zerolinecolor": COLORS.text_muted,
            },
            "yaxis": {
                **plotly_layout_defaults()["yaxis"],
                "title": "Vertical (voltage steps)",
                "zeroline": True,
                "zerolinecolor": COLORS.text_muted,
                "scaleanchor": "x",
            },
            "legend": {
                "font": {"color": COLORS.text_secondary},
                "bgcolor": "rgba(0,0,0,0)",
            },
        },
    }
    ui.plotly(fig).classes("w-full").style("height: 500px")
