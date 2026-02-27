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
def serve(host: str, port: int) -> None:
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

    app = create_app()
    uvicorn.run(app, host=host, port=port)


# Register sub-command groups
from serialcables_switchtec.cli.device import device  # noqa: E402
from serialcables_switchtec.cli.diag import diag  # noqa: E402
from serialcables_switchtec.cli.events import events_group  # noqa: E402
from serialcables_switchtec.cli.fabric import fabric_group  # noqa: E402
from serialcables_switchtec.cli.firmware import fw_group  # noqa: E402

cli.add_command(device)
cli.add_command(diag)
cli.add_command(events_group)
cli.add_command(fabric_group)
cli.add_command(fw_group)


if __name__ == "__main__":
    cli()
