"""Event management CLI commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("events")
@click.pass_context
def events_group(ctx: click.Context) -> None:
    """Event management commands."""
    ctx.ensure_object(dict)


@events_group.command("summary")
@click.argument("device_path")
@click.pass_context
def events_summary(ctx: click.Context, device_path: str) -> None:
    """Show event summary counts."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            summary = dev.events.get_summary()
            if ctx.obj.get("json_output"):
                click.echo(summary.model_dump_json(indent=2))
            else:
                click.echo(f"Global events:    {summary.global_events}")
                click.echo(f"Partition events: {summary.partition_events}")
                click.echo(f"PFF events:       {summary.pff_events}")
                click.echo(f"Total:            {summary.total_count}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@events_group.command("clear")
@click.argument("device_path")
@click.pass_context
def events_clear(ctx: click.Context, device_path: str) -> None:
    """Clear all events."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.events.clear_all()
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"cleared": True}))
            else:
                click.echo("All events cleared.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@events_group.command("wait")
@click.argument("device_path")
@click.option("--timeout", default=-1, type=int, help="Timeout in milliseconds (-1 for infinite).")
@click.pass_context
def events_wait(ctx: click.Context, device_path: str, timeout: int) -> None:
    """Wait for an event to occur."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.events.wait_for_event(timeout_ms=timeout)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"event_received": True}))
            else:
                click.echo("Event received.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
