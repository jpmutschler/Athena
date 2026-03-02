"""Margin heatmap visualization and export helpers for multi-port sweep."""

from __future__ import annotations

import csv
import io
import json

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults

# Red (failing) -> Yellow (marginal) -> Green (passing) colorscale
_MARGIN_COLORSCALE: list[tuple[float, str]] = [
    [0.0, "#ef5350"],   # red — failing
    [0.3, "#ffa726"],   # orange — low margin
    [0.5, "#ffee58"],   # yellow — marginal
    [0.7, "#66bb6a"],   # green — adequate
    [1.0, "#2e7d32"],   # dark green — excellent
]


def margin_heatmap_pair(
    port_ids: list[int],
    max_lane_count: int,
    h_grid: list[list[float | None]],
    v_grid: list[list[float | None]],
    h_thresh: int,
    v_thresh: int,
    is_pam4: bool = True,
) -> None:
    """Render side-by-side H-Margin and V-Margin heatmaps.

    Args:
        port_ids: Physical port IDs for Y-axis labels.
        max_lane_count: Maximum lane count across all ports (X-axis size).
        h_grid: 2D grid [port_idx][lane_idx] of horizontal margin values.
        v_grid: 2D grid [port_idx][lane_idx] of vertical margin values.
        h_thresh: Horizontal margin warning threshold.
        v_thresh: Vertical margin warning threshold.
        is_pam4: If True, use PAM4 colorscale range (0-20); else NRZ (0-60).
    """
    z_max = 20 if is_pam4 else 60
    y_labels = [f"Port {pid}" for pid in port_ids]
    x_labels = [f"L{i}" for i in range(max_lane_count)]

    def _nan_grid(grid: list[list[float | None]]) -> list[list[float]]:
        return [
            [float("nan") if v is None else float(v) for v in row]
            for row in grid
        ]

    def _text_grid(grid: list[list[float | None]]) -> list[list[str]]:
        return [
            ["" if v is None else str(int(v)) for v in row]
            for row in grid
        ]

    def _make_heatmap(
        grid: list[list[float | None]],
        title: str,
        thresh: int,
    ) -> dict:
        z = _nan_grid(grid)
        text = _text_grid(grid)
        return {
            "data": [{
                "type": "heatmap",
                "z": z,
                "x": x_labels,
                "y": y_labels,
                "text": text,
                "texttemplate": "%{text}",
                "colorscale": _MARGIN_COLORSCALE,
                "zmin": 0,
                "zmax": z_max,
                "colorbar": {"title": "Margin", "tickfont": {"color": COLORS.text_secondary}},
                "hoverongaps": False,
            }],
            "layout": {
                **plotly_layout_defaults(),
                "title": f"{title} (threshold: {thresh})",
                "xaxis": {
                    **plotly_layout_defaults()["xaxis"],
                    "title": "Lane",
                    "dtick": 1,
                },
                "yaxis": {
                    **plotly_layout_defaults()["yaxis"],
                    "title": "Port",
                    "autorange": "reversed",
                },
            },
        }

    with ui.row().classes("w-full q-gutter-md"):
        with ui.column().classes("col"):
            fig_h = _make_heatmap(h_grid, "H-Margin", h_thresh)
            ui.plotly(fig_h).classes("w-full").style("height: 400px")
        with ui.column().classes("col"):
            fig_v = _make_heatmap(v_grid, "V-Margin", v_thresh)
            ui.plotly(fig_v).classes("w-full").style("height: 400px")


def build_margin_csv(rows: list[dict]) -> bytes:
    """Build CSV bytes from margin sweep rows.

    Expected row keys: port_id, lane_index, lane_id, h_margin, v_margin,
    verdict, eye_left_lim, eye_right_lim, eye_top_left_lim,
    eye_top_right_lim, eye_bot_left_lim, eye_bot_right_lim.
    """
    columns = [
        "port_id", "lane_index", "lane_id", "h_margin", "v_margin",
        "verdict", "eye_left_lim", "eye_right_lim", "eye_top_left_lim",
        "eye_top_right_lim", "eye_bot_left_lim", "eye_bot_right_lim",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: row.get(k, "") for k in columns})
    return buf.getvalue().encode("utf-8")


def build_margin_json(rows: list[dict], thresholds: dict) -> bytes:
    """Build JSON bytes from margin sweep rows.

    Returns: ``{"thresholds": {...}, "lanes": [...]}``
    """
    payload = {
        "thresholds": thresholds,
        "lanes": rows,
    }
    return json.dumps(payload, indent=2).encode("utf-8")
