"""Workflow run report generator.

Produces self-contained HTML reports from completed workflow runs.
Reports use inline CSS (dark theme) and require no external assets.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from serialcables_switchtec.core.workflows.export import DeviceContext
from serialcables_switchtec.core.workflows.report_charts import (
    _esc,
    css_metric_card,
    css_status_badge,
)
from serialcables_switchtec.core.workflows.report_sections import render_recipe_section
from serialcables_switchtec.core.workflows.workflow_models import (
    WorkflowDefinition,
    WorkflowStepSummary,
    WorkflowSummary,
)

_MAX_SLUG_LENGTH = 200


def _safe_slug(name: str) -> str:
    """Convert a name to a filesystem-safe slug (matches WorkflowStorage pattern)."""
    slug = name[:_MAX_SLUG_LENGTH].lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "unnamed"


# ---------------------------------------------------------------------------
# Report CSS — dark theme extending board_bringup_report pattern
# ---------------------------------------------------------------------------

_REPORT_CSS = """\
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  background: #1a1a2e; color: #e0e0e0;
  font-family: 'Consolas', 'Courier New', monospace;
  padding: 24px; max-width: 1100px; margin: 0 auto;
}
h1 { color: #00d4ff; margin-bottom: 8px; }
h2 { color: #00d4ff; margin: 24px 0 12px 0; border-bottom: 1px solid #333; padding-bottom: 4px; }
h3 { color: #7ec8e3; margin: 16px 0 8px 0; }
h4 { color: #7ec8e3; margin: 12px 0 6px 0; font-size: 0.95em; }
.meta { color: #888; font-size: 0.9em; margin-bottom: 16px; }
table { border-collapse: collapse; margin: 8px 0 16px 0; width: 100%; }
th, td { border: 1px solid #333; padding: 6px 10px; text-align: left; font-size: 0.85em; }
th { background: #16213e; color: #00d4ff; }
td { background: #0f3460; }
.summary-grid {
  display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px; margin: 12px 0;
}
.summary-card {
  background: #16213e; border: 1px solid #333; border-radius: 6px;
  padding: 12px; text-align: center;
}
.summary-card .value { font-size: 1.6em; font-weight: bold; }
.summary-card .label { font-size: 0.8em; color: #888; margin-top: 2px; }
.verdict-banner {
  padding: 12px 20px; border-radius: 6px; margin: 16px 0;
  font-size: 1.2em; font-weight: bold; text-align: center;
}
.recipe-section {
  background: #0f3460; border: 1px solid #333; border-radius: 6px;
  padding: 16px; margin: 12px 0;
}
.recipe-header {
  display: flex; align-items: center; gap: 12px; margin-bottom: 8px;
}
hr { border: none; border-top: 1px solid #333; margin: 24px 0; }
"""


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------


class WorkflowReportInput(BaseModel):
    """All data needed to generate a workflow report."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    workflow_summary: WorkflowSummary
    workflow_definition: WorkflowDefinition
    device_context: DeviceContext
    generated_at: str = ""


# ---------------------------------------------------------------------------
# Report generator
# ---------------------------------------------------------------------------


class WorkflowReportGenerator:
    """Generates self-contained HTML workflow reports."""

    def generate(self, report_input: WorkflowReportInput) -> str:
        """Return a complete HTML report string."""
        generated_at = report_input.generated_at or datetime.now(
            tz=timezone.utc,
        ).isoformat()

        parts = [
            "<!DOCTYPE html><html lang='en'><head>",
            "<meta charset='UTF-8'>",
            f"<title>Workflow Report - {_esc(report_input.workflow_summary.workflow_name)}</title>",
            f"<style>{_REPORT_CSS}</style>",
            "</head><body>",
            self._build_header(report_input, generated_at),
            self._build_summary_dashboard(report_input.workflow_summary),
            self._build_workflow_config(report_input),
            self._build_recipe_sections(report_input.workflow_summary),
            "<hr>",
            self._build_footer(generated_at),
            "</body></html>",
        ]
        return "\n".join(parts)

    def generate_to_file(
        self,
        report_input: WorkflowReportInput,
        output_dir: Path,
    ) -> Path:
        """Write the report to an HTML file and return the path."""
        output_dir.mkdir(parents=True, exist_ok=True)
        slug = _safe_slug(report_input.workflow_summary.workflow_name)
        ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename = f"workflow_report_{slug}_{ts}.html"
        path = (output_dir / filename).resolve()
        if not path.is_relative_to(output_dir.resolve()):
            msg = f"Path escapes output directory: {path}"
            raise ValueError(msg)
        path.write_text(self.generate(report_input), encoding="utf-8")
        return path

    # -- Section builders --------------------------------------------------

    @staticmethod
    def _build_header(report_input: WorkflowReportInput, generated_at: str) -> str:
        ctx = report_input.device_context
        wf = report_input.workflow_summary
        return (
            f"<h1>Workflow Report: {_esc(wf.workflow_name)}</h1>\n"
            f'<p class="meta">'
            f"{_esc(ctx.name)} &mdash; {_esc(ctx.generation)} &mdash; "
            f"FW {_esc(ctx.fw_version)} &mdash; {_esc(generated_at)}"
            f"</p>\n"
        )

    @staticmethod
    def _build_summary_dashboard(summary: WorkflowSummary) -> str:
        total = summary.total_recipes
        completed = summary.completed_recipes
        skipped = sum(1 for s in summary.step_summaries if s.skipped)

        passed = 0
        failed = 0
        warnings = 0
        for s in summary.step_summaries:
            rs = s.recipe_summary
            if rs is not None:
                passed += rs.passed
                failed += rs.failed
                warnings += rs.warnings

        # Verdict
        if summary.aborted:
            verdict_text = "ABORTED"
            verdict_color = "#ffaa00"
        elif failed > 0:
            verdict_text = "FAILED"
            verdict_color = "#ff4444"
        elif warnings > 0:
            verdict_text = "PASSED WITH WARNINGS"
            verdict_color = "#ffaa00"
        else:
            verdict_text = "PASSED"
            verdict_color = "#00ff88"

        cards = [
            ("Total Recipes", str(total), "#00d4ff"),
            ("Completed", str(completed), "#00d4ff"),
            ("Passed", str(passed), "#00ff88"),
            ("Failed", str(failed), "#ff4444" if failed > 0 else "#00ff88"),
            ("Warnings", str(warnings), "#ffaa00" if warnings > 0 else "#00ff88"),
            ("Skipped", str(skipped), "#888"),
            ("Duration", f"{summary.elapsed_s:.1f}s", "#00d4ff"),
        ]

        lines = ["<h2>Executive Summary</h2>"]
        lines.append(
            f'<div class="verdict-banner" style="background:{verdict_color}22;'
            f'border:2px solid {verdict_color};color:{verdict_color};">'
            f"{_esc(verdict_text)}</div>"
        )
        lines.append('<div class="summary-grid">')
        for label, value, color in cards:
            lines.append(
                f'<div class="summary-card">'
                f'<div class="value" style="color:{color};">{_esc(value)}</div>'
                f'<div class="label">{_esc(label)}</div></div>'
            )
        lines.append("</div>")
        return "\n".join(lines)

    @staticmethod
    def _build_workflow_config(report_input: WorkflowReportInput) -> str:
        defn = report_input.workflow_definition
        lines = ["<h2>Workflow Configuration</h2>"]

        lines.append(f"<p><strong>Name:</strong> {_esc(defn.name)}</p>")
        if defn.description:
            lines.append(f"<p><strong>Description:</strong> {_esc(defn.description)}</p>")

        lines.append(
            "<table><tr>"
            "<th>#</th><th>Recipe Key</th><th>Label</th><th>On-Fail</th>"
            "</tr>"
        )
        for idx, step in enumerate(defn.steps):
            label = step.label or "-"
            lines.append(
                f"<tr>"
                f"<td>{idx + 1}</td>"
                f"<td>{_esc(step.recipe_key)}</td>"
                f"<td>{_esc(label)}</td>"
                f"<td>{_esc(step.on_fail.value)}</td>"
                f"</tr>"
            )
        lines.append("</table>")
        return "\n".join(lines)

    @staticmethod
    def _build_recipe_sections(summary: WorkflowSummary) -> str:
        lines = ["<h2>Recipe Results</h2>"]

        for step_sum in summary.step_summaries:
            rs = step_sum.recipe_summary

            # Determine verdict badge
            if step_sum.skipped:
                badge = css_status_badge("SKIPPED", "skip")
                duration_str = "-"
            elif rs is None:
                badge = css_status_badge("NO RESULT", "skip")
                duration_str = "-"
            elif rs.failed > 0:
                badge = css_status_badge("FAIL", "fail")
                duration_str = f"{rs.elapsed_s:.1f}s"
            elif rs.warnings > 0:
                badge = css_status_badge("WARN", "warn")
                duration_str = f"{rs.elapsed_s:.1f}s"
            else:
                badge = css_status_badge("PASS", "pass")
                duration_str = f"{rs.elapsed_s:.1f}s"

            lines.append('<div class="recipe-section">')
            lines.append(
                f'<div class="recipe-header">'
                f"<h3>[{step_sum.step_index + 1}] {_esc(step_sum.recipe_name)}</h3>"
                f" {badge}"
                f'<span style="color:#888;font-size:0.85em;margin-left:auto;">'
                f"{_esc(duration_str)}</span>"
                f"</div>"
            )

            if step_sum.skipped:
                reason = step_sum.skip_reason or "Skipped"
                lines.append(f'<p style="color:#888;">{_esc(reason)}</p>')
            else:
                lines.append(render_recipe_section(step_sum))

            # Loop iteration breakdown
            if (
                step_sum.iteration_summaries is not None
                and len(step_sum.iteration_summaries) > 1
            ):
                lines.append(
                    f"<p style='color:#888;margin-top:8px;'>"
                    f"Loop: {len(step_sum.iteration_summaries)} iterations</p>"
                )
                for i, iter_sum in enumerate(step_sum.iteration_summaries):
                    iter_badge = (
                        css_status_badge("FAIL", "fail")
                        if iter_sum.failed > 0
                        else css_status_badge("PASS", "pass")
                    )
                    lines.append(
                        f"<p style='margin-left:12px;'>"
                        f"Iteration {i + 1}: {iter_badge} "
                        f"{iter_sum.passed}P {iter_sum.failed}F "
                        f"({iter_sum.elapsed_s:.1f}s)</p>"
                    )

            lines.append("</div>")

        return "\n".join(lines)

    @staticmethod
    def _build_footer(generated_at: str) -> str:
        return (
            f'<p class="meta" style="margin-top:16px;">'
            f"Generated: {_esc(generated_at)} &mdash; "
            f"Serialcables Switchtec Workflow Report Generator</p>"
        )
