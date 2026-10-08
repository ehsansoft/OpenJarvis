"""jarvis projects — discover, inventory, and organize local workspaces."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import click

from openjarvis.core.config import load_config
from openjarvis.core.paths import get_config_dir
from openjarvis.projects import (
    discover_projects,
    load_registry,
    scan_cleanup_candidates,
    scan_drive_inventory,
    scan_duplicate_files,
    scan_machine_inventory,
    write_cleanup_report,
    write_duplicate_report,
    write_inventory,
    write_machine_inventory,
    write_registry,
)

_SCAN_TASK_NAME = "OpenJarvis Drive Inventory"


def _default_root(configured_root: str) -> Path:
    if configured_root:
        return Path(configured_root).expanduser()
    if os.name == "nt":
        d_projects = Path("D:/Projects")
        if d_projects.exists():
            return d_projects
    return Path.cwd()


def _default_inventory_root(configured_root: str) -> Path:
    if configured_root:
        return Path(configured_root).expanduser()
    if os.name == "nt":
        d_drive = Path("D:/")
        if d_drive.exists():
            return d_drive
    return Path.cwd()


def _powershell_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _scan_script_path() -> Path:
    return get_config_dir() / "scripts" / "drive-inventory.ps1"


def _write_windows_scan_script(
    *,
    root: Path,
    projects_root: Path,
    output: Path,
    max_files: int,
) -> Path:
    script = _scan_script_path()
    script.parent.mkdir(parents=True, exist_ok=True)

    scripts_dir = Path(sys.executable).resolve().parent
    jarvis_exe = scripts_dir / ("jarvis.exe" if os.name == "nt" else "jarvis")
    command = _powershell_quote(str(jarvis_exe))
    root_q = _powershell_quote(str(root))
    projects_q = _powershell_quote(str(projects_root))
    output_q = _powershell_quote(str(output))
    lines = [
        "$ErrorActionPreference = 'Stop'",
        f"& {command} projects scan {projects_q} --max-depth 5",
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        f"& {command} projects machine-scan",
        "if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }",
        f"& {command} projects inventory {root_q} "
        f"--output {output_q} --max-files {max_files}",
        "exit $LASTEXITCODE",
        "",
    ]
    script.write_text("\n".join(lines), encoding="utf-8")
    return script


@click.group()
def projects() -> None:
    """Manage the local project and drive knowledge fabric."""


@projects.command("scan")
@click.argument(
    "root",
    required=False,
    type=click.Path(path_type=Path, file_okay=False),
)
@click.option("--max-depth", type=click.IntRange(min=0), default=None)
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
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
        click.echo(
            f"- {record.project_id}: {record.project_type} "
            f"[{langs}] -> {record.path}"
        )


@projects.command("list")
@click.option(
    "--registry",
    "registry_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
@click.option("--json", "as_json", is_flag=True)
def list_projects(registry_path: Path | None, as_json: bool) -> None:
    """List projects from the last persisted scan."""
    config = load_config()
    if registry_path is None:
        registry_path = Path(config.projects.registry_path).expanduser()
    if not registry_path.exists():
        raise click.ClickException(
            f"Project registry not found: {registry_path}. "
            "Run 'jarvis projects scan'."
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
            f"{project.get('project_type', 'generic')} -> "
            f"{project.get('path', '')}"
        )


@projects.command("inventory")
@click.argument(
    "root",
    required=False,
    type=click.Path(path_type=Path, file_okay=False),
)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
@click.option(
    "--max-files",
    type=click.IntRange(min=1),
    default=None,
    help="Stop after this many files and mark the inventory truncated.",
)
@click.option("--json", "as_json", is_flag=True)
def inventory(
    root: Path | None,
    output_path: Path | None,
    max_files: int | None,
    as_json: bool,
) -> None:
    """Scan a whole drive/root using metadata only; never read file contents."""
    config = load_config()
    project_config = config.projects
    root_path = (
        root or _default_inventory_root(project_config.inventory_root)
    ).expanduser().resolve()
    if output_path is None:
        output_path = Path(project_config.inventory_path).expanduser()
    limit = (
        project_config.inventory_max_files
        if max_files is None
        else max_files
    )

    result = scan_drive_inventory(root_path, max_files=limit)
    write_inventory(result, output_path)

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    gib = result.bytes_seen / (1024**3)
    click.echo(
        f"Inventory complete: {result.files_seen:,} files, "
        f"{result.directories_seen:,} directories, {gib:.2f} GiB observed."
    )
    click.echo(f"Projects detected: {len(result.project_roots)}")
    click.echo(f"Output: {output_path.resolve()}")
    if result.truncated:
        click.echo("WARNING: scan hit max-files and is incomplete.")
    if result.recommendations:
        click.echo("\nOrganization recommendations:")
        for item in result.recommendations:
            click.echo(
                f"- [{item['priority']}] {item['title']}: "
                f"{item['recommendation']}"
            )


@projects.command("machine-scan")
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
@click.option("--json", "as_json", is_flag=True)
def machine_scan(output_path: Path | None, as_json: bool) -> None:
    """Detect Ollama models, WampServer runtimes, and developer tool versions."""
    config = load_config()
    project_config = config.projects
    if output_path is None:
        output_path = Path(project_config.machine_inventory_path).expanduser()

    host = config.engine.ollama.host or os.environ.get("OLLAMA_HOST", "")
    result = scan_machine_inventory(host)
    write_machine_inventory(result, output_path)

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    click.echo(f"Machine inventory: {output_path.resolve()}")
    click.echo(f"Tools detected: {len(result.tools)}")
    ollama = result.ollama
    click.echo(
        "Ollama: "
        + (
            f"{ollama.get('model_count', 0)} model(s)"
            if ollama.get("reachable")
            else "not reachable"
        )
    )
    wamp = result.wampserver
    click.echo(
        f"WampServer: {'detected' if wamp.get('detected') else 'not detected'}"
    )
    for item in result.recommendations:
        click.echo(f"- [{item['priority']}] {item['title']}")


@projects.command("cleanup-scan")
@click.argument(
    "root",
    required=False,
    type=click.Path(path_type=Path, file_okay=False),
)
@click.option("--min-age-days", type=click.IntRange(min=0), default=None)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
@click.option("--json", "as_json", is_flag=True)
def cleanup_scan(
    root: Path | None,
    min_age_days: int | None,
    output_path: Path | None,
    as_json: bool,
) -> None:
    """Find stale rebuildable folders without deleting anything."""
    config = load_config()
    project_config = config.projects
    root_path = (
        root or _default_inventory_root(project_config.inventory_root)
    ).expanduser().resolve()
    age = (
        project_config.cleanup_min_age_days
        if min_age_days is None
        else min_age_days
    )
    if output_path is None:
        output_path = Path(project_config.cleanup_report_path).expanduser()

    result = scan_cleanup_candidates(root_path, min_age_days=age)
    write_cleanup_report(result, output_path)

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    gib = result.estimated_bytes / (1024**3)
    click.echo(
        f"Cleanup candidates: {result.candidate_count} "
        f"(up to {gib:.2f} GiB observed)"
    )
    click.echo(f"Report: {output_path.resolve()}")
    for item in result.candidates[:25]:
        click.echo(
            f"- [{item['risk']}] {item['kind']} "
            f"{item['bytes'] / (1024**2):.1f} MiB -> {item['path']}"
        )


@projects.command("duplicates")
@click.argument(
    "root",
    required=False,
    type=click.Path(path_type=Path, file_okay=False),
)
@click.option("--min-size-mb", type=click.IntRange(min=1), default=None)
@click.option("--max-files", type=click.IntRange(min=1), default=750_000)
@click.option(
    "--output",
    "output_path",
    type=click.Path(path_type=Path, dir_okay=False),
    default=None,
)
@click.option("--json", "as_json", is_flag=True)
def duplicates(
    root: Path | None,
    min_size_mb: int | None,
    max_files: int,
    output_path: Path | None,
    as_json: bool,
) -> None:
    """Verify exact duplicate files with hashes; never delete them."""
    config = load_config()
    project_config = config.projects
    root_path = (
        root or _default_inventory_root(project_config.inventory_root)
    ).expanduser().resolve()
    min_mb = (
        project_config.duplicate_min_size_mb
        if min_size_mb is None
        else min_size_mb
    )
    if output_path is None:
        output_path = Path(project_config.duplicate_report_path).expanduser()

    result = scan_duplicate_files(
        root_path,
        min_size_bytes=min_mb * 1024 * 1024,
        max_files=max_files,
    )
    write_duplicate_report(result, output_path)

    if as_json:
        click.echo(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    gib = result.reclaimable_bytes / (1024**3)
    click.echo(
        f"Exact duplicate groups: {len(result.duplicate_groups)} "
        f"(potential reclaim {gib:.2f} GiB)"
    )
    click.echo(f"Report: {output_path.resolve()}")
    if result.truncated:
        click.echo("WARNING: duplicate scan hit max-files and is incomplete.")
    for group in result.duplicate_groups[:20]:
        click.echo(
            f"- {group['size'] / (1024**2):.1f} MiB x "
            f"{len(group['files'])}: {group['files'][0]}"
        )


@projects.command("install-scan-task")
@click.option(
    "--root",
    type=click.Path(path_type=Path, file_okay=False),
    default=None,
)
@click.option(
    "--daily-at",
    default="03:00",
    show_default=True,
    help="Local 24-hour HH:MM time for the metadata inventory.",
)
@click.option(
    "--max-files",
    type=click.IntRange(min=1),
    default=None,
)
def install_scan_task(
    root: Path | None,
    daily_at: str,
    max_files: int | None,
) -> None:
    """Install/update a daily Windows Task Scheduler inventory job."""
    if os.name != "nt":
        raise click.ClickException(
            "install-scan-task currently supports native Windows only."
        )

    config = load_config()
    project_config = config.projects
    root_path = (
        root or _default_inventory_root(project_config.inventory_root)
    ).expanduser().resolve()
    output = Path(project_config.inventory_path).expanduser().resolve()
    projects_root = _default_root(project_config.root).expanduser().resolve()
    limit = (
        project_config.inventory_max_files
        if max_files is None
        else max_files
    )

    try:
        hour, minute = daily_at.split(":", 1)
        hour_i = int(hour)
        minute_i = int(minute)
        if not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
            raise ValueError
    except ValueError as exc:
        raise click.BadParameter(
            "Use 24-hour HH:MM, for example 03:00.",
            param_hint="--daily-at",
        ) from exc

    script = _write_windows_scan_script(
        root=root_path,
        projects_root=projects_root,
        output=output,
        max_files=limit,
    )
    task_cmd = (
        f'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "{script}"'
    )
    cmd = [
        "schtasks.exe",
        "/Create",
        "/F",
        "/TN",
        _SCAN_TASK_NAME,
        "/SC",
        "DAILY",
        "/ST",
        f"{hour_i:02d}:{minute_i:02d}",
        "/TR",
        task_cmd,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or result.stdout.strip() or "schtasks failed"
        )

    click.echo(f"Installed Windows task: {_SCAN_TASK_NAME}")
    click.echo(f"Daily at: {hour_i:02d}:{minute_i:02d}")
    click.echo(f"Project root: {projects_root}")
    click.echo(f"Inventory root: {root_path}")
    click.echo(f"Inventory: {output}")
    click.echo(f"Script: {script}")


@projects.command("scan-task-status")
def scan_task_status() -> None:
    """Show the Windows scheduled inventory task status."""
    if os.name != "nt":
        raise click.ClickException(
            "scan-task-status currently supports native Windows only."
        )
    result = subprocess.run(
        ["schtasks.exe", "/Query", "/TN", _SCAN_TASK_NAME, "/FO", "LIST", "/V"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or "Scheduled inventory task is not installed."
        )
    click.echo(result.stdout.strip())


@projects.command("remove-scan-task")
def remove_scan_task() -> None:
    """Remove the Windows scheduled inventory task."""
    if os.name != "nt":
        raise click.ClickException(
            "remove-scan-task currently supports native Windows only."
        )
    result = subprocess.run(
        ["schtasks.exe", "/Delete", "/F", "/TN", _SCAN_TASK_NAME],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            result.stderr.strip() or "Could not remove scheduled inventory task."
        )
    click.echo(f"Removed Windows task: {_SCAN_TASK_NAME}")


__all__ = ["projects"]
