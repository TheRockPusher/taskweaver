"""CLI commands for TaskWeaver."""

from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from .database.models import Task, TaskCreate, TaskStatus, TaskUpdate
from .database.repository import TaskRepository

app = typer.Typer(
    help="🧵 TaskWeaver - AI-powered task organizer with intelligent decomposition",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
DEFAULT_DB = Path.home() / ".taskweaver" / "tasks.db"


@app.command(name="create", help="Create a new task")
def create(
    title: Annotated[str, typer.Argument(help="Task title")],
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Task description")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Create a new task with title and optional description."""
    task_create = TaskCreate(title=title, description=description)
    task = TaskRepository(db_path).create_task(task_create)
    console.print(f"✅ Created task: [cyan]{task.task_id}[/cyan] - [bold]{task.title}[/bold]")


@app.command(name="ls", help="List all tasks or filter by status")
def list_tasks(
    status: Annotated[
        TaskStatus | None,
        typer.Option("--status", "-s", help="Filter by status (pending/in_progress/completed/cancelled)"),
    ] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """List tasks with optional status filter. Use -s to filter by status."""
    columns = list(Task.model_fields.keys())
    table = Table(*columns, title="📋 Tasks", show_lines=True)

    task_list = TaskRepository(db_path).list_tasks(status=status)

    if not task_list:
        console.print("[yellow]No tasks found[/yellow]")
        return

    for task in task_list:
        row_values = []
        for field in columns:
            value = getattr(task, field)
            # Format datetime fields as yyyy-mm-dd
            if field in ("created_at", "updated_at") and isinstance(value, datetime):
                row_values.append(value.strftime("%Y-%m-%d"))
            else:
                row_values.append(str(value))
        table.add_row(*row_values)

    console.print(table)
    console.print(f"\n[dim]Total: {len(task_list)} task(s)[/dim]")


@app.command(name="edit", help="Update an existing task")
def update(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID to update")],
    title: Annotated[str | None, typer.Option("--title", "-t", help="New task title")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="New task description")] = None,
    status: Annotated[
        TaskStatus | None,
        typer.Option("--status", "-s", help="New status (pending/in_progress/completed/cancelled)"),
    ] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Update task fields. Specify at least one field to update."""
    if not any([title, description, status]):
        console.print("[red]Error: Must specify at least one field to update[/red]")
        raise typer.Exit(code=1)

    task_update = TaskUpdate(title=title, description=description, status=status)
    task = TaskRepository(db_path).update_task(task_id, task_update)
    console.print(f"✅ Updated task: [cyan]{task.task_id}[/cyan] - [bold]{task.title}[/bold]")


@app.command(name="rm", help="Delete a task")
def delete(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID to delete")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation prompt")] = False,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Delete a task by UUID. Use -f to skip confirmation."""
    if not force:
        confirm = typer.confirm(f"Delete task {task_id}?")
        if not confirm:
            console.print("[yellow]Cancelled[/yellow]")
            raise typer.Abort()

    TaskRepository(db_path).delete_task(task_id=task_id)
    console.print(f"🗑️  Deleted task: [cyan]{task_id}[/cyan]")


@app.command(name="show", help="Show detailed information about a task")
def show(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID to display")],
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Display detailed information for a specific task."""
    task = TaskRepository(db_path).get_task(task_id)

    if task is None:
        console.print(f"[red]Task not found: {task_id}[/red]")
        raise typer.Exit(code=1)

    console.print("\n[bold cyan]Task Details[/bold cyan]\n")
    console.print(f"[bold]ID:[/bold]          {task.task_id}")
    console.print(f"[bold]Title:[/bold]       {task.title}")
    console.print(f"[bold]Description:[/bold] {task.description or '[dim]None[/dim]'}")
    console.print(f"[bold]Status:[/bold]      {task.status}")
    console.print(f"[bold]Created:[/bold]     {task.created_at}")
    console.print(f"[bold]Updated:[/bold]     {task.updated_at}\n")


def main() -> None:
    """Main entry point for CLI."""
    logger.debug("TaskWeaver CLI starting")
    app()


if __name__ == "__main__":
    main()
