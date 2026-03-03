"""Recipe-specific metric card renderers for the live workflow monitor.

Each renderer takes a data dict (merged from ``RecipeResult.data``) and
a NiceGUI container, then populates it with metric cards.
"""

from __future__ import annotations

from collections.abc import Callable

from nicegui import ui

from serialcables_switchtec.ui.theme import COLORS

MetricRenderer = Callable[[dict, ui.column], None]


# ---------------------------------------------------------------------------
# Card helper
# ---------------------------------------------------------------------------


def _metric_card(
    label: str,
    value: str,
    color: str = COLORS.accent,
    container: ui.column | ui.row | None = None,
) -> None:
    """Render a compact metric card widget."""
    parent = container or ui
    with ui.card().classes("q-pa-sm").style(
        f"border: 1px solid {COLORS.text_muted};"
        f" background: {COLORS.bg_secondary};"
        f" min-width: 100px;"
    ):
        ui.label(label).classes("text-subtitle2").style(
            f"color: {COLORS.text_secondary};"
        )
        ui.label(value).classes("text-h6").style(
            f"color: {color};"
        )


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def _render_generic(data: dict, container: ui.column) -> None:
    """Show scalar values from data dict as key-value cards."""
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            rendered = False
            for key, val in data.items():
                if isinstance(val, (list, dict)):
                    continue
                _metric_card(str(key), str(val))
                rendered = True
            if not rendered:
                ui.label("No scalar metrics").classes("text-caption").style(
                    f"color: {COLORS.text_muted};"
                )


# ---------------------------------------------------------------------------
# Priority renderers
# ---------------------------------------------------------------------------


def _render_cross_hair_margin(data: dict, container: ui.column) -> None:
    with container:
        lanes = data.get("lanes", [])
        if not lanes or not isinstance(lanes, list):
            _render_generic(data, container)
            return

        with ui.row().classes("q-gutter-sm flex-wrap"):
            for lane in lanes:
                if not isinstance(lane, dict):
                    continue
                lane_id = lane.get("lane", "?")
                h_margin = lane.get("h_margin", 0)
                v_margin = lane.get("v_margin", 0)
                h_color = COLORS.error if h_margin < 0.1 else COLORS.success
                v_color = COLORS.error if v_margin < 0.1 else COLORS.success
                _metric_card(f"L{lane_id} H", f"{h_margin:.3f}", h_color)
                _metric_card(f"L{lane_id} V", f"{v_margin:.3f}", v_color)


def _render_ber_soak(data: dict, container: ui.column) -> None:
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            total_errors = data.get("total_errors")
            if total_errors is not None:
                color = COLORS.success if total_errors == 0 else COLORS.error
                _metric_card("Total Errors", str(total_errors), color)

            lane_errors = data.get("lane_errors", [])
            if isinstance(lane_errors, list):
                for entry in lane_errors:
                    if isinstance(entry, dict):
                        lane_id = entry.get("lane", "?")
                        errors = entry.get("errors", 0)
                        color = COLORS.success if errors == 0 else COLORS.error
                        _metric_card(f"Lane {lane_id}", str(errors), color)

        if total_errors is None and not lane_errors:
            _render_generic(data, container)


def _render_bandwidth_baseline(data: dict, container: ui.column) -> None:
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            for direction in ("egress", "ingress"):
                avg = data.get(f"{direction}_avg_mbps")
                if avg is not None:
                    _metric_card(f"{direction.title()} Avg", f"{avg:.0f} MB/s", COLORS.blue)

        if not any(data.get(f"{d}_avg_mbps") for d in ("egress", "ingress")):
            _render_generic(data, container)


def _render_link_health_check(data: dict, container: ui.column) -> None:
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            link_up = data.get("link_up")
            if link_up is not None:
                color = COLORS.success if link_up else COLORS.error
                _metric_card("Link", "UP" if link_up else "DOWN", color)

            rate = data.get("link_rate")
            if rate is not None:
                _metric_card("Rate", str(rate), COLORS.blue)

            temp = data.get("temperature")
            if temp is not None:
                color = COLORS.warning if temp > 85 else COLORS.accent
                _metric_card("Temp", f"{temp:.1f} C", color)

        if link_up is None and rate is None and temp is None:
            _render_generic(data, container)


def _render_all_port_sweep(data: dict, container: ui.column) -> None:
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            total = data.get("total_ports")
            up = data.get("ports_up")
            down = data.get("ports_down")

            if total is not None:
                _metric_card("Total", str(total), COLORS.blue)
            if up is not None:
                _metric_card("UP", str(up), COLORS.success)
            if down is not None:
                color = COLORS.error if down > 0 else COLORS.success
                _metric_card("DOWN", str(down), color)

        if total is None and up is None:
            _render_generic(data, container)


def _render_eye_quick_scan(data: dict, container: ui.column) -> None:
    with container:
        with ui.row().classes("q-gutter-sm flex-wrap"):
            width = data.get("eye_width")
            height = data.get("eye_height")
            area = data.get("eye_area_pct")

            if width is not None:
                _metric_card("Width", str(width), COLORS.accent)
            if height is not None:
                _metric_card("Height", str(height), COLORS.blue)
            if area is not None:
                _metric_card("Area", f"{area:.1f}%", COLORS.purple)

        if width is None and height is None:
            _render_generic(data, container)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_RENDERERS: dict[str, MetricRenderer] = {
    "cross_hair_margin": _render_cross_hair_margin,
    "ber_soak": _render_ber_soak,
    "bandwidth_baseline": _render_bandwidth_baseline,
    "link_health_check": _render_link_health_check,
    "all_port_sweep": _render_all_port_sweep,
    "eye_quick_scan": _render_eye_quick_scan,
}


def render_metrics(recipe_key: str, data: dict, container: ui.column) -> None:
    """Dispatch to the registered renderer for *recipe_key* or generic fallback."""
    renderer = _RENDERERS.get(recipe_key, _render_generic)
    renderer(data, container)
