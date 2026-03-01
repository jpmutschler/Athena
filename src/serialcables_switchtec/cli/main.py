"""Root CLI group and serve command."""

from __future__ import annotations

import click

from serialcables_switchtec.utils.logging import setup_logging


@click.group()
@click.version_option(package_name="serialcables-switchtec")
@click.option("--debug", is_flag=True, help="Enable debug logging.")
@click.option("--json-output", is_flag=True, help="Output logs as JSON.")
@click.pass_context
def cli(ctx: click.Context, debug: bool, json_output: bool) -> None:
    """Athena -- Serial Cables Gen6 PCIe Switchtec Host Card Management Interface."""
    ctx.ensure_object(dict)
    level = "DEBUG" if debug else "INFO"
    setup_logging(level=level, json_output=json_output)
    ctx.obj["debug"] = debug
    ctx.obj["json_output"] = json_output


@cli.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="API server host. Use 0.0.0.0 for network access.")
@click.option("--port", default=8000, type=int, help="API server port.")
@click.option(
    "--cors-origins",
    default=None,
    help=(
        "Comma-separated CORS origins. "
        "Use '*' to allow all origins (lab networks). "
        "Defaults to http://localhost:<port> and http://127.0.0.1:<port>. "
        "Can also be set via ATHENA_CORS_ORIGINS env var."
    ),
)
def serve(host: str, port: int, cors_origins: str | None) -> None:
    """Start the API server and NiceGUI dashboard."""
    try:
        import uvicorn

        from serialcables_switchtec.api.app import create_app
    except ImportError:
        click.echo(
            "API dependencies not installed. "
            "Install with: pip install serialcables-switchtec[all]",
            err=True,
        )
        raise click.Abort()

    origins: list[str] | None = None
    if cors_origins is not None:
        origins = [o.strip() for o in cors_origins.split(",") if o.strip()]
    else:
        # Auto-generate origins from the configured host/port so that
        # remote access works out of the box when --host 0.0.0.0 is used.
        origins = [
            f"http://localhost:{port}",
            f"http://127.0.0.1:{port}",
        ]

    app = create_app(cors_origins=origins)
    uvicorn.run(app, host=host, port=port)


# Register sub-command groups
from serialcables_switchtec.cli.device import device  # noqa: E402
from serialcables_switchtec.cli.diag import diag  # noqa: E402
from serialcables_switchtec.cli.evcntr import evcntr_group  # noqa: E402
from serialcables_switchtec.cli.events import events_group  # noqa: E402
from serialcables_switchtec.cli.fabric import fabric_group  # noqa: E402
from serialcables_switchtec.cli.firmware import fw_group  # noqa: E402
from serialcables_switchtec.cli.mrpc import mrpc_group  # noqa: E402
from serialcables_switchtec.cli.osa import osa_group  # noqa: E402
from serialcables_switchtec.cli.perf import perf_group  # noqa: E402
from serialcables_switchtec.cli.recipe import recipe  # noqa: E402

cli.add_command(device)
cli.add_command(diag)
cli.add_command(evcntr_group)
cli.add_command(events_group)
cli.add_command(fabric_group)
cli.add_command(fw_group)
cli.add_command(mrpc_group)
cli.add_command(osa_group)
cli.add_command(perf_group)
cli.add_command(recipe)


if __name__ == "__main__":
    cli()
