"""CLI formatting helpers for workflow execution output.

Provides step headers, inline metrics, and summary tables for
the ``run-workflow`` command.
"""

from __future__ import annotations

from serialcables_switchtec.core.workflows.models import RecipeResult, StepStatus
from serialcables_switchtec.core.workflows.workflow_models import WorkflowSummary

# Keys we look for when extracting inline metrics from result data
_KNOWN_SCALAR_KEYS = (
    "total_errors",
    "errors",
    "temperature",
    "link_up",
    "ports_up",
    "ports_down",
    "total_ports",
    "eye_width",
    "eye_height",
    "eye_area_pct",
    "egress_avg_mbps",
    "ingress_avg_mbps",
    "transition_count",
    "verdict",
    "h_margin",
    "v_margin",
)


def format_step_header(step_index: int, total: int, recipe_name: str) -> str:
    """Format a step separator header.

    Example: ``=== [1/3] Cross-Hair Margin Analysis ===``
    """
    return f"=== [{step_index + 1}/{total}] {recipe_name} ==="


_STATUS_CHARS: dict[StepStatus, str] = {
    StepStatus.RUNNING: "...",
    StepStatus.PASS: "PASS",
    StepStatus.FAIL: "FAIL",
    StepStatus.WARN: "WARN",
    StepStatus.INFO: "INFO",
    StepStatus.SKIP: "SKIP",
}


def _extract_cli_metrics(data: dict | None) -> str:
    """Pick up to 3 known scalar keys from data and format inline."""
    if not data:
        return ""
    parts: list[str] = []
    for key in _KNOWN_SCALAR_KEYS:
        if key in data:
            val = data[key]
            if isinstance(val, (list, dict)):
                continue
            if isinstance(val, float):
                parts.append(f"{key}={val:.1f}")
            else:
                parts.append(f"{key}={val}")
            if len(parts) >= 3:
                break
    if not parts:
        return ""
    return f"  ({', '.join(parts)})"


def format_result_line(result: RecipeResult) -> str:
    """Format a single result line with status, detail, and inline metrics.

    Example: ``  [PASS] Check Link: Link UP  (temperature=42.1)``
    """
    status_char = _STATUS_CHARS.get(result.status, "???")
    metrics = _extract_cli_metrics(result.data)
    step_name = result.step
    if " > " in step_name:
        step_name = step_name.split(" > ", 1)[1]
    return f"  [{status_char}] {step_name}: {result.detail}{metrics}"


def format_summary_table(summary: WorkflowSummary) -> str:
    """Format a bordered summary with per-recipe breakdown.

    Returns a multi-line string.
    """
    width = 60
    lines: list[str] = []
    lines.append("=" * width)

    verdict = "ABORTED" if summary.aborted else "FINISHED"
    lines.append(
        f"  {summary.workflow_name}: {verdict} "
        f"({summary.completed_recipes}/{summary.total_recipes} recipes, "
        f"{summary.elapsed_s:.1f}s)"
    )
    lines.append("-" * width)

    for step_sum in summary.step_summaries:
        prefix = f"  [{step_sum.step_index + 1}] {step_sum.recipe_name}"
        if step_sum.skipped:
            reason = f" ({step_sum.skip_reason})" if step_sum.skip_reason else ""
            lines.append(f"{prefix}: SKIPPED{reason}")
        elif step_sum.recipe_summary:
            rs = step_sum.recipe_summary
            loop_info = ""
            if step_sum.loop_total is not None and step_sum.loop_total > 1:
                loop_info = f" x{step_sum.loop_total} iters"
            lines.append(
                f"{prefix}: "
                f"{rs.passed}P {rs.failed}F {rs.warnings}W "
                f"({rs.elapsed_s:.1f}s){loop_info}"
            )
        else:
            lines.append(f"{prefix}: NO RESULT")

    lines.append("=" * width)
    return "\n".join(lines)
