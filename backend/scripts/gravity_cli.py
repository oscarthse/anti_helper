"""
Gravity CLI - Command Line Interface

A beautiful CLI for interacting with the Antigravity Dev platform.
"""

import asyncio

import httpx
import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

app = typer.Typer(
    name="gravity",
    help="Antigravity Dev - AI-powered development platform",
    add_completion=False,
)
console = Console()

# API base URL
API_URL = "http://localhost:8000"


# =============================================================================
# Repository Commands
# =============================================================================

repo_app = typer.Typer(help="Manage repositories")
app.add_typer(repo_app, name="repo")


@repo_app.command("add")
def add_repo(
    path: str = typer.Argument(..., help="Path to the repository"),
    name: str | None = typer.Option(None, "--name", "-n", help="Display name"),
) -> None:
    """Register a repository for agent access."""

    from pathlib import Path

    repo_path = Path(path).resolve()
    if not repo_path.exists():
        rprint(f"[red]Error:[/red] Path does not exist: {repo_path}")
        raise typer.Exit(1)

    display_name = name or repo_path.name

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Registering repository...", total=None)

        response = httpx.post(
            f"{API_URL}/api/repos/",
            json={"name": display_name, "path": str(repo_path)},
            timeout=30,
        )

    if response.status_code == 201:
        data = response.json()
        rprint(Panel(
            f"[green]✓ Repository registered[/green]\n\n"
            f"ID: {data['id']}\n"
            f"Name: {data['name']}\n"
            f"Path: {data['path']}",
            title="Success",
        ))
    elif response.status_code == 409:
        rprint("[yellow]Repository already registered[/yellow]")
    else:
        rprint(f"[red]Error:[/red] {response.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)


@repo_app.command("list")
def list_repos() -> None:
    """List all registered repositories."""

    response = httpx.get(f"{API_URL}/api/repos/", timeout=10)

    if response.status_code != 200:
        rprint("[red]Error:[/red] Failed to fetch repositories")
        raise typer.Exit(1)

    repos = response.json()

    if not repos:
        rprint("[dim]No repositories registered. Use 'gravity repo add <path>' to add one.[/dim]")
        return

    table = Table(title="Registered Repositories")
    table.add_column("ID", style="dim")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Framework")
    table.add_column("Path")

    for repo in repos:
        table.add_row(
            repo["id"][:8] + "...",
            repo["name"],
            repo.get("project_type") or "-",
            repo.get("framework") or "-",
            repo["path"][:50] + "..." if len(repo["path"]) > 50 else repo["path"],
        )

    console.print(table)


@repo_app.command("scan")
def scan_repo(
    repo_id: str = typer.Argument(..., help="Repository ID"),
) -> None:
    """Scan a repository to detect project type and framework."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Scanning repository...", total=None)

        response = httpx.post(
            f"{API_URL}/api/repos/{repo_id}/scan",
            timeout=60,
        )

    if response.status_code == 200:
        data = response.json()
        rprint(Panel(
            f"[green]✓ Scan complete[/green]\n\n"
            f"Project Type: {data.get('project_type') or 'Unknown'}\n"
            f"Framework: {data.get('framework') or 'None detected'}\n"
            f"Files: {data.get('file_count', 0)}\n"
            f"Directories: {data.get('directory_count', 0)}",
            title="Repository Scan",
        ))
    else:
        rprint(f"[red]Error:[/red] {response.json().get('detail', 'Unknown error')}")
        raise typer.Exit(1)


# =============================================================================
# Task Commands
# =============================================================================

task_app = typer.Typer(help="Manage tasks")
app.add_typer(task_app, name="task")


@task_app.command("run")
def run_task(
    repo_id: str = typer.Argument(..., help="Repository ID"),
    request: str = typer.Argument(..., help="What you want the AI to do"),
) -> None:
    """Submit a task for AI execution."""

    rprint("\n[bold]Creating task...[/bold]")
    rprint(f"Repository: {repo_id[:8]}...")
    rprint(f"Request: {request[:100]}{'...' if len(request) > 100 else ''}\n")

    # Create task
    response = httpx.post(
        f"{API_URL}/api/tasks/",
        json={"repo_id": repo_id, "user_request": request},
        timeout=30,
    )

    if response.status_code != 201:
        rprint(f"[red]Error:[/red] {response.json().get('detail', 'Failed to create task')}")
        raise typer.Exit(1)

    task = response.json()
    task_id = task["id"]

    rprint(f"[green]✓ Task created:[/green] {task_id[:8]}...\n")

    # Execute task
    exec_response = httpx.post(
        f"{API_URL}/api/tasks/{task_id}/execute",
        timeout=10,
    )

    if exec_response.status_code != 200:
        rprint("[yellow]Warning:[/yellow] Could not trigger execution")

    # Stream progress
    rprint("[bold]Streaming progress...[/bold]\n")

    try:
        _stream_task_progress(task_id)
    except KeyboardInterrupt:
        rprint("\n[yellow]Interrupted. Task continues in background.[/yellow]")


def _stream_task_progress(task_id: str) -> None:
    """Stream and display task progress."""

    import sseclient

    try:
        response = httpx.get(
            f"{API_URL}/api/stream/task/{task_id}",
            timeout=None,
        )

        client = sseclient.SSEClient(response)

        for event in client.events():
            import json
            data = json.loads(event.data)

            if event.event == "status":
                status = data["status"]
                agent = data.get("current_agent", "")
                rprint(f"[dim]Status:[/dim] {status} {f'({agent})' if agent else ''}")

            elif event.event == "agent_log":
                rprint(Panel(
                    f"[bold]{data['ui_title']}[/bold]\n\n{data['ui_subtitle']}",
                    title=f"🤖 {data['agent_persona'].upper()}"
                ))

            elif event.event == "complete":
                if data["status"] == "completed":
                    rprint("\n[green bold]✓ Task completed successfully![/green bold]")
                else:
                    rprint("\n[red bold]✗ Task failed[/red bold]")
                break

            elif event.event == "error":
                rprint(f"\n[red]Error:[/red] {data.get('message')}")
                break

    except ImportError:
        # SSE client not available, poll instead
        rprint("[dim]Note: Install sseclient for real-time streaming[/dim]")
        rprint("[dim]Polling for updates...[/dim]\n")

        while True:
            response = httpx.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)
            task = response.json()

            rprint(f"Status: {task['status']}")

            if task["status"] in ["completed", "failed"]:
                break

            asyncio.run(asyncio.sleep(2))


@task_app.command("list")
def list_tasks(
    repo_id: str | None = typer.Option(None, "--repo", "-r", help="Filter by repository"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of tasks to show"),
) -> None:
    """List recent tasks."""

    params = {"limit": limit}
    if repo_id:
        params["repo_id"] = repo_id

    response = httpx.get(f"{API_URL}/api/tasks/", params=params, timeout=10)

    if response.status_code != 200:
        rprint("[red]Error:[/red] Failed to fetch tasks")
        raise typer.Exit(1)

    tasks = response.json()

    if not tasks:
        rprint("[dim]No tasks found.[/dim]")
        return

    table = Table(title="Recent Tasks")
    table.add_column("ID", style="dim")
    table.add_column("Status", style="cyan")
    table.add_column("Request")
    table.add_column("Created")

    for task in tasks:
        status_color = {
            "completed": "green",
            "failed": "red",
            "executing": "yellow",
        }.get(task["status"], "white")

        table.add_row(
            task["id"][:8] + "...",
            f"[{status_color}]{task['status']}[/{status_color}]",
            task["user_request"][:40] + "..." if len(task["user_request"]) > 40 else task["user_request"],
            task["created_at"][:16],
        )

    console.print(table)


@task_app.command("status")
def task_status(
    task_id: str = typer.Argument(..., help="Task ID"),
) -> None:
    """Get detailed status of a task."""

    response = httpx.get(f"{API_URL}/api/tasks/{task_id}", timeout=10)

    if response.status_code == 404:
        rprint("[red]Error:[/red] Task not found")
        raise typer.Exit(1)

    if response.status_code != 200:
        rprint("[red]Error:[/red] Failed to fetch task")
        raise typer.Exit(1)

    task = response.json()

    # Task info
    status_color = {
        "completed": "green",
        "failed": "red",
        "executing": "yellow",
        "planning": "blue",
    }.get(task["status"], "white")

    rprint(Panel(
        f"[bold]Status:[/bold] [{status_color}]{task['status']}[/{status_color}]\n"
        f"[bold]Current Agent:[/bold] {task.get('current_agent') or 'None'}\n"
        f"[bold]Step:[/bold] {task['current_step']}\n\n"
        f"[bold]Request:[/bold]\n{task['user_request'][:500]}",
        title=f"Task: {task['id'][:8]}...",
    ))

    # Agent logs
    if task.get("agent_logs"):
        rprint("\n[bold]Agent Activity:[/bold]\n")
        for log in task["agent_logs"]:
            rprint(f"  [{log['agent_persona']}] {log['ui_title']}")
            rprint(f"    [dim]{log['ui_subtitle'][:80]}...[/dim]\n")


# =============================================================================
# Database Commands (Alembic)
# =============================================================================

db_app = typer.Typer(help="Database migration commands")
app.add_typer(db_app, name="db")


@db_app.command("upgrade")
def db_upgrade(
    revision: str = typer.Argument("head", help="Revision to upgrade to (default: head)"),
) -> None:
    """Apply database migrations."""
    import subprocess

    rprint(f"[bold]Upgrading database to: {revision}[/bold]\n")

    result = subprocess.run(
        ["alembic", "upgrade", revision],
        capture_output=True,
        text=True,
        cwd=str(__file__).replace("/scripts/gravity_cli.py", "").replace("/backend", ""),
    )

    if result.returncode == 0:
        rprint("[green]✓ Database upgraded successfully[/green]")
        if result.stdout:
            rprint(f"\n[dim]{result.stdout}[/dim]")
    else:
        rprint(f"[red]Error:[/red] {result.stderr}")
        raise typer.Exit(1)


@db_app.command("downgrade")
def db_downgrade(
    revision: str = typer.Argument(..., help="Revision to downgrade to (e.g., -1, head~1)"),
) -> None:
    """Revert database migrations."""
    import subprocess

    rprint(f"[bold]Downgrading database to: {revision}[/bold]\n")

    result = subprocess.run(
        ["alembic", "downgrade", revision],
        capture_output=True,
        text=True,
        cwd=str(__file__).replace("/scripts/gravity_cli.py", "").replace("/backend", ""),
    )

    if result.returncode == 0:
        rprint("[green]✓ Database downgraded successfully[/green]")
    else:
        rprint(f"[red]Error:[/red] {result.stderr}")
        raise typer.Exit(1)


@db_app.command("revision")
def db_revision(
    message: str = typer.Option(..., "--message", "-m", help="Revision message"),
    autogenerate: bool = typer.Option(True, "--autogenerate/--no-autogenerate", help="Auto-detect changes"),
) -> None:
    """Create a new migration revision."""
    import subprocess

    rprint(f"[bold]Creating new revision: {message}[/bold]\n")

    cmd = ["alembic", "revision", "-m", message]
    if autogenerate:
        cmd.append("--autogenerate")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(__file__).replace("/scripts/gravity_cli.py", "").replace("/backend", ""),
    )

    if result.returncode == 0:
        rprint("[green]✓ Revision created successfully[/green]")
        if result.stdout:
            rprint(f"\n[dim]{result.stdout}[/dim]")
    else:
        rprint(f"[red]Error:[/red] {result.stderr}")
        raise typer.Exit(1)


@db_app.command("current")
def db_current() -> None:
    """Show current revision."""
    import subprocess

    result = subprocess.run(
        ["alembic", "current"],
        capture_output=True,
        text=True,
        cwd=str(__file__).replace("/scripts/gravity_cli.py", "").replace("/backend", ""),
    )

    if result.returncode == 0:
        rprint("[bold]Current revision:[/bold]")
        rprint(result.stdout or "[dim]No migrations applied[/dim]")
    else:
        rprint(f"[red]Error:[/red] {result.stderr}")


@db_app.command("history")
def db_history() -> None:
    """Show migration history."""
    import subprocess

    result = subprocess.run(
        ["alembic", "history"],
        capture_output=True,
        text=True,
        cwd=str(__file__).replace("/scripts/gravity_cli.py", "").replace("/backend", ""),
    )

    if result.returncode == 0:
        rprint("[bold]Migration history:[/bold]")
        rprint(result.stdout or "[dim]No migrations[/dim]")
    else:
        rprint(f"[red]Error:[/red] {result.stderr}")


# =============================================================================
# Main Entry
# =============================================================================

@app.callback()
def main() -> None:
    """
    🚀 Antigravity Dev - AI-powered development platform

    A repo-aware, sandboxed, multi-agent AI development platform
    that plans, edits, and tests changes across complex applications.
    """
    pass


if __name__ == "__main__":
    app()
