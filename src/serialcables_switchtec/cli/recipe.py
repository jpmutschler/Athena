"""CLI commands for running workflow recipes."""

from __future__ import annotations

import sys
import threading

import click

from serialcables_switchtec.core.workflows import RECIPE_REGISTRY, get_recipe
from serialcables_switchtec.core.workflows.models import RecipeCategory, StepStatus


@click.group("recipe")
def recipe() -> None:
    """Manage and run workflow recipes."""


@recipe.command("list")
@click.option(
    "--category",
    type=click.Choice([c.value for c in RecipeCategory], case_sensitive=False),
    default=None,
    help="Filter recipes by category.",
)
def recipe_list(category: str | None) -> None:
    """List available recipes."""
    for name, cls in sorted(RECIPE_REGISTRY.items()):
        instance = cls()
        if category is not None and instance.category.value != category:
            continue
        click.echo(
            f"  {name:<30s}  [{instance.category.value}]  {instance.duration_label}"
        )


@recipe.command("params")
@click.argument("recipe_name")
def recipe_params(recipe_name: str) -> None:
    """Show parameters for a recipe."""
    if recipe_name not in RECIPE_REGISTRY:
        click.echo(f"Unknown recipe: {recipe_name}", err=True)
        click.echo(f"Available: {', '.join(sorted(RECIPE_REGISTRY))}", err=True)
        raise SystemExit(2)

    instance = get_recipe(recipe_name)
    params = instance.parameters()
    if not params:
        click.echo(f"{recipe_name}: no parameters")
        return

    click.echo(f"{recipe_name} parameters:")
    for p in params:
        default_str = f" (default={p.default})" if p.default is not None else ""
        required_str = " [required]" if p.required else " [optional]"
        type_str = p.param_type
        if p.choices:
            type_str = f"select({', '.join(p.choices)})"
        range_str = ""
        if p.min_val is not None or p.max_val is not None:
            lo = p.min_val if p.min_val is not None else "..."
            hi = p.max_val if p.max_val is not None else "..."
            range_str = f" [{lo}..{hi}]"
        click.echo(
            f"  {p.name:<25s}  {type_str}{range_str}{default_str}{required_str}"
        )


@recipe.command("run")
@click.argument("recipe_name")
@click.option(
    "--param", "-p",
    multiple=True,
    help="Recipe parameter as key=value. Can be repeated.",
)
@click.option(
    "--export",
    type=click.Choice(["json", "csv"]),
    default=None,
    help="Export results in the specified format.",
)
@click.option(
    "--output-dir", "-o",
    type=click.Path(),
    default=".",
    help="Output directory for exports.",
)
@click.option(
    "--device", "-d",
    default=None,
    help="Device path (e.g., /dev/switchtec0).",
)
def recipe_run(
    recipe_name: str,
    param: tuple[str, ...],
    export: str | None,
    output_dir: str,
    device: str | None,
) -> None:
    """Run a workflow recipe."""
    if recipe_name not in RECIPE_REGISTRY:
        click.echo(f"Unknown recipe: {recipe_name}", err=True)
        click.echo(f"Available: {', '.join(sorted(RECIPE_REGISTRY))}", err=True)
        raise SystemExit(2)

    # Parse --param key=value pairs
    kwargs: dict[str, object] = {}
    for kv in param:
        if "=" not in kv:
            click.echo(f"Invalid param format: {kv!r} (expected key=value)", err=True)
            raise SystemExit(2)
        key, value = kv.split("=", 1)
        # Try numeric conversion
        try:
            kwargs[key] = int(value)
        except ValueError:
            try:
                kwargs[key] = float(value)
            except ValueError:
                if value.lower() in ("true", "false"):
                    kwargs[key] = value.lower() == "true"
                else:
                    kwargs[key] = value

    # Validate params
    instance = get_recipe(recipe_name)
    valid_names = {p.name for p in instance.parameters()}
    for key in kwargs:
        if key not in valid_names:
            click.echo(
                f"Unknown parameter '{key}' for {recipe_name}. "
                f"Valid: {', '.join(sorted(valid_names))}",
                err=True,
            )
            raise SystemExit(2)

    # Open device
    if device is None:
        click.echo("No device specified. Use --device/-d.", err=True)
        raise SystemExit(2)

    from serialcables_switchtec.core.device import SwitchtecDevice

    try:
        dev = SwitchtecDevice.open(device)
    except Exception as exc:
        click.echo(f"Cannot open device {device}: {exc}", err=True)
        raise SystemExit(2) from exc

    # Run recipe
    cancel = threading.Event()
    summary = None
    try:
        try:
            gen = instance.run(dev, cancel, **kwargs)
            results = []
            try:
                while True:
                    result = next(gen)
                    results.append(result)
                    status_char = {
                        StepStatus.RUNNING: "...",
                        StepStatus.PASS: "PASS",
                        StepStatus.FAIL: "FAIL",
                        StepStatus.WARN: "WARN",
                        StepStatus.INFO: "INFO",
                        StepStatus.SKIP: "SKIP",
                    }.get(result.status, "???")
                    click.echo(
                        f"  [{status_char}] {result.step}: {result.detail}",
                        err=True,
                    )
            except StopIteration as stop:
                summary = stop.value
        except Exception as exc:
            instance.cleanup(dev, **kwargs)
            click.echo(f"Recipe failed: {exc}", err=True)
            raise SystemExit(1) from exc

        # Print summary
        if summary is not None:
            click.echo(
                f"\n{instance.name}: "
                f"{summary.passed} passed, {summary.failed} failed, "
                f"{summary.warnings} warnings, {summary.skipped} skipped "
                f"({summary.elapsed_s:.1f}s)"
            )

        # Export if requested
        if export and summary:
            from pathlib import Path

            from serialcables_switchtec.core.workflows.export import (
                RecipeRunExporter,
                _make_device_context,
            )

            try:
                context = _make_device_context(
                    device_path=device,
                    name=dev.name,
                    device_id=dev.device_id,
                    generation=dev.generation_str,
                    fw_version=dev.get_fw_version(),
                )
            except Exception:
                context = _make_device_context(device_path=device)

            exporter = RecipeRunExporter(Path(output_dir))
            if export == "json":
                path = exporter.export_json(summary, context)
            else:
                path = exporter.export_csv(summary, context)
            click.echo(f"Exported to: {path}")
    finally:
        dev.close()

    # Exit code
    if summary and summary.failed > 0:
        sys.exit(1)
    elif summary and summary.aborted:
        sys.exit(2)
