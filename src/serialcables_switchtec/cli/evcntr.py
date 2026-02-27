"""Event counter CLI commands for BER testing and error monitoring."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("evcntr")
@click.pass_context
def evcntr_group(ctx: click.Context) -> None:
    """Event counter commands for error monitoring and BER testing."""
    ctx.ensure_object(dict)


@evcntr_group.command("setup")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--counter", required=True, type=click.IntRange(0, 63), help="Counter ID.")
@click.option("--port-mask", required=True, type=str,
              help="Port mask (hex or int, e.g. 0xff).")
@click.option("--type-mask", required=True, type=str,
              help="Event type mask (hex or int, e.g. 0x7fffff for ALL).")
@click.option("--egress", is_flag=True, default=False,
              help="Count egress (default: ingress).")
@click.option("--threshold", default=0, type=int, help="Interrupt threshold.")
@click.pass_context
def evcntr_setup(
    ctx: click.Context,
    device_path: str,
    stack: int,
    counter: int,
    port_mask: str,
    type_mask: str,
    egress: bool,
    threshold: int,
) -> None:
    """Configure an event counter."""
    try:
        pm = int(port_mask, 0)
        tm = int(type_mask, 0)
    except ValueError:
        click.echo("Error: --port-mask and --type-mask must be hex or int values.", err=True)
        raise click.Abort()

    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.evcntr.setup(stack, counter, pm, tm, egress=egress, threshold=threshold)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "status": "configured",
                    "stack": stack,
                    "counter": counter,
                }))
            else:
                click.echo(
                    f"Counter {counter} on stack {stack} configured: "
                    f"port_mask=0x{pm:x} type_mask=0x{tm:x} "
                    f"{'egress' if egress else 'ingress'}"
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@evcntr_group.command("read")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--counter", required=True, type=click.IntRange(0, 63),
              help="Starting counter ID.")
@click.option("--count", default=1, type=click.IntRange(1, 64),
              help="Number of counters to read.")
@click.option("--clear", is_flag=True, default=False,
              help="Clear counters after reading.")
@click.option("--show-setup", is_flag=True, default=False,
              help="Also show counter setup configuration.")
@click.pass_context
def evcntr_read(
    ctx: click.Context,
    device_path: str,
    stack: int,
    counter: int,
    count: int,
    clear: bool,
    show_setup: bool,
) -> None:
    """Read event counter values."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            if show_setup:
                values = dev.evcntr.get_both(stack, counter, count, clear=clear)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps(
                        [v.model_dump() for v in values], indent=2,
                    ))
                else:
                    for v in values:
                        s = v.setup
                        direction = "egress" if s and s.egress else "ingress"
                        tm = f"0x{s.type_mask:x}" if s else "?"
                        click.echo(
                            f"  Counter {v.counter_id}: {v.count:>10}  "
                            f"type_mask={tm}  {direction}"
                        )
            else:
                counts = dev.evcntr.get_counts(stack, counter, count, clear=clear)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps({
                        "stack": stack,
                        "counters": [
                            {"id": counter + i, "count": c}
                            for i, c in enumerate(counts)
                        ],
                    }))
                else:
                    for i, c in enumerate(counts):
                        click.echo(f"  Counter {counter + i}: {c}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@evcntr_group.command("get-setup")
@click.argument("device_path")
@click.option("--stack", required=True, type=click.IntRange(0, 7), help="Stack ID.")
@click.option("--counter", required=True, type=click.IntRange(0, 63),
              help="Starting counter ID.")
@click.option("--count", default=1, type=click.IntRange(1, 64),
              help="Number of counters to query.")
@click.pass_context
def evcntr_get_setup(
    ctx: click.Context,
    device_path: str,
    stack: int,
    counter: int,
    count: int,
) -> None:
    """Show event counter setup configuration."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            setups = dev.evcntr.get_setup(stack, counter, count)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps(
                    [s.model_dump() for s in setups], indent=2,
                ))
            else:
                for i, s in enumerate(setups):
                    direction = "egress" if s.egress else "ingress"
                    click.echo(
                        f"  Counter {counter + i}: "
                        f"port_mask=0x{s.port_mask:x} "
                        f"type_mask=0x{s.type_mask:x} "
                        f"{direction} threshold={s.threshold}"
                    )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
