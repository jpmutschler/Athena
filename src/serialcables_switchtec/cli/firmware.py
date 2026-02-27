"""Firmware management CLI commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("fw")
@click.pass_context
def fw_group(ctx: click.Context) -> None:
    """Firmware management commands."""
    ctx.ensure_object(dict)


@fw_group.command("version")
@click.argument("device_path")
@click.pass_context
def fw_version(ctx: click.Context, device_path: str) -> None:
    """Show firmware version."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            version = dev.firmware.get_fw_version()
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"fw_version": version}))
            else:
                click.echo(f"Firmware version: {version}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fw_group.command("toggle")
@click.argument("device_path")
@click.option("--bl2", is_flag=True, default=False, help="Toggle BL2 partition.")
@click.option("--key", is_flag=True, default=False, help="Toggle key partition.")
@click.option("--fw", is_flag=True, default=False, help="Toggle firmware partition.")
@click.option("--cfg", is_flag=True, default=False, help="Toggle config partition.")
@click.option("--riot", is_flag=True, default=False, help="Toggle RIoT Core partition.")
@click.pass_context
def fw_toggle(
    ctx: click.Context,
    device_path: str,
    bl2: bool,
    key: bool,
    fw: bool,
    cfg: bool,
    riot: bool,
) -> None:
    """Toggle the active firmware partition."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.firmware.toggle_active_partition(
                toggle_bl2=bl2,
                toggle_key=key,
                toggle_fw=fw,
                toggle_cfg=cfg,
                toggle_riotcore=riot,
            )
            toggled = [
                name
                for name, flag in [
                    ("BL2", bl2),
                    ("KEY", key),
                    ("FW", fw),
                    ("CFG", cfg),
                    ("RIoT", riot),
                ]
                if flag
            ]
            label = ", ".join(toggled) if toggled else "none"
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({"toggled": toggled}))
            else:
                click.echo(f"Active partition toggled: {label}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fw_group.command("boot-ro")
@click.argument("device_path")
@click.option("--set", "set_ro", is_flag=True, default=False, help="Set boot partition read-only.")
@click.option("--clear", "clear_ro", is_flag=True, default=False, help="Clear boot partition read-only.")
@click.pass_context
def fw_boot_ro(
    ctx: click.Context,
    device_path: str,
    set_ro: bool,
    clear_ro: bool,
) -> None:
    """Show or set boot partition read-only status."""
    if set_ro and clear_ro:
        click.echo("Error: --set and --clear are mutually exclusive.", err=True)
        ctx.exit(2)
        return

    try:
        with SwitchtecDevice.open(device_path) as dev:
            if set_ro:
                dev.firmware.set_boot_ro(read_only=True)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps({"boot_ro": True}))
                else:
                    click.echo("Boot partition set to read-only.")
            elif clear_ro:
                dev.firmware.set_boot_ro(read_only=False)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps({"boot_ro": False}))
                else:
                    click.echo("Boot partition read-only cleared.")
            else:
                is_ro = dev.firmware.is_boot_ro()
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps({"boot_ro": is_ro}))
                else:
                    status = "read-only" if is_ro else "read-write"
                    click.echo(f"Boot partition: {status}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fw_group.command("read")
@click.argument("device_path")
@click.option("--address", required=True, type=str, help="Start address (hex or decimal).")
@click.option("--length", required=True, type=int, help="Number of bytes to read.")
@click.pass_context
def fw_read(ctx: click.Context, device_path: str, address: str, length: int) -> None:
    """Read raw firmware data at a given address."""
    try:
        addr = int(address, 0)
    except ValueError:
        click.echo(f"Error: invalid address '{address}'", err=True)
        ctx.exit(2)
        return

    try:
        with SwitchtecDevice.open(device_path) as dev:
            data = dev.firmware.read_firmware(addr, length)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "address": f"0x{addr:08x}",
                    "length": length,
                    "hex": data.hex(),
                }))
            else:
                click.echo(f"Address: 0x{addr:08x}  Length: {length}")
                # Print hex dump in 16-byte rows
                for offset in range(0, len(data), 16):
                    chunk = data[offset:offset + 16]
                    hex_part = " ".join(f"{b:02x}" for b in chunk)
                    click.echo(f"  {addr + offset:08x}: {hex_part}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@fw_group.command("summary")
@click.argument("device_path")
@click.pass_context
def fw_summary(ctx: click.Context, device_path: str) -> None:
    """Show firmware partition summary."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            summary = dev.firmware.get_part_summary()
            if ctx.obj.get("json_output"):
                click.echo(summary.model_dump_json(indent=2))
            else:
                click.echo(f"Boot RO: {summary.is_boot_ro}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
