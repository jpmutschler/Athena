"""Pure conversion helpers for the Workflow Builder page.

These functions convert between builder UI state dicts and Pydantic models.
Extracted to keep the main builder page under 800 lines.
"""

from __future__ import annotations

from serialcables_switchtec.core.workflows.workflow_models import (
    LoopConfig,
    OnFailAction,
    StepCondition,
    WorkflowStep,
)


def step_data_to_model(s: dict) -> WorkflowStep:
    """Convert a builder step dict to a WorkflowStep model."""
    adv = s.get("advanced", {})

    return WorkflowStep(
        recipe_key=s["recipe_key"],
        label=s.get("label", ""),
        params=dict(s.get("params", {})),
        on_fail=adv.get("on_fail", OnFailAction.ABORT),
        on_fail_goto=adv.get("on_fail_goto", ""),
        param_bindings=dict(adv.get("param_bindings", {})),
        loop=build_loop_config(adv),
        condition=build_condition(adv),
    )


def model_to_step_data(step: WorkflowStep) -> dict:
    """Convert a WorkflowStep model to a builder step dict."""
    adv: dict = {
        "on_fail": step.on_fail,
        "on_fail_goto": step.on_fail_goto,
        "param_bindings": dict(step.param_bindings),
    }

    if step.loop is not None:
        loop = step.loop
        if loop.count is not None:
            adv["loop_mode"] = "count"
            adv["loop_count"] = loop.count
        elif loop.over_values is not None:
            adv["loop_mode"] = "over_values"
            adv["loop_values"] = ",".join(str(v) for v in loop.over_values)
            adv["loop_param"] = loop.over_param
        elif loop.until_ref is not None:
            adv["loop_mode"] = "until"
            adv["loop_until_ref"] = loop.until_ref
            adv["loop_until_value"] = str(loop.until_value) if loop.until_value is not None else ""
        adv["loop_max"] = loop.max_iterations
    else:
        adv["loop_mode"] = "none"

    if step.condition is not None:
        adv["cond_enabled"] = True
        adv["cond_ref"] = step.condition.ref
        adv["cond_op"] = step.condition.operator
        adv["cond_value"] = str(step.condition.value) if step.condition.value is not None else ""
    else:
        adv["cond_enabled"] = False

    return {
        "recipe_key": step.recipe_key,
        "label": step.label,
        "params": dict(step.params),
        "advanced": adv,
    }


def build_loop_config(adv: dict) -> LoopConfig | None:
    """Build a LoopConfig from advanced step data, or None."""
    loop_mode = adv.get("loop_mode", "none")
    if loop_mode == "none":
        return None

    if loop_mode == "count":
        return LoopConfig(count=adv.get("loop_count", 3))

    if loop_mode == "over_values":
        raw = adv.get("loop_values", "")
        values = parse_loop_values(raw)
        return LoopConfig(
            over_values=values,
            over_param=adv.get("loop_param") or None,
        )

    if loop_mode == "until":
        return LoopConfig(
            until_ref=adv.get("loop_until_ref") or None,
            until_value=coerce_value(adv.get("loop_until_value", "")),
            max_iterations=adv.get("loop_max", 100),
        )

    return None


def build_condition(adv: dict) -> StepCondition | None:
    """Build a StepCondition from advanced step data, or None."""
    if not adv.get("cond_enabled", False):
        return None
    ref = (adv.get("cond_ref") or "").strip()
    if not ref:
        return None
    return StepCondition(
        ref=ref,
        operator=adv.get("cond_op", "eq"),
        value=coerce_value(adv.get("cond_value", "")),
    )


def parse_loop_values(raw: str) -> list[int | float | str]:
    """Parse comma-separated loop values with auto type coercion."""
    if not raw.strip():
        return []
    values: list[int | float | str] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        try:
            values.append(int(part))
        except ValueError:
            try:
                values.append(float(part))
            except ValueError:
                values.append(part)
    return values


def coerce_value(raw: str) -> int | float | str | bool | None:
    """Coerce a raw string value to the most appropriate type."""
    if not raw:
        return None
    if raw.lower() == "true":
        return True
    if raw.lower() == "false":
        return False
    try:
        return int(raw)
    except ValueError:
        try:
            return float(raw)
        except ValueError:
            return raw


def collect_advanced_data(adv_widgets: dict, recipe: object) -> dict:
    """Read advanced widget values into a dict."""
    adv: dict = {}

    on_fail_w = adv_widgets.get("on_fail")
    if on_fail_w is not None:
        adv["on_fail"] = getattr(on_fail_w, "value", OnFailAction.ABORT)

    goto_w = adv_widgets.get("on_fail_goto")
    if goto_w is not None:
        adv["on_fail_goto"] = getattr(goto_w, "value", "") or ""

    # Parameter bindings
    bindings: dict[str, str] = {}
    for p in recipe.parameters():
        bw = adv_widgets.get(f"bind_{p.name}")
        if bw is not None:
            val = (getattr(bw, "value", "") or "").strip()
            if val:
                bindings[p.name] = val
    adv["param_bindings"] = bindings

    # Loop config
    loop_mode_w = adv_widgets.get("loop_mode")
    adv["loop_mode"] = getattr(loop_mode_w, "value", "none") if loop_mode_w else "none"

    loop_count_w = adv_widgets.get("loop_count")
    adv["loop_count"] = int(getattr(loop_count_w, "value", 3) or 3) if loop_count_w else 3

    loop_values_w = adv_widgets.get("loop_values")
    adv["loop_values"] = getattr(loop_values_w, "value", "") or "" if loop_values_w else ""

    loop_param_w = adv_widgets.get("loop_param")
    adv["loop_param"] = getattr(loop_param_w, "value", None) if loop_param_w else None

    loop_until_ref_w = adv_widgets.get("loop_until_ref")
    adv["loop_until_ref"] = getattr(loop_until_ref_w, "value", "") or "" if loop_until_ref_w else ""

    loop_until_value_w = adv_widgets.get("loop_until_value")
    adv["loop_until_value"] = getattr(loop_until_value_w, "value", "") or "" if loop_until_value_w else ""

    loop_max_w = adv_widgets.get("loop_max")
    adv["loop_max"] = int(getattr(loop_max_w, "value", 100) or 100) if loop_max_w else 100

    # Condition
    cond_enabled_w = adv_widgets.get("cond_enabled")
    adv["cond_enabled"] = bool(getattr(cond_enabled_w, "value", False)) if cond_enabled_w else False

    cond_ref_w = adv_widgets.get("cond_ref")
    adv["cond_ref"] = getattr(cond_ref_w, "value", "") or "" if cond_ref_w else ""

    cond_op_w = adv_widgets.get("cond_op")
    adv["cond_op"] = getattr(cond_op_w, "value", "eq") if cond_op_w else "eq"

    cond_value_w = adv_widgets.get("cond_value")
    adv["cond_value"] = getattr(cond_value_w, "value", "") or "" if cond_value_w else ""

    return adv
