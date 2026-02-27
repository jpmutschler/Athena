"""Device discovery and information commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group()
@click.pass_context
def device(ctx: click.Context) -> None:
    """Device discovery and information commands."""
    ctx.ensure_object(dict)


@device.command("list")
@click.pass_context
def list_devices(ctx: click.Context) -> None:
    """List available Switchtec devices."""
    try:
        devices = SwitchtecDevice.list_devices()
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()

    if ctx.obj.get("json_output"):
        click.echo(json.dumps([d.model_dump() for d in devices], indent=2))
    else:
        if not devices:
            click.echo("No Switchtec devices found.")
            return
        for d in devices:
            click.echo(f"  {d.name}: {d.description} ({d.path})")


@device.command()
@click.argument("device_path")
@click.pass_context
def info(ctx: click.Context, device_path: str) -> None:
    """Show detailed device information."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            summary = dev.get_summary()
            if ctx.obj.get("json_output"):
                click.echo(summary.model_dump_json(indent=2))
            else:
                click.echo(f"Name:        {summary.name}")
                click.echo(f"Device ID:   0x{summary.device_id:04x}")
                click.echo(f"Generation:  {summary.generation}")
                click.echo(f"Variant:     {summary.variant}")
                click.echo(f"Boot Phase:  {summary.boot_phase}")
                click.echo(f"FW Version:  {summary.fw_version}")
                click.echo(f"Temperature: {summary.die_temperature:.1f} C")
                click.echo(f"Ports:       {summary.port_count}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@device.command()
@click.argument("device_path")
@click.pass_context
def temp(ctx: click.Context, device_path: str) -> None:
    """Read die temperature."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            t = dev.die_temperature
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"temperature_c": t}))
            else:
                click.echo(f"Die temperature: {t:.1f} C")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@device.command()
@click.argument("device_path")
@click.pass_context
def status(ctx: click.Context, device_path: str) -> None:
    """Show port status for a device."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            ports = dev.get_status()
            if ctx.obj.get("json_output"):
                click.echo(json.dumps([p.model_dump() for p in ports], indent=2))
            else:
                click.echo(f"{'Port':>6} {'Link':>6} {'Width':>6} {'Rate':>6} {'LTSSM':>30}")
                click.echo("-" * 60)
                for p in ports:
                    link = "UP" if p.link_up else "DOWN"
                    click.echo(
                        f"{p.port.phys_id:>6} {link:>6} "
                        f"x{p.neg_lnk_width:>4} Gen{p.link_rate:>3} "
                        f"{p.ltssm_str:>30}"
                    )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
