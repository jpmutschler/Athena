"""Eye diagram heatmap chart component."""

from __future__ import annotations

from nicegui import ui


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

    fig = {
        "data": [{
            "type": "heatmap",
            "z": z_data,
            "colorscale": "Hot",
            "reversescale": True,
        }],
        "layout": {
            "title": title,
            "xaxis": {"title": "Phase (UI)"},
            "yaxis": {"title": "Voltage (mV)"},
            "paper_bgcolor": "#2d2d3f",
            "plot_bgcolor": "#1e1e2e",
            "font": {"color": "#e0e0e0"},
        },
    }
    ui.plotly(fig).classes("w-full").style("height: 500px")
