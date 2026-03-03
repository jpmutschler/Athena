"""Recipe-specific HTML section renderers for workflow reports.

Each renderer receives a ``WorkflowStepSummary`` and returns an HTML
fragment.  Recipes without a custom renderer fall back to the generic
results table.
"""

from __future__ import annotations

from collections.abc import Callable

from serialcables_switchtec.core.workflows.models import RecipeResult, StepStatus
from serialcables_switchtec.core.workflows.report_charts import (
    _esc,
    css_bar_chart,
    css_metric_card,
    css_results_table,
    css_status_badge,
)
from serialcables_switchtec.core.workflows.workflow_models import WorkflowStepSummary

RecipeSectionRenderer = Callable[[WorkflowStepSummary], str]


# ---------------------------------------------------------------------------
# Generic fallback
# ---------------------------------------------------------------------------


def _render_generic_section(step_summary: WorkflowStepSummary) -> str:
    """Standard results table that every recipe gets."""
    rs = step_summary.recipe_summary
    if rs is None:
        return '<p style="color:#888;">No results recorded.</p>'
    return css_results_table(list(rs.results))


# ---------------------------------------------------------------------------
# Helper: extract merged data from all results
# ---------------------------------------------------------------------------


def _merged_data(step_summary: WorkflowStepSummary) -> dict:
    rs = step_summary.recipe_summary
    if rs is None:
        return {}
    merged: dict = {}
    for r in rs.results:
        if r.data:
            merged.update(r.data)
    return merged


# ---------------------------------------------------------------------------
# Priority renderers
# ---------------------------------------------------------------------------


def _render_cross_hair_margin(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    lanes = data.get("lanes", [])
    if lanes and isinstance(lanes, list):
        h_bars = []
        v_bars = []
        for lane in lanes:
            if isinstance(lane, dict):
                label = f"Lane {lane.get('lane', '?')}"
                h_margin = lane.get("h_margin", 0)
                v_margin = lane.get("v_margin", 0)
                h_bars.append((label, float(h_margin)))
                v_bars.append((label, float(v_margin)))

        if h_bars:
            parts.append("<h4 style='color:#7ec8e3;'>Horizontal Margin</h4>")
            parts.append(css_bar_chart(h_bars, warn_threshold=0.3))
        if v_bars:
            parts.append("<h4 style='color:#7ec8e3;'>Vertical Margin</h4>")
            parts.append(css_bar_chart(v_bars, warn_threshold=0.3))

    return "\n".join(parts)


def _render_ber_soak(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    total_errors = data.get("total_errors", None)
    if total_errors is not None:
        color = "#00ff88" if total_errors == 0 else "#ff4444"
        parts.append(css_metric_card("Total Errors", str(total_errors), color))

    lane_errors = data.get("lane_errors", [])
    if lane_errors and isinstance(lane_errors, list):
        bars = []
        for entry in lane_errors:
            if isinstance(entry, dict):
                label = f"Lane {entry.get('lane', '?')}"
                errors = entry.get("errors", 0)
                bars.append((label, float(errors)))
        if bars:
            parts.append("<h4 style='color:#7ec8e3;'>Per-Lane Errors</h4>")
            parts.append(css_bar_chart(bars, bar_color="#ff4444"))

    return "\n".join(parts)


def _render_bandwidth_baseline(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    cards: list[str] = []
    for direction in ("egress", "ingress"):
        avg = data.get(f"{direction}_avg_mbps")
        if avg is not None:
            cards.append(css_metric_card(f"{direction.title()} Avg", f"{avg:.0f} MB/s"))
        min_val = data.get(f"{direction}_min_mbps")
        max_val = data.get(f"{direction}_max_mbps")
        if min_val is not None and max_val is not None:
            bars = [
                ("Min", float(min_val)),
                ("Max", float(max_val)),
            ]
            if avg is not None:
                bars.insert(1, ("Avg", float(avg)))
            parts.append(f"<h4 style='color:#7ec8e3;'>{direction.title()} Bandwidth</h4>")
            parts.append(css_bar_chart(bars))

    if cards:
        parts.insert(1, '<div style="margin:8px 0;">' + "".join(cards) + "</div>")

    return "\n".join(parts)


def _render_all_port_sweep(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    total = data.get("total_ports")
    up = data.get("ports_up")
    down = data.get("ports_down")

    cards: list[str] = []
    if total is not None:
        cards.append(css_metric_card("Total Ports", str(total)))
    if up is not None:
        cards.append(css_metric_card("Ports UP", str(up), "#00ff88"))
    if down is not None:
        color = "#ff4444" if down > 0 else "#00ff88"
        cards.append(css_metric_card("Ports DOWN", str(down), color))

    if cards:
        parts.insert(1, '<div style="margin:8px 0;">' + "".join(cards) + "</div>")

    port_list = data.get("ports", [])
    if port_list and isinstance(port_list, list):
        rows: list[str] = [
            "<table><tr><th>Port</th><th>Status</th><th>Rate</th><th>Width</th></tr>",
        ]
        for p in port_list:
            if isinstance(p, dict):
                link_up = p.get("link_up", False)
                badge = css_status_badge("UP", "pass") if link_up else css_status_badge("DOWN", "fail")
                rows.append(
                    f"<tr><td>{_esc(p.get('port_id', '?'))}</td>"
                    f"<td>{badge}</td>"
                    f"<td>{_esc(p.get('rate', '-'))}</td>"
                    f"<td>{_esc(p.get('width', '-'))}</td></tr>"
                )
        rows.append("</table>")
        parts.append("\n".join(rows))

    return "\n".join(parts)


def _render_eye_quick_scan(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    cards: list[str] = []
    width = data.get("eye_width")
    if width is not None:
        cards.append(css_metric_card("Eye Width", f"{width}"))
    height = data.get("eye_height")
    if height is not None:
        cards.append(css_metric_card("Eye Height", f"{height}"))
    area = data.get("eye_area_pct")
    if area is not None:
        cards.append(css_metric_card("Eye Area", f"{area:.1f}%"))

    if cards:
        parts.insert(1, '<div style="margin:8px 0;">' + "".join(cards) + "</div>")

    return "\n".join(parts)


def _render_ltssm_monitor(step_summary: WorkflowStepSummary) -> str:
    parts = [_render_generic_section(step_summary)]
    data = _merged_data(step_summary)

    patterns = data.get("patterns_detected", [])
    if patterns and isinstance(patterns, list):
        rows = ["<h4 style='color:#7ec8e3;'>Patterns Detected</h4>"]
        rows.append("<table><tr><th>Pattern</th><th>Severity</th><th>Count</th></tr>")
        for p in patterns:
            if isinstance(p, dict):
                sev = p.get("severity", "info")
                badge = css_status_badge(sev.upper(), "fail" if sev == "critical" else "warn")
                rows.append(
                    f"<tr><td>{_esc(p.get('name', '?'))}</td>"
                    f"<td>{badge}</td>"
                    f"<td>{_esc(p.get('count', 0))}</td></tr>"
                )
        rows.append("</table>")
        parts.append("\n".join(rows))

    transitions = data.get("transition_count")
    if transitions is not None:
        parts.append(css_metric_card("Transitions", str(transitions)))

    verdict = data.get("verdict")
    if verdict is not None:
        status = "pass" if verdict == "PASS" else "fail"
        parts.append(f"<p>Verdict: {css_status_badge(str(verdict), status)}</p>")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


_SECTION_RENDERERS: dict[str, RecipeSectionRenderer] = {
    "cross_hair_margin": _render_cross_hair_margin,
    "ber_soak": _render_ber_soak,
    "bandwidth_baseline": _render_bandwidth_baseline,
    "all_port_sweep": _render_all_port_sweep,
    "eye_quick_scan": _render_eye_quick_scan,
    "ltssm_monitor": _render_ltssm_monitor,
}


def render_recipe_section(step_summary: WorkflowStepSummary) -> str:
    """Dispatch to registered renderer or generic fallback."""
    renderer = _SECTION_RENDERERS.get(step_summary.recipe_key, _render_generic_section)
    return renderer(step_summary)
