"""Ordered Set Analyzer (OSA) CLI commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("osa")
@click.pass_context
def osa_group(ctx: click.Context) -> None:
    """Ordered Set Analyzer commands."""
    ctx.ensure_object(dict)


@osa_group.command("start")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.pass_context
def osa_start(ctx: click.Context, device_path: str, stack: int) -> None:
    """Start OSA capture on a stack."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.osa.start(stack)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "started", "stack": stack}))
            else:
                click.echo(f"OSA started on stack {stack}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("stop")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.pass_context
def osa_stop(ctx: click.Context, device_path: str, stack: int) -> None:
    """Stop OSA capture on a stack."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.osa.stop(stack)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "stopped", "stack": stack}))
            else:
                click.echo(f"OSA stopped on stack {stack}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("config-type")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--direction", required=True, type=click.IntRange(0, 1),
              help="Direction: 0=RX, 1=TX.")
@click.option("--lane-mask", required=True, type=int, help="Bitmask of lanes to monitor.")
@click.option("--link-rate", required=True, type=click.IntRange(0, 6),
              help="Link rate (0=invalid, 1=Gen1, ..., 6=Gen6).")
@click.option("--os-types", required=True, type=int, help="Ordered set type filter bitmask.")
@click.pass_context
def osa_config_type(
    ctx: click.Context,
    device_path: str,
    stack: int,
    direction: int,
    lane_mask: int,
    link_rate: int,
    os_types: int,
) -> None:
    """Configure OSA ordered set type filter."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.osa.configure_type(stack, direction, lane_mask, link_rate, os_types)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "configured"}))
            else:
                click.echo("OSA type filter configured.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("config-pattern")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--direction", required=True, type=click.IntRange(0, 1),
              help="Direction: 0=RX, 1=TX.")
@click.option("--lane-mask", required=True, type=int, help="Bitmask of lanes.")
@click.option("--link-rate", required=True, type=click.IntRange(0, 6),
              help="Link rate enum value.")
@click.option("--value", required=True, type=str,
              help="4 hex DWORDs pattern value, comma-separated (e.g. 0x1,0x2,0x3,0x4).")
@click.option("--mask", required=True, type=str,
              help="4 hex DWORDs pattern mask, comma-separated.")
@click.pass_context
def osa_config_pattern(
    ctx: click.Context,
    device_path: str,
    stack: int,
    direction: int,
    lane_mask: int,
    link_rate: int,
    value: str,
    mask: str,
) -> None:
    """Configure OSA pattern match filter."""
    try:
        value_data = [int(v.strip(), 0) for v in value.split(",")]
        mask_data = [int(m.strip(), 0) for m in mask.split(",")]
    except ValueError:
        click.echo("Error: --value and --mask must be comma-separated hex/int values.", err=True)
        raise click.Abort()

    if len(value_data) != 4 or len(mask_data) != 4:
        click.echo("Error: --value and --mask must each have exactly 4 DWORDs.", err=True)
        raise click.Abort()

    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.osa.configure_pattern(stack, direction, lane_mask, link_rate,
                                      value_data, mask_data)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "configured"}))
            else:
                click.echo("OSA pattern filter configured.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("capture")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--lane-mask", required=True, type=int, help="Bitmask of lanes.")
@click.option("--direction", required=True, type=click.IntRange(0, 1),
              help="Direction: 0=RX, 1=TX.")
@click.option("--drop-single-os", default=0, type=click.IntRange(0, 1),
              help="Drop single ordered sets.")
@click.option("--stop-mode", default=0, type=int, help="Stop mode.")
@click.option("--snapshot-mode", default=0, type=int, help="Snapshot mode.")
@click.option("--post-trigger", default=0, type=int, help="Post-trigger entries.")
@click.option("--os-types", default=0, type=int, help="Ordered set type filter.")
@click.pass_context
def osa_capture(
    ctx: click.Context,
    device_path: str,
    stack: int,
    lane_mask: int,
    direction: int,
    drop_single_os: int,
    stop_mode: int,
    snapshot_mode: int,
    post_trigger: int,
    os_types: int,
) -> None:
    """Configure and start OSA capture control."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.osa.capture_control(
                stack, lane_mask, direction,
                drop_single_os, stop_mode, snapshot_mode,
                post_trigger, os_types,
            )
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "capture_started"}))
            else:
                click.echo("OSA capture control configured.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("read")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--lane", required=True, type=click.IntRange(0, 143), help="Lane ID.")
@click.option("--direction", required=True, type=click.IntRange(0, 1),
              help="Direction: 0=RX, 1=TX.")
@click.pass_context
def osa_read(
    ctx: click.Context,
    device_path: str,
    stack: int,
    lane: int,
    direction: int,
) -> None:
    """Read captured OSA data."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.osa.capture_data(stack, lane, direction)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "ok", "result": result}))
            else:
                click.echo(f"Capture data result: {result}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@osa_group.command("dump-config")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.pass_context
def osa_dump_config(ctx: click.Context, device_path: str, stack: int) -> None:
    """Dump current OSA configuration."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.osa.dump_config(stack)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"status": "ok", "result": result}))
            else:
                click.echo(f"OSA config dump result: {result}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
