"""CSS-based chart primitives for workflow HTML reports.

All functions return raw HTML strings. Charts are rendered with styled
``<div>`` elements — no SVG, no JavaScript — so the report is fully
self-contained and renderable offline.
"""

from __future__ import annotations

import html
import re

from serialcables_switchtec.core.workflows.models import RecipeResult, StepStatus

# Report color palette — intentionally different from ui/theme.py COLORS.
# HTML reports use the dark-on-dark scheme from board_bringup_report.py
# for consistency with existing lab report standards.

_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")


def _esc(text: object) -> str:
    return html.escape(str(text))


def _safe_color(color: str, default: str = "#888") -> str:
    """Validate a CSS color string to prevent injection."""
    return color if _COLOR_RE.match(color) else default


# ---------------------------------------------------------------------------
# CSS bar chart
# ---------------------------------------------------------------------------


def css_bar_chart(
    bars: list[tuple[str, float]],
    max_value: float | None = None,
    bar_color: str = "#00d4ff",
    warn_threshold: float | None = None,
) -> str:
    """Horizontal bar chart using ``width: N%`` divs.

    Args:
        bars: ``(label, value)`` pairs.
        max_value: Scale reference. Defaults to the largest value.
        bar_color: Default bar color.
        warn_threshold: Values above this use red; below use *bar_color*.

    Returns:
        HTML string.
    """
    if not bars:
        return '<p style="color:#888;">No data</p>'

    effective_max = max_value if max_value is not None else max(v for _, v in bars)
    if effective_max <= 0:
        effective_max = 1.0

    safe_bar_color = _safe_color(bar_color)
    lines: list[str] = ['<div style="margin:8px 0;">']
    for label, value in bars:
        pct = min(value / effective_max * 100, 100)
        color = safe_bar_color
        if warn_threshold is not None and value > warn_threshold:
            color = "#ff4444"

        lines.append(
            f'<div style="display:flex;align-items:center;margin:3px 0;">'
            f'<span style="width:100px;font-size:0.8em;color:#aaa;text-align:right;'
            f'padding-right:8px;">{_esc(label)}</span>'
            f'<div style="flex:1;background:#1a1a2e;border-radius:3px;overflow:hidden;">'
            f'<div style="width:{pct:.1f}%;background:{color};height:18px;'
            f'border-radius:3px;min-width:2px;"></div>'
            f"</div>"
            f'<span style="width:60px;font-size:0.8em;color:#ddd;padding-left:8px;">'
            f"{_esc(f'{value:.2f}')}</span>"
            f"</div>"
        )
    lines.append("</div>")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Metric card
# ---------------------------------------------------------------------------


def css_metric_card(label: str, value: str, color: str = "#00d4ff") -> str:
    """Compact metric card with large value and small label."""
    safe = _safe_color(color)
    return (
        f'<div style="display:inline-block;background:#16213e;border:1px solid #333;'
        f'border-radius:6px;padding:10px 16px;text-align:center;margin:4px;min-width:110px;">'
        f'<div style="font-size:1.4em;color:{safe};font-weight:bold;">{_esc(value)}</div>'
        f'<div style="font-size:0.75em;color:#888;margin-top:2px;">{_esc(label)}</div>'
        f"</div>"
    )


# ---------------------------------------------------------------------------
# Status badge
# ---------------------------------------------------------------------------

_BADGE_COLORS: dict[str, str] = {
    "pass": "#00ff88",
    "fail": "#ff4444",
    "warn": "#ffaa00",
    "skip": "#666",
    "info": "#58a6ff",
}


def css_status_badge(text: str, status: str = "pass") -> str:
    """Inline status badge span with colored background."""
    bg = _BADGE_COLORS.get(status, "#666")
    return (
        f'<span style="display:inline-block;background:{bg};color:#000;'
        f'font-size:0.75em;font-weight:bold;padding:2px 8px;border-radius:3px;'
        f'margin:0 2px;">{_esc(text)}</span>'
    )


# ---------------------------------------------------------------------------
# Results table
# ---------------------------------------------------------------------------

_STATUS_MAP: dict[StepStatus, tuple[str, str]] = {
    StepStatus.PASS: ("PASS", "pass"),
    StepStatus.FAIL: ("FAIL", "fail"),
    StepStatus.WARN: ("WARN", "warn"),
    StepStatus.SKIP: ("SKIP", "skip"),
    StepStatus.INFO: ("INFO", "info"),
    StepStatus.RUNNING: ("...", "info"),
}


def css_results_table(results: list[RecipeResult]) -> str:
    """HTML table with status badges, step name, and detail columns."""
    if not results:
        return '<p style="color:#888;">No results</p>'

    lines: list[str] = [
        "<table>",
        "<tr><th>Step</th><th>Status</th><th>Criticality</th><th>Detail</th></tr>",
    ]
    for r in results:
        badge_text, badge_status = _STATUS_MAP.get(r.status, ("???", "info"))
        badge = css_status_badge(badge_text, badge_status)
        lines.append(
            f"<tr>"
            f"<td>{_esc(r.step)}</td>"
            f"<td>{badge}</td>"
            f"<td>{_esc(r.criticality.value)}</td>"
            f"<td>{_esc(r.detail)}</td>"
            f"</tr>"
        )
    lines.append("</table>")
    return "\n".join(lines)
