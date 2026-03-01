"""Performance monitoring CLI commands."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError


@click.group("perf")
@click.pass_context
def perf_group(ctx: click.Context) -> None:
    """Performance monitoring commands."""
    ctx.ensure_object(dict)


@perf_group.command("bw")
@click.argument("device_path")
@click.option(
    "--ports",
    required=True,
    help="Comma-separated list of physical port IDs.",
)
@click.option("--clear", is_flag=True, default=False, help="Clear counters after reading.")
@click.option("--watch", is_flag=True, default=False, help="Continuous monitoring mode.")
@click.option(
    "--interval",
    default=1.0,
    type=float,
    help="Seconds between samples (with --watch).",
)
@click.option(
    "--count",
    "sample_count",
    default=0,
    type=int,
    help="Number of samples, 0=infinite (with --watch).",
)
@click.pass_context
def perf_bw(
    ctx: click.Context,
    device_path: str,
    ports: str,
    clear: bool,
    watch: bool,
    interval: float,
    sample_count: int,
) -> None:
    """Get bandwidth counters for specified ports."""
    try:
        port_ids = [int(p.strip()) for p in ports.split(",")]
    except ValueError:
        click.echo("Error: --ports must be comma-separated integers", err=True)
        raise click.Abort()

    for pid in port_ids:
        if not (0 <= pid <= 59):
            click.echo(f"Error: port_id {pid} out of range 0-59", err=True)
            raise click.Abort()

    try:
        with SwitchtecDevice.open(device_path) as dev:
            if watch:
                json_output = ctx.obj.get("json_output")
                for sample in dev.monitor.watch_bw(
                    port_ids, interval=interval, count=sample_count
                ):
                    if json_output:
                        click.echo(sample.model_dump_json())
                    else:
                        click.echo(
                            f"[{sample.elapsed_s:>8.1f}s] Port {sample.port_id}: "
                            f"egress={sample.egress_total} "
                            f"ingress={sample.ingress_total} "
                            f"(time={sample.time_us} us)"
                        )
            else:
                results = dev.performance.bw_get(port_ids, clear=clear)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps(
                        [r.model_dump() for r in results], indent=2
                    ))
                else:
                    for port_id, r in zip(port_ids, results):
                        click.echo(f"Port {port_id} (time={r.time_us} us):")
                        click.echo(
                            f"  Egress:  posted={r.egress.posted} "
                            f"comp={r.egress.comp} "
                            f"nonposted={r.egress.nonposted} "
                            f"total={r.egress.total}"
                        )
                        click.echo(
                            f"  Ingress: posted={r.ingress.posted} "
                            f"comp={r.ingress.comp} "
                            f"nonposted={r.ingress.nonposted} "
                            f"total={r.ingress.total}"
                        )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
    except KeyboardInterrupt:
        click.echo("\nMonitoring stopped.")


@perf_group.command("latency-setup")
@click.argument("device_path")
@click.option("--egress", required=True, type=click.IntRange(0, 59), help="Egress port ID.")
@click.option("--ingress", required=True, type=click.IntRange(0, 59), help="Ingress port ID.")
@click.option("--clear", is_flag=True, default=False, help="Clear counters.")
def perf_latency_setup(
    device_path: str, egress: int, ingress: int, clear: bool
) -> None:
    """Configure latency measurement between two ports."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.performance.lat_setup(egress, ingress, clear=clear)
            click.echo(
                f"Latency measurement configured: egress={egress} ingress={ingress}"
            )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@perf_group.command("latency")
@click.argument("device_path")
@click.option("--egress", required=True, type=click.IntRange(0, 59), help="Egress port ID.")
@click.option("--clear", is_flag=True, default=False, help="Clear counters after reading.")
@click.pass_context
def perf_latency(
    ctx: click.Context, device_path: str, egress: int, clear: bool
) -> None:
    """Get latency measurement for an egress port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.performance.lat_get(egress, clear=clear)
            if ctx.obj.get("json_output"):
                click.echo(result.model_dump_json(indent=2))
            else:
                click.echo(f"Port {egress}: current={result.current_ns} ns  max={result.max_ns} ns")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
