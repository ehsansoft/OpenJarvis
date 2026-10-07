"""jarvis projects — discover and inspect local project workspaces."""

from __future__ import annotations

import json
import os
from pathlib import Path

import click

from openjarvis.core.config import load_config
from openjarvis.projects import discover_projects, load_registry, write_registry


def _default_root(configured_root: str) -> Path:
    if configured_root:
        return Path(configured_root).expanduser()
    if os.name == "nt":
        d_projects = Path("D:/Projects")
        if d_projects.exists():
            return d_projects
    return Path.cwd()


@click.group()
def projects() -> None:
    """Manage the local project fabric."""


@projects.command("scan")
@click.argument(\n    "root",\n    required=False,\n    type=click.Path(path_type=Path, file_okay=False),\n)
@click.option("--max-depth", type=click.IntRange(min=0), default=None)
@click.option(\n    "--registry",\n    "registry_path",\n    type=click.Path(path_type=Path, dir_okay=False),\n    default=None,\n)
@click.option("--json", "as_json", is_flag=True)
@click.option("--no-write", is_flag=True)
def scan_projects(
    root: Path | None,
    max_depth: int | None,
    registry_path: Path | None,
    as_json: bool,
    no_write: bool,
) -> None:
    """Discover project roots without ingesting project source code."""
    config = load_config()
    project_config = config.projects
    root_path = (root or _default_root(project_config.root)).expanduser().resolve()
    depth = project_config.max_depth if max_depth is None else max_depth
    records = discover_projects(root_path, max_depth=depth)

    if registry_path is None:
        registry_path = Path(project_config.registry_path).expanduser()
    if not no_write:
        write_registry(records, registry_path, root=root_path)

    payload = {
        "root": str(root_path),
        "count": len(records),
        "registry": "" if no_write else str(registry_path.resolve()),
        "projects": [record.to_dict() for record in records],
    }
    if as_json:
        click.echo(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    click.echo(f"Discovered {len(records)} project(s) under {root_path}")
    if not no_write:
        click.echo(f"Registry: {registry_path.resolve()}")
    for record in records:
        langs = ", ".join(record.languages) or "-"
        click.echo(\n            f"- {record.project_id}: {record.project_type} "
            f"[{langs}] -> {record.path}"\n        )


@projects.command("list")
@click.option("--registry", "registry_path", type=click.Path(path_type=Path, dir_okay=False), default=None)
@click.option("--json", "as_json", is_flag=True)
def list_projects(registry_path: Path | None, as_json: bool) -> None:
    """List projects from the last persisted scan."""
    config = load_config()
    if registry_path is None:
        registry_path = Path(config.projects.registry_path).expanduser()
    if not registry_path.exists():
        raise click.ClickException(
            f"Project registry not found: {registry_path}. Run 'jarvis projects scan'."
        )

    registry = load_registry(registry_path)
    if as_json:
        click.echo(json.dumps(registry, indent=2, ensure_ascii=False))
        return

    projects_data = registry["projects"]
    click.echo(f"{len(projects_data)} project(s) in {registry_path.resolve()}")
    for project in projects_data:
        click.echo(
            f"- {project.get('project_id', '?')}: "
            f"{project.get('project_type', 'generic')} -> {project.get('path', '')}"
        )


__all__ = ["projects"]
