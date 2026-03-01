"""Diagnostic commands for PCIe validation."""

from __future__ import annotations

import json

import click

from serialcables_switchtec.core.device import SwitchtecDevice
from serialcables_switchtec.exceptions import SwitchtecError

_PATTERN_MAP_GEN4 = {
    "prbs7": 0, "prbs11": 1, "prbs23": 2, "prbs31": 3,
    "prbs9": 4, "prbs15": 5, "disabled": 6,
}
_PATTERN_MAP_GEN5 = {
    "prbs7": 0, "prbs11": 1, "prbs23": 2, "prbs31": 3,
    "prbs9": 4, "prbs15": 5, "prbs5": 6, "prbs20": 7, "disabled": 10,
}
_PATTERN_MAP_GEN6 = {
    "prbs7": 0, "prbs9": 1, "prbs11": 2, "prbs13": 3,
    "prbs15": 4, "prbs23": 5, "prbs31": 6, "52ui-jitter": 0x19, "disabled": 0x1a,
}
_GEN_TO_PATTERN_MAP = {
    "gen3": _PATTERN_MAP_GEN4,
    "gen4": _PATTERN_MAP_GEN4,
    "gen5": _PATTERN_MAP_GEN5,
    "gen6": _PATTERN_MAP_GEN6,
}
_ALL_PATTERN_NAMES = sorted(
    set().union(*[m.keys() for m in _GEN_TO_PATTERN_MAP.values()])
)
_SPEED_MAP = {
    "gen1": 1, "gen2": 2, "gen3": 3, "gen4": 4, "gen5": 5, "gen6": 6,
}
_LTSSM_SPEED_MAP = {
    "gen1": 0, "gen2": 1, "gen3": 2, "gen4": 3, "gen5": 4, "gen6": 5,
}


@click.group()
@click.pass_context
def diag(ctx: click.Context) -> None:
    """Diagnostic commands for PCIe validation."""
    ctx.ensure_object(dict)


@diag.command()
@click.argument("device_path")
@click.option("--lanes", default="1,0,0,0", help="Lane mask as comma-separated ints (4 values).")
@click.option("--x-step", default=1, type=int, help="X-axis step size.")
@click.option("--y-step", default=2, type=int, help="Y-axis step size.")
def eye(device_path: str, lanes: str, x_step: int, y_step: int) -> None:
    """Start eye diagram capture."""
    try:
        lane_mask = [int(x) for x in lanes.split(",")][:4]
        with SwitchtecDevice.open(device_path) as dev:
            dev.diagnostics.eye_start(lane_mask=lane_mask, x_step=x_step, y_step=y_step)
            click.echo("Eye diagram capture started.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command("eye-fetch")
@click.argument("device_path")
@click.option("--pixels", default=4096, type=int, help="Number of pixels to fetch.")
@click.pass_context
def eye_fetch(ctx: click.Context, device_path: str, pixels: int) -> None:
    """Fetch eye diagram data from an in-progress capture."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.diagnostics.eye_fetch(pixels)
            if ctx.obj.get("json_output"):
                click.echo(result.model_dump_json(indent=2))
            else:
                click.echo(f"Lane: {result.lane_id}")
                click.echo(f"Pixels fetched: {len(result.pixels)}")
                non_zero = sum(1 for p in result.pixels if p != 0.0)
                click.echo(f"Non-zero pixels: {non_zero}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command("eye-cancel")
@click.argument("device_path")
def eye_cancel(device_path: str) -> None:
    """Cancel an in-progress eye diagram capture."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.diagnostics.eye_cancel()
            click.echo("Eye diagram capture cancelled.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.pass_context
def ltssm(ctx: click.Context, device_path: str, port_id: int) -> None:
    """Dump LTSSM state log for a port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            entries = dev.diagnostics.ltssm_log(port_id)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps([e.model_dump() for e in entries], indent=2))
            else:
                for e in entries:
                    click.echo(
                        f"  [{e.timestamp:>10}] {e.link_state_str:<40} "
                        f"Rate={e.link_rate:.1f} Width={e.link_width}"
                    )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command("ltssm-clear")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
def ltssm_clear(device_path: str, port_id: int) -> None:
    """Clear LTSSM log for a port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.diagnostics.ltssm_clear(port_id)
            click.echo("LTSSM log cleared.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--enable/--disable", default=True, help="Enable or disable loopback.")
@click.option(
    "--ltssm-speed",
    type=click.Choice(list(_LTSSM_SPEED_MAP.keys()), case_sensitive=False),
    default="gen4",
    help="LTSSM speed for loopback.",
)
def loopback(device_path: str, port_id: int, enable: bool, ltssm_speed: str) -> None:
    """Configure loopback on a port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            from serialcables_switchtec.bindings.constants import DiagLtssmSpeed
            speed_val = DiagLtssmSpeed(_LTSSM_SPEED_MAP[ltssm_speed.lower()])
            dev.diagnostics.loopback_set(port_id, enable=enable, ltssm_speed=speed_val)
            action = "enabled" if enable else "disabled"
            click.echo(f"Loopback {action} on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option(
    "--pattern",
    type=click.Choice(_ALL_PATTERN_NAMES, case_sensitive=False),
    default="prbs31",
    help="Pattern type.",
)
@click.option(
    "--speed",
    type=click.Choice(list(_SPEED_MAP.keys()), case_sensitive=False),
    default="gen4",
    help="Link speed for pattern.",
)
@click.option(
    "--gen",
    type=click.Choice(list(_GEN_TO_PATTERN_MAP.keys()), case_sensitive=False),
    default="gen4",
    help="PCIe generation for pattern encoding (gen3, gen4, gen5, gen6).",
)
def patgen(device_path: str, port_id: int, pattern: str, speed: str, gen: str) -> None:
    """Set pattern generator on a port."""
    try:
        pat_map = _GEN_TO_PATTERN_MAP[gen.lower()]
        pat_key = pattern.lower()
        if pat_key not in pat_map:
            raise click.BadParameter(
                f"Pattern '{pattern}' is not valid for {gen}. "
                f"Valid patterns: {', '.join(sorted(pat_map.keys()))}",
                param_hint="'--pattern'",
            )
        with SwitchtecDevice.open(device_path) as dev:
            from serialcables_switchtec.bindings.constants import DiagPatternLinkRate
            pat_val = pat_map[pat_key]
            spd_val = DiagPatternLinkRate(_SPEED_MAP[speed.lower()])
            dev.diagnostics.pattern_gen_set(port_id, pattern=pat_val, link_speed=spd_val)
            click.echo(f"Pattern generator set: {pattern} at {speed} on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.argument("lane_id", type=click.IntRange(0, 143))
@click.pass_context
def patmon(ctx: click.Context, device_path: str, port_id: int, lane_id: int) -> None:
    """Get pattern monitor results."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            result = dev.diagnostics.pattern_mon_get(port_id, lane_id)
            if ctx.obj.get("json_output"):
                click.echo(result.model_dump_json(indent=2))
            else:
                click.echo(f"Port {port_id} Lane {lane_id}: "
                          f"pattern={result.pattern_type} errors={result.error_count}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# ─── Error Injection Subgroup ───────────────────────────────────────

@diag.group()
@click.pass_context
def inject(ctx: click.Context) -> None:
    """Error injection commands."""
    ctx.ensure_object(dict)


@inject.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--data", required=True, type=int, help="DLLP data to inject.")
def dllp(device_path: str, port_id: int, data: int) -> None:
    """Inject a raw DLLP on a port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_dllp(port_id, data)
            click.echo(f"DLLP injected on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@inject.command("dllp-crc")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--enable/--disable", default=True, help="Enable or disable DLLP CRC injection.")
@click.option("--rate", default=1, type=int, help="Injection rate (0-65535).")
def dllp_crc(device_path: str, port_id: int, enable: bool, rate: int) -> None:
    """Enable/disable DLLP CRC error injection."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_dllp_crc(port_id, enable, rate)
            action = "enabled" if enable else "disabled"
            click.echo(f"DLLP CRC injection {action} on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@inject.command("tlp-lcrc")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--enable/--disable", default=True, help="Enable or disable TLP LCRC injection.")
@click.option("--rate", default=1, type=int, help="Injection rate (0-255).")
def tlp_lcrc(device_path: str, port_id: int, enable: bool, rate: int) -> None:
    """Enable/disable TLP LCRC error injection."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_tlp_lcrc(port_id, enable, rate)
            action = "enabled" if enable else "disabled"
            click.echo(f"TLP LCRC injection {action} on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@inject.command("seq-num")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
def seq_num(device_path: str, port_id: int) -> None:
    """Inject a TLP sequence number error."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_tlp_seq_num(port_id)
            click.echo(f"Sequence number error injected on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@inject.command("ack-nack")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--seq-num", required=True, type=int, help="Sequence number.")
@click.option("--count", default=1, type=int, help="Number of errors to inject.")
def ack_nack(device_path: str, port_id: int, seq_num: int, count: int) -> None:
    """Inject ACK/NACK errors."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_ack_nack(port_id, seq_num, count)
            click.echo(f"ACK/NACK errors injected on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@inject.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
def cto(device_path: str, port_id: int) -> None:
    """Inject completion timeout."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.injector.inject_cto(port_id)
            click.echo(f"Completion timeout injected on port {port_id}.")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# ─── AER Event Generation ─────────────────────────────────────────


@diag.command("aer-gen")
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--error-id", required=True, type=click.IntRange(0, 0xFFFF), help="AER error type identifier.")
@click.option("--trigger", default=0, type=click.IntRange(0, 0xFFFF), help="Event trigger flag.")
@click.pass_context
def aer_gen(
    ctx: click.Context,
    device_path: str,
    port_id: int,
    error_id: int,
    trigger: int,
) -> None:
    """Generate an AER event on a port."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            dev.diagnostics.aer_event_gen(port_id, error_id, trigger)
            if ctx.obj.get("json_output"):
                click.echo(json.dumps({
                    "port_id": port_id,
                    "error_id": error_id,
                    "trigger": trigger,
                    "generated": True,
                }))
            else:
                click.echo(
                    f"AER event generated on port {port_id} "
                    f"(error_id={error_id}, trigger={trigger})."
                )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


# ─── Receiver / EQ / Cross-Hair ────────────────────────────────────

@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.argument("lane_id", type=click.IntRange(0, 143))
@click.option("--link", type=click.Choice(["current", "previous"]), default="current",
              help="Link to query.")
@click.pass_context
def rcvr(ctx: click.Context, device_path: str, port_id: int, lane_id: int, link: str) -> None:
    """Dump receiver calibration object."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            from serialcables_switchtec.bindings.constants import DiagLink
            link_enum = DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
            result = dev.diagnostics.rcvr_obj(port_id, lane_id, link=link_enum)
            if ctx.obj.get("json_output"):
                click.echo(result.model_dump_json(indent=2))
            else:
                click.echo(f"CTLE: {result.ctle}")
                click.echo(f"Target Amplitude: {result.target_amplitude}")
                click.echo(f"Speculative DFE: {result.speculative_dfe}")
                click.echo(f"Dynamic DFE: {result.dynamic_dfe}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.argument("port_id", type=click.IntRange(0, 59))
@click.option("--end", type=click.Choice(["local", "far_end"]), default="local",
              help="Which end to query.")
@click.option("--link", type=click.Choice(["current", "previous"]), default="current",
              help="Link to query.")
@click.pass_context
def eq(ctx: click.Context, device_path: str, port_id: int, end: str, link: str) -> None:
    """Dump port equalization TX coefficients."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            from serialcables_switchtec.bindings.constants import DiagEnd, DiagLink
            end_enum = DiagEnd.LOCAL if end == "local" else DiagEnd.FAR_END
            link_enum = DiagLink.CURRENT if link == "current" else DiagLink.PREVIOUS
            result = dev.diagnostics.port_eq_tx_coeff(port_id, end=end_enum, link=link_enum)
            if ctx.obj.get("json_output"):
                click.echo(result.model_dump_json(indent=2))
            else:
                click.echo(f"Lane count: {result.lane_count}")
                for i, c in enumerate(result.cursors):
                    click.echo(f"  Lane {i}: pre={c.pre} post={c.post}")
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()


@diag.command()
@click.argument("device_path")
@click.option("--lane", default=-1, type=int, help="Lane ID (-1 for all).")
@click.option("--action", type=click.Choice(["enable", "disable", "get"]),
              default="get", help="Cross-hair action.")
@click.pass_context
def crosshair(ctx: click.Context, device_path: str, lane: int, action: str) -> None:
    """Cross-hair measurement."""
    try:
        with SwitchtecDevice.open(device_path) as dev:
            if action == "enable":
                dev.diagnostics.cross_hair_enable(lane)
                click.echo(f"Cross-hair enabled on lane {lane}.")
            elif action == "disable":
                dev.diagnostics.cross_hair_disable()
                click.echo("Cross-hair disabled.")
            else:
                from serialcables_switchtec.bindings.constants import DIAG_CROSS_HAIR_MAX_LANES
                start = 0 if lane < 0 else lane
                num_lanes = DIAG_CROSS_HAIR_MAX_LANES if lane < 0 else 1
                results = dev.diagnostics.cross_hair_get(start, num_lanes)
                if ctx.obj.get("json_output"):
                    click.echo(json.dumps([r.model_dump() for r in results], indent=2))
                else:
                    for r in results:
                        click.echo(
                            f"  Lane {r.lane_id}: {r.state_name} "
                            f"L={r.eye_left_lim} R={r.eye_right_lim}"
                        )
    except SwitchtecError as e:
        click.echo(f"Error: {e}", err=True)
        raise click.Abort()
