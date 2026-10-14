"""``jarvis team`` — named roster and durable task board (T1/T2).

Roster commands manage who exists and what they do. Board commands manage
work: create, promote, claim, review, approve. Dispatch is explicit — no
command here polls, spawns workers or bypasses the state machine.
"""

from __future__ import annotations

from typing import Optional

import click
from rich.console import Console
from rich.table import Table

console = Console(stderr=True)


def _get_roster():
    """Build a RosterStore from config paths."""
    from openjarvis.core.config import DEFAULT_CONFIG_DIR, load_config
    from openjarvis.team.roster import RosterStore

    config = load_config()
    db_path = getattr(getattr(config, "team", None), "roster_db_path", None) or str(
        DEFAULT_CONFIG_DIR / "team.db"
    )
    return RosterStore(db_path)


def _get_board():
    """Build a BoardStore sharing the roster DB file."""
    from openjarvis.core.config import DEFAULT_CONFIG_DIR, load_config
    from openjarvis.team.board import BoardStore

    config = load_config()
    db_path = getattr(getattr(config, "team", None), "roster_db_path", None) or str(
        DEFAULT_CONFIG_DIR / "team.db"
    )
    return BoardStore(db_path)


@click.group()
def team() -> None:
    """Named agent roster and collaborative task board."""


# -- Roster -------------------------------------------------------------------


@team.group("roster")
def roster() -> None:
    """Manage the named-agent roster."""


@roster.command("add")
@click.argument("name")
@click.option("--role", default="", help="Role description for routing.")
@click.option(
    "--model",
    "model_alias",
    default="local/fast",
    help="Explicit model route (local/* or free/*).",
)
@click.option("--tool-policy", default="", help="Tool policy profile name.")
@click.option(
    "--privacy",
    default="private",
    type=click.Choice(["private", "public", "mixed"]),
    help="Privacy label for this agent.",
)
def roster_add(
    name: str, role: str, model_alias: str, tool_policy: str, privacy: str
) -> None:
    """Register a named agent on the roster."""
    store = _get_roster()
    try:
        entry = store.add(
            name,
            role,
            model_alias,
            tool_policy=tool_policy,
            privacy_label=privacy,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(
        f"[green]Registered[/green] {entry['name']} ->"
        f" {entry['model_alias']} ({entry['privacy_label']})"
    )


@roster.command("list")
@click.option(
    "--status",
    default=None,
    type=click.Choice(["active", "paused", "archived"]),
    help="Filter by status.",
)
def roster_list(status: Optional[str]) -> None:
    """List roster entries."""
    store = _get_roster()
    try:
        entries = store.list(status=status)
    finally:
        store.close()
    if not entries:
        console.print("[dim]Roster is empty. Add with: jarvis team roster add[/dim]")
        return
    table = Table(title="Agent roster")
    table.add_column("Name", style="cyan")
    table.add_column("Role")
    table.add_column("Model", style="green")
    table.add_column("Privacy", style="yellow")
    table.add_column("Status")
    for e in entries:
        table.add_row(
            e["name"],
            e["role_description"],
            e["model_alias"],
            e["privacy_label"],
            e["status"],
        )
    console.print(table)


@roster.command("set")
@click.argument("name")
@click.option("--role", default=None, help="New role description.")
@click.option("--model", "model_alias", default=None, help="New model route.")
@click.option(
    "--status",
    default=None,
    type=click.Choice(["active", "paused", "archived"]),
)
@click.option(
    "--privacy", default=None, type=click.Choice(["private", "public", "mixed"])
)
def roster_set(
    name: str,
    role: Optional[str],
    model_alias: Optional[str],
    status: Optional[str],
    privacy: Optional[str],
) -> None:
    """Update roster entry fields."""
    store = _get_roster()
    try:
        entry = store.update(
            name,
            role_description=role,
            model_alias=model_alias,
            status=status,
            privacy_label=privacy,
        )
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(
        f"[green]Updated[/green] {entry['name']} -> {entry['model_alias']}"
        f" ({entry['status']}, {entry['privacy_label']})"
    )


@roster.command("routing")
def roster_routing() -> None:
    """Print the active roster as a routing prompt block."""
    store = _get_roster()
    try:
        click.echo(store.describe_routing())
    finally:
        store.close()


# -- Board --------------------------------------------------------------------


@team.group("board")
def board() -> None:
    """Manage the collaborative task board."""


@board.command("create")
@click.argument("title")
@click.option("--body", default="", help="Task details.")
@click.option("--assignee", default="", help="Roster name of the owner.")
@click.option("--depends-on", default="", help="Comma-separated dependency task IDs.")
@click.option("--created-by", default="", help="Author (roster name or operator).")
def board_create(
    title: str, body: str, assignee: str, depends_on: str, created_by: str
) -> None:
    """Create a task in triage."""
    deps = [d.strip() for d in depends_on.split(",") if d.strip()]
    store = _get_board()
    try:
        task = store.create(
            title, body, assignee=assignee, depends_on=deps, created_by=created_by
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(f"[green]Created[/green] {task['id']} [{task['state']}] {title}")


@board.command("list")
@click.option(
    "--state",
    default=None,
    type=click.Choice(
        sorted({"triage", "ready", "running", "blocked", "review", "done", "archived"})
    ),
)
def board_list(state: Optional[str]) -> None:
    """List board tasks."""
    store = _get_board()
    try:
        tasks = store.list(state=state)
    finally:
        store.close()
    if not tasks:
        console.print("[dim]Board is empty.[/dim]")
        return
    table = Table(title="Task board")
    table.add_column("ID", style="cyan")
    table.add_column("State")
    table.add_column("Title")
    table.add_column("Assignee", style="green")
    table.add_column("Claim", style="dim")
    for t in tasks:
        table.add_row(
            t["id"],
            t["state"],
            t["title"],
            t["assignee"],
            t["claim_owner"],
        )
    console.print(table)


@board.command("ready")
@click.argument("task_id")
@click.option("--actor", default="", help="Roster name or operator.")
def board_ready(task_id: str, actor: str) -> None:
    """Promote a task to ready (fails if dependencies are unfinished)."""
    store = _get_board()
    try:
        task = store.ready(task_id, actor=actor)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(f"[green]{task['id']} is {task['state']}[/green]")


@board.command("claim")
@click.argument("task_id")
@click.option("--owner", required=True, help="Roster name claiming the work.")
def board_claim(task_id: str, owner: str) -> None:
    """Atomically claim a ready task."""
    store = _get_board()
    try:
        task = store.claim(task_id, owner=owner)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    if task is None:
        console.print("[red]Claim failed: not ready, taken, or dependencies open[/red]")
        raise SystemExit(1)
    console.print(f"[green]{task['id']} claimed by {owner}[/green]")


@board.command("block")
@click.argument("task_id")
@click.option("--reason", default="", help="Why the task is blocked.")
@click.option("--actor", default="")
def board_block(task_id: str, reason: str, actor: str) -> None:
    """Block a task with an explanatory comment."""
    store = _get_board()
    try:
        task = store.block(task_id, reason=reason, actor=actor)
    except KeyError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(f"[yellow]{task['id']} blocked[/yellow]")


@board.command("review")
@click.argument("task_id")
@click.option("--owner", required=True, help="Current claimant.")
@click.option("--summary", default="", help="What was done.")
def board_review(task_id: str, owner: str, summary: str) -> None:
    """Submit claimed work for review."""
    store = _get_board()
    try:
        task = store.request_review(task_id, owner=owner, summary=summary)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(f"[yellow]{task['id']} is in review[/yellow]")


@board.command("approve")
@click.argument("task_id")
@click.option("--reviewer", required=True, help="One reviewer decision.")
@click.option("--note", default="")
def board_approve(task_id: str, reviewer: str, note: str) -> None:
    """Approve reviewed work; the only path to done."""
    store = _get_board()
    try:
        task = store.approve(task_id, reviewer=reviewer, note=note)
    except (KeyError, ValueError) as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc
    finally:
        store.close()
    console.print(f"[green]{task['id']} approved by {reviewer}[/green]")


@board.command("show")
@click.argument("task_id")
def board_show(task_id: str) -> None:
    """Show a task with dependencies and comments."""
    store = _get_board()
    try:
        task = store.get(task_id)
    finally:
        store.close()
    if task is None:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise SystemExit(1)
    console.print(f"[bold]{task['id']}[/bold] [{task['state']}] {task['title']}")
    if task["body"]:
        console.print(task["body"])
    console.print(
        f"assignee={task['assignee'] or '-'} claim={task['claim_owner'] or '-'}"
        f" depends_on={', '.join(task['depends_on']) or '-'}"
    )
    for c in task["comments"]:
        console.print(f"  [dim]{c['author']}:[/dim] {c['body']}")


__all__ = ["team"]
