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
@click.option("--ep-number", default=0, type=int, help="Number of endpoint functions to bind.")
@click.option("--ep-pdfid", multiple=True, type=int, help="Endpoint PD Function ID(s), up to 8.")
@click.pass_context
def fabric_bind(
    ctx: click.Context,
    device_path: str,
    host_sw_idx: int,
    host_phys_port: int,
    host_log_port: int,
    ep_number: int,
    ep_pdfid: tuple[int, ...],
) -> None:
    """Bind a host port to endpoint(s) via GFMS."""
    try:
        request = GfmsBindRequest(
            host_sw_idx=host_sw_idx,
            host_phys_port_id=host_phys_port,
            host_log_port_id=host_log_port,
            ep_number=ep_number,
            ep_pdfid=list(ep_pdfid),
        )
        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.bind(request)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "bound": True,
                    "host_phys_port": host_phys_port,
                    "ep_number": ep_number,
                }))
            else:
                click.echo(
                    f"Bound host port {host_phys_port} "
                    f"({ep_number} endpoint(s))."
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("unbind")
@click.argument("device_path")
@click.option("--host-sw-idx", required=True, type=int, help="Host switch index.")
@click.option("--host-phys-port", required=True, type=click.IntRange(0, 59), help="Host physical port ID.")
@click.option("--host-log-port", required=True, type=int, help="Host logical port ID.")
@click.option("--pdfid", default=0, type=int, help="Endpoint PD Function ID to unbind.")
@click.option("--option", "unbind_option", default=0, type=int, help="Unbind option.")
@click.pass_context
def fabric_unbind(
    ctx: click.Context,
    device_path: str,
    host_sw_idx: int,
    host_phys_port: int,
    host_log_port: int,
    pdfid: int,
    unbind_option: int,
) -> None:
    """Unbind a host port from an endpoint port via GFMS."""
    try:
        request = GfmsUnbindRequest(
            host_sw_idx=host_sw_idx,
            host_phys_port_id=host_phys_port,
            host_log_port_id=host_log_port,
            pdfid=pdfid,
            option=unbind_option,
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


@fabric_group.command("csr-read")
@click.argument("device_path")
@click.option("--pdfid", required=True, type=click.IntRange(0, 0xFFFF), help="Endpoint PD Function ID.")
@click.option("--addr", required=True, type=str, help="Config space offset (hex, e.g. 0x10).")
@click.option(
    "--width",
    type=click.Choice(["8", "16", "32"]),
    default="32",
    help="Register width in bits.",
)
@click.pass_context
def fabric_csr_read(
    ctx: click.Context,
    device_path: str,
    pdfid: int,
    addr: str,
    width: str,
) -> None:
    """Read an endpoint PCIe config space register."""
    try:
        try:
            addr_int = int(addr, 0)
        except ValueError:
            raise click.BadParameter(f"invalid address: {addr!r}", param_hint="'--addr'")
        if addr_int < 0 or addr_int > 0xFFF:
            click.echo(f"Error: addr must be 0x000-0xFFF, got 0x{addr_int:x}", err=True)
            raise click.Abort()
        width_int = int(width)
        with SwitchtecDevice.open(device_path) as dev:
            value = dev.fabric.csr_read(pdfid, addr_int, width_int)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "pdfid": pdfid,
                    "addr": f"0x{addr_int:x}",
                    "width": width_int,
                    "value": f"0x{value:x}",
                }))
            else:
                click.echo(
                    f"CSR[0x{addr_int:x}] (w{width_int}) = 0x{value:x}"
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fabric_group.command("csr-write")
@click.argument("device_path")
@click.option("--pdfid", required=True, type=click.IntRange(0, 0xFFFF), help="Endpoint PD Function ID.")
@click.option("--addr", required=True, type=str, help="Config space offset (hex, e.g. 0x10).")
@click.option("--value", required=True, type=str, help="Value to write (hex, e.g. 0xFF).")
@click.option(
    "--width",
    type=click.Choice(["8", "16", "32"]),
    default="32",
    help="Register width in bits.",
)
@click.pass_context
def fabric_csr_write(
    ctx: click.Context,
    device_path: str,
    pdfid: int,
    addr: str,
    value: str,
    width: str,
) -> None:
    """Write an endpoint PCIe config space register."""
    try:
        try:
            addr_int = int(addr, 0)
        except ValueError:
            raise click.BadParameter(f"invalid address: {addr!r}", param_hint="'--addr'")
        if addr_int < 0 or addr_int > 0xFFF:
            click.echo(f"Error: addr must be 0x000-0xFFF, got 0x{addr_int:x}", err=True)
            raise click.Abort()
        try:
            value_int = int(value, 0)
        except ValueError:
            raise click.BadParameter(f"invalid value: {value!r}", param_hint="'--value'")
        width_int = int(width)
        max_val = (1 << width_int) - 1
        if value_int < 0 or value_int > max_val:
            click.echo(
                f"Error: value 0x{value_int:x} exceeds {width_int}-bit max 0x{max_val:x}",
                err=True,
            )
            raise click.Abort()
        with SwitchtecDevice.open(device_path) as dev:
            dev.fabric.csr_write(pdfid, addr_int, value_int, width_int)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "pdfid": pdfid,
                    "addr": f"0x{addr_int:x}",
                    "width": width_int,
                    "value": f"0x{value_int:x}",
                    "written": True,
                }))
            else:
                click.echo(
                    f"CSR[0x{addr_int:x}] (w{width_int}) <- 0x{value_int:x}"
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
