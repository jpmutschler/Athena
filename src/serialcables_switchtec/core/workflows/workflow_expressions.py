"""Safe expression parsing and evaluation for workflow step references.

Supports references like:
  steps[0].data.temperature       — by index
  steps[-1].data.total_errors     — negative index (previous step)
  steps[link_check].data.link_up  — by label
  steps[0].data.ports.0.link_up   — nested key path
  steps[0].failed                 — boolean: did step 0 have failures?
  steps[0].passed                 — boolean: did step 0 pass?
  steps[0].status                 — string status of step

No eval() — regex parser only.
"""

from __future__ import annotations

import operator
import re
from typing import Any

# Pattern: steps[<ref>].<property>
# ref can be: integer (0, -1), or label string (link_check)
# property can be: data.<key.path>, failed, passed, status
_REF_PATTERN = re.compile(
    r"^steps\[(?P<ref>[^\]]+)\]\.(?P<prop>data(?:\.\w+)+|failed|passed|status)$"
)

_OPERATORS: dict[str, Any] = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "lt": operator.lt,
    "gte": operator.ge,
    "lte": operator.le,
    "is_true": lambda v, _: bool(v) is True,
    "is_false": lambda v, _: bool(v) is False,
}


def parse_ref(ref_str: str) -> tuple[str, str] | None:
    """Parse a reference string into (step_ref, property_path).

    Returns ``None`` if the string doesn't match the expected format.
    Rejects dunder segments (``__foo__``) for safety.
    """
    m = _REF_PATTERN.match(ref_str.strip())
    if m is None:
        return None
    prop = m.group("prop")
    # Reject dunder segments in data paths
    if prop.startswith("data."):
        for segment in prop[5:].split("."):
            if segment.startswith("__"):
                return None
    return m.group("ref"), prop


def resolve_step_index(
    step_ref: str,
    total_steps: int,
    label_index: dict[str, int],
) -> int | None:
    """Resolve a step reference to an integer index.

    *step_ref* may be an integer literal (``"0"``, ``"-1"``) or a label
    string looked up in *label_index*.  Returns ``None`` on failure.
    """
    try:
        idx = int(step_ref)
        if idx < 0:
            idx = total_steps + idx
        if 0 <= idx < total_steps:
            return idx
        return None
    except ValueError:
        return label_index.get(step_ref)


def walk_key_path(data: dict, key_path: str) -> Any:
    """Walk a dot-separated key path through nested dicts.

    ``"ports.0.link_up"`` walks ``data["ports"]["0"]["link_up"]``
    (or ``data["ports"][0]["link_up"]`` for list-like structures).

    Returns ``None`` on any missing key.
    """
    current: Any = data
    for segment in key_path.split("."):
        if isinstance(current, dict):
            if segment in current:
                current = current[segment]
            else:
                return None
        elif isinstance(current, (list, tuple)):
            try:
                current = current[int(segment)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return current


def resolve_ref(
    ref_str: str,
    step_data: dict[int, dict],
    step_failed: dict[int, bool],
    total_steps: int,
    label_index: dict[str, int],
) -> Any:
    """Resolve a full reference string to a value.

    Returns ``None`` on any resolution failure (never throws).
    """
    parsed = parse_ref(ref_str)
    if parsed is None:
        return None

    step_ref, prop = parsed
    idx = resolve_step_index(step_ref, total_steps, label_index)
    if idx is None:
        return None

    if prop == "failed":
        return step_failed.get(idx, False)
    if prop == "passed":
        return not step_failed.get(idx, True)
    if prop == "status":
        return "failed" if step_failed.get(idx, False) else "passed"

    # prop starts with "data."
    key_path = prop[5:]  # strip "data."
    data = step_data.get(idx)
    if data is None:
        return None
    return walk_key_path(data, key_path)


def evaluate_condition(
    ref: str,
    op: str,
    value: Any,
    step_data: dict[int, dict],
    step_failed: dict[int, bool],
    total_steps: int,
    label_index: dict[str, int],
) -> bool:
    """Evaluate a step condition.

    Returns ``True`` if the condition is met (step should run).
    If the reference can't be resolved, returns ``True`` (fail-open).
    """
    resolved = resolve_ref(ref, step_data, step_failed, total_steps, label_index)
    if resolved is None:
        return True  # fail-open: run step if ref missing

    op_fn = _OPERATORS.get(op)
    if op_fn is None:
        return True  # unknown operator: fail-open

    try:
        return bool(op_fn(resolved, value))
    except (TypeError, ValueError):
        return True  # comparison error: fail-open


def resolve_params(
    static_params: dict[str, Any],
    param_bindings: dict[str, str],
    step_data: dict[int, dict],
    step_failed: dict[int, bool],
    total_steps: int,
    label_index: dict[str, int],
) -> dict[str, Any]:
    """Resolve parameter bindings, falling back to static params.

    For each entry in *param_bindings*, the reference is resolved from
    the execution context.  If resolution succeeds, the bound value
    overrides the static param.  If it fails, the static value is kept.
    """
    resolved = dict(static_params)
    for param_name, ref_str in param_bindings.items():
        ref_value = resolve_ref(
            ref_str, step_data, step_failed, total_steps, label_index,
        )
        if ref_value is not None:
            resolved[param_name] = ref_value
    return resolved
