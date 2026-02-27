"""Fabric topology management CLI commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.bindings.constants import (
    FabHotResetFlag,
    FabPortControlType,
)
from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError
from serialcables_switchtec.models.fabric import GfmsBindRequest, GfmsUnbindRequest

_ACTION_MAP = {
    "enable": FabPortControlType.ENABLE,
    "disable": FabPortControlType.DISABLE,
    "hot-reset": FabPortControlType.HOT_RESET,
}


@click.group("fabric")
@click.pass_context
def fabric_group(ctx: click.Context) -> None:
    """Fabric topology management commands (PAX devices)."""
    ctx.ensure_object(dict)


@fabric_group.command("port-control")
@click.argument("device_path")
@click.option("--port", required=True, type=click.IntRange(0, 59), help="Physical port ID.")
@click.option(
    "--action",
    required=True,
    type=click.Choice(list(_ACTION_MAP.keys()), case_sensitive=False),
    help="Port control action.",
)
@click.option("--hot-reset-flag", default="none", type=click.Choice(["none", "perst"]),
              help="Hot reset flag (only for hot-reset action).")
@click.pass_context
def fabric_port_control(
    ctx: click.Context,
    device_path: str,
    port: int,
    action: str,
    hot_reset_flag: str,
) -> None:
    """Enable, disable, or hot-reset a fabric port."""
    try:
        control_type = _ACTION_MAP[action.lower()]
        hr_flag = FabHotResetFlag.NONE
        if hot_reset_flag == "perst":
            hr_flag = FabHotResetFlag(1)

        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.port_control(port, control_type, hr_flag)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "port": port,
                    "action": action,
                }))
            else:
                click.echo(f"Port {port}: {action} complete.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("port-config")
@click.argument("device_path")
@click.option("--port", required=True, type=click.IntRange(0, 59), help="Physical port ID.")
@click.pass_context
def fabric_port_config(ctx: click.Context, device_path: str, port: int) -> None:
    """Get fabric port configuration."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            config = dev.fabric.get_port_config(port)
            if ctx.obj.get("json_output"):
                click.echo(config.model_dump_json(indent=2))
            else:
                click.echo(f"Port {config.phys_port_id}:")
                click.echo(f"  Type:         {config.port_type}")
                click.echo(f"  Clock Source: {config.clock_source}")
                click.echo(f"  Clock SRIS:   {config.clock_sris}")
                click.echo(f"  HVD Instance: {config.hvd_inst}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("bind")
@click.argument("device_path")
@click.option("--host-sw-idx", required=True, type=int, help="Host switch index.")
@click.option("--host-phys-port", required=True, type=click.IntRange(0, 59), help="Host physical port ID.")
@click.option("--host-log-port", required=True, type=int, help="Host logical port ID.")
@click.option("--ep-sw-idx", required=True, type=int, help="Endpoint switch index.")
@click.option("--ep-phys-port", required=True, type=click.IntRange(0, 59), help="Endpoint physical port ID.")
@click.pass_context
def fabric_bind(
    ctx: click.Context,
    device_path: str,
    host_sw_idx: int,
    host_phys_port: int,
    host_log_port: int,
    ep_sw_idx: int,
    ep_phys_port: int,
) -> None:
    """Bind a host port to an endpoint port via GFMS."""
    try:
        request = GfmsBindRequest(
            host_sw_idx=host_sw_idx,
            host_phys_port_id=host_phys_port,
            host_log_port_id=host_log_port,
            ep_sw_idx=ep_sw_idx,
            ep_phys_port_id=ep_phys_port,
        )
        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.bind(request)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "bound": True,
                    "host_phys_port": host_phys_port,
                    "ep_phys_port": ep_phys_port,
                }))
            else:
                click.echo(
                    f"Bound host port {host_phys_port} to "
                    f"endpoint port {ep_phys_port}."
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("unbind")
@click.argument("device_path")
@click.option("--host-sw-idx", required=True, type=int, help="Host switch index.")
@click.option("--host-phys-port", required=True, type=click.IntRange(0, 59), help="Host physical port ID.")
@click.option("--host-log-port", required=True, type=int, help="Host logical port ID.")
@click.option("--opt", default=0, type=int, help="Unbind option.")
@click.pass_context
def fabric_unbind(
    ctx: click.Context,
    device_path: str,
    host_sw_idx: int,
    host_phys_port: int,
    host_log_port: int,
    opt: int,
) -> None:
    """Unbind a host port from an endpoint port via GFMS."""
    try:
        request = GfmsUnbindRequest(
            host_sw_idx=host_sw_idx,
            host_phys_port_id=host_phys_port,
            host_log_port_id=host_log_port,
            opt=opt,
        )
        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.unbind(request)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "unbound": True,
                    "host_phys_port": host_phys_port,
                }))
            else:
                click.echo(f"Unbound host port {host_phys_port}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("clear-events")
@click.argument("device_path")
@click.pass_context
def fabric_clear_events(ctx: click.Context, device_path: str) -> None:
    """Clear all GFMS events."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.clear_gfms_events()
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"cleared": True}))
            else:
                click.echo("GFMS events cleared.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
