import json

import click


@click.command("model-lab")
@click.option(
    "--models", default="local/fast", help="Comma-separated installed local aliases."
)
def model_lab(models):
    """Run bounded synthetic checks against installed local models."""
    from openjarvis.core.model_lab import run_evaluations
    from openjarvis.system import SystemBuilder

    with SystemBuilder().scheduler(False).build() as system:
        click.echo(
            json.dumps(run_evaluations(system.engine, models.split(",")), indent=2)
        )
