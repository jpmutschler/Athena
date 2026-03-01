"""Eye diagram heatmap chart component."""

from __future__ import annotations

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS, plotly_layout_defaults


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


def eye_metrics_cards(
    pixels: list[float],
    x_count: int,
    y_count: int,
) -> dict[str, float]:
    """Compute and display eye opening metrics from pixel data.

    Renders stat cards for eye width, height, and area.

    Returns:
        Dict with keys 'width', 'height', 'area_pct'.
    """
    if not pixels or x_count <= 0 or y_count <= 0:
        ui.label("No pixel data for metrics").classes("text-subtitle2")
        return {"width": 0, "height": 0, "area_pct": 0}

    peak = max(pixels) if pixels else 1.0
    threshold = peak * 0.1 if peak > 0 else 0

    # Eye width: contiguous open region in center row
    center_y = y_count // 2
    center_row = pixels[center_y * x_count : (center_y + 1) * x_count]
    width = _contiguous_below(center_row, threshold)

    # Eye height: contiguous open region in center column
    center_x = x_count // 2
    center_col = [pixels[y * x_count + center_x] for y in range(y_count)]
    height = _contiguous_below(center_col, threshold)

    # Eye area: fraction of pixels below threshold (open eye = low hit count)
    open_count = sum(1 for p in pixels if p <= threshold)
    total = len(pixels)
    area_pct = (open_count / total * 100) if total > 0 else 0

    with ui.row().classes("q-gutter-md q-mb-md flex-wrap"):
        for label, value, unit, color in [
            ("Eye Width", width, "phase steps", COLORS.accent),
            ("Eye Height", height, "voltage steps", COLORS.blue),
            ("Eye Area", f"{area_pct:.1f}", "% open", COLORS.purple),
        ]:
            with ui.card().classes("q-pa-sm").style(
                f"border: 1px solid {COLORS.text_muted};"
                f" background: {COLORS.bg_secondary};"
            ):
                ui.label(label).classes("text-subtitle2").style(
                    f"color: {COLORS.text_secondary};"
                )
                ui.label(f"{value} {unit}").classes("text-h5").style(
                    f"color: {color};"
                )

    return {"width": width, "height": height, "area_pct": area_pct}


def _contiguous_below(data: list[float], threshold: float) -> int:
    """Find the longest contiguous run of values <= threshold centered in data."""
    n = len(data)
    if n == 0:
        return 0

    center = n // 2
    # Expand outward from center
    left = center
    right = center
    while left > 0 and data[left - 1] <= threshold:
        left -= 1
    while right < n - 1 and data[right + 1] <= threshold:
        right += 1

    return right - left + 1 if data[center] <= threshold else 0
