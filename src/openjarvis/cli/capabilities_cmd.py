"""Read-only workstation capability catalog."""

import json

import click

from openjarvis.core.capability_catalog import build_catalog
from openjarvis.core.config import JarvisConfig, get_config_path, load_config
from openjarvis.core.paths import get_config_dir


@click.command("capabilities")
@click.option(
    "--json", "as_json", is_flag=True, help="Emit the versioned readiness contract."
)
@click.option(
    "--timeout",
    type=click.FloatRange(min=0.1, max=10),
    default=3.0,
    show_default=True,
    help="Maximum HTTP request timeout in seconds.",
)
def capabilities(as_json: bool, timeout: float) -> None:
    """Show what is ready, missing, disabled or awaiting acceptance; change nothing."""
    # load_config historically mkdirs the state root. Do not create a new root
    # merely for a status command when configuration has never been initialized.
    root = get_config_dir()
    config = (
        load_config()
        if root.is_dir() and get_config_path().is_file()
        else JarvisConfig()
    )
    report = build_catalog(config, root, timeout=timeout)
    if as_json:
        click.echo(json.dumps(report, indent=2, ensure_ascii=False))
        return
    click.echo("OPENJARVIS WORKSTATION CAPABILITIES")
    click.echo(f"Observed: {report['observed_at']} (read-only)")
    for record in report["capabilities"]:
        click.echo(f"\n{record['display_name']:<25} {record['status']}")
        click.echo(f"  {record['reason']}")
        if record["status"] != "READY":
            click.echo(f"  Next: {record['next_action']}")
