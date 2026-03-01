"""Eye diagram heatmap chart component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.theme import plotly_layout_defaults


def eye_heatmap(
    pixels: list[float],
    x_count: int,
    y_count: int,
    title: str = "Eye Diagram",
) -> None:
    """Render an eye diagram as a Plotly heatmap."""
    # Reshape flat pixel array into 2D
    z_data = []
    for y in range(y_count):
        row = pixels[y * x_count : (y + 1) * x_count]
        z_data.append(row)

    defaults = plotly_layout_defaults()
    layout = {
        **defaults,
        "title": title,
        "xaxis": {
            **defaults["xaxis"],
            "title": "Phase (UI)",
        },
        "yaxis": {
            **defaults["yaxis"],
            "title": "Voltage (mV)",
        },
    }

    fig = {
        "data": [{
            "type": "heatmap",
            "z": z_data,
            "colorscale": "Hot",
            "reversescale": True,
        }],
        "layout": layout,
    }
    ui.plotly(fig).classes("w-full").style("height: 500px")
