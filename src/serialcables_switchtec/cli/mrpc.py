"""Raw MRPC command interface for firmware debugging."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("mrpc")
@click.pass_context
def mrpc_group(ctx: click.Context) -> None:
    """Raw MRPC commands for firmware debugging."""
    ctx.ensure_object(dict)


@mrpc_group.command("cmd")
@click.argument("device_path")
@click.argument("command_id", type=str)
@click.option(
    "--payload",
    default="",
    help="Hex-encoded payload bytes (e.g. 'deadbeef').",
)
@click.option(
    "--resp-len",
    default=0,
    type=click.IntRange(0, 1024),
    help="Expected response length in bytes (max 1024).",
)
@click.pass_context
def mrpc_cmd(
    ctx: click.Context,
    device_path: str,
    command_id: str,
    payload: str,
    resp_len: int,
) -> None:
    """Send a raw MRPC command.

    COMMAND_ID is the MRPC command ID (hex or decimal, e.g. 0x1 or 1).
    """
    try:
        cmd_val = int(command_id, 0)
    except ValueError:
        click.echo(f"Error: Invalid command ID: {command_id}", err=True)
        raise click.Abort()

    if cmd_val < 0 or cmd_val > 0xFFFFFFFF:
        click.echo("Error: Command ID must be 0-0xFFFFFFFF", err=True)
        raise click.Abort()

    try:
        payload_bytes = bytes.fromhex(payload) if payload else b""
    except ValueError:
        click.echo(f"Error: Invalid hex payload: {payload}", err=True)
        raise click.Abort()

    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.mrpc_cmd(
                cmd_val, payload=payload_bytes, resp_len=resp_len
            )
            if ctx.obj.get("json_output"):
                click.echo(
                    json.dumps(
                        {
                            "command": f"0x{cmd_val:x}",
                            "payload": payload,
                            "response": result.hex() if result else "",
                            "response_len": len(result),
                        }
                    )
                )
            else:
                click.echo(f"Command: 0x{cmd_val:x}")
                if payload_bytes:
                    click.echo(f"Payload: {payload_bytes.hex()}")
                if result:
                    click.echo(
                        f"Response ({len(result)} bytes): {result.hex()}"
                    )
                else:
                    click.echo("OK (no response data)")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
