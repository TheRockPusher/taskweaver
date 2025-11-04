"""CLI commands for TaskWeaver."""

from datetime import datetime
from pathlib import Path
from typing import Annotated
from uuid import UUID

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

from .agents.chat_handler import CliChatHandler
from .agents.task_agent import run_chat
from .config import get_config, get_paths
from .database.connection import init_database
from .database.dependency_repository import TaskDependencyRepository
from .database.models import Task, TaskCreate, TaskStatus, TaskUpdate, TaskWithDependencies
from .database.repository import TaskRepository
from .setup import run_first_time_setup
from .tui import run_tui

app = typer.Typer(
    help="🧵 TaskWeaver - AI-powered task organizer with intelligent decomposition",
    add_completion=True,
    rich_markup_mode="rich",
)
console = Console()
DEFAULT_DB = get_paths().database_file


@app.command(name="create", help="Create a new task")
def create(
    title: Annotated[str, typer.Argument(help="Task title")],
    duration_min: Annotated[int, typer.Option("--duration", "-t", help="Duration in minutes")],
    llm_value: Annotated[float, typer.Option("--value", "-v", help="LLM value score (0-100)")],
    requirement: Annotated[str, typer.Option("--req", "-r", help="Task requirement/conclusion")],
    description: Annotated[str | None, typer.Option("--desc", "-d", help="Task description")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Create a new task with title and required fields."""
    task_create = TaskCreate(
        title=title,
        description=description,
        duration_min=duration_min,
        llm_value=llm_value,
        requirement=requirement,
    )
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
    table = Table(title="📋 Tasks", show_lines=True)
    for col in columns:
        table.add_column(col, header_style="bold blue")

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


@app.command(name="lso", help="List all open tasks")
def list_open(
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """List open tasks with dependency counts."""
    columns = list(TaskWithDependencies.model_fields.keys())
    table = Table(title="📋 Tasks", show_lines=True)
    for col in columns:
        table.add_column(col, header_style="bold blue")

    task_list: list[TaskWithDependencies] = TaskRepository(db_path).list_tasks_with_deps()

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
    title: Annotated[str | None, typer.Option("--title", help="New task title")] = None,
    description: Annotated[str | None, typer.Option("--desc", "-d", help="New task description")] = None,
    status: Annotated[
        TaskStatus | None,
        typer.Option("--status", "-s", help="New status (pending/in_progress/completed/cancelled)"),
    ] = None,
    duration_min: Annotated[int | None, typer.Option("--duration", "-t", help="Duration in minutes")] = None,
    llm_value: Annotated[float | None, typer.Option("--value", "-v", help="LLM value score (0-100)")] = None,
    requirement: Annotated[str | None, typer.Option("--req", "-r", help="Task requirement/conclusion")] = None,
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Update task fields. Specify at least one field to update."""
    if not any([title, description, status, duration_min, llm_value, requirement]):
        console.print("[red]Error: Must specify at least one field to update[/red]")
        raise typer.Exit(code=1)

    task_update = TaskUpdate(
        title=title,
        description=description,
        status=status,
        duration_min=duration_min,
        llm_value=llm_value,
        requirement=requirement,
    )
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

    # Create a vertical table with field names and values
    table = Table(show_header=False, title=f"📋 Task: {task.task_id}", show_lines=True)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")

    for field in Task.model_fields:
        value = getattr(task, field)
        # Format None values
        display_value = "[dim]None[/dim]" if value is None else str(value)
        table.add_row(field.replace("_", " ").title(), display_value)

    console.print(table)


@app.command(name="chat", help="Start interactive conversation with AI agent.")
def chat(db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB) -> None:
    """Start an interactive conversation with the AI agent."""
    run_chat(CliChatHandler(), db_path)


@app.command(name="tui", help="Launch Terminal User Interface")
def tui(db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB) -> None:
    """Launch the Textual TUI interface."""
    run_tui(db_path)


@app.command(name="restartDB", help="Reinitialize database schema (optionally delete existing data).")
def restart(
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
    delete: Annotated[
        bool, typer.Option("--delete", "-d", help="Delete existing database before reinitializing")
    ] = False,
) -> None:
    """Reinitialize database schema.

    By default, reinitializes schema without deleting existing data.
    Use --delete to remove the database file first (all data will be lost).
    """
    if delete and db_path.exists():
        console.print(f"[yellow]Deleting existing database: {db_path}[/yellow]")
        db_path.unlink()
        console.print("[green]Database deleted[/green]")

    init_database(db_path=db_path)
    console.print(f"[green]✅ Database initialized: {db_path}[/green]")


@app.command(name="createDep", help="Creates a dependency between two tasks")
def create_dependency(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID")],
    blocker_id: Annotated[UUID, typer.Argument(help="Blocker UUID")],
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Creates a dependency between two tasks."""
    TaskDependencyRepository(db_path).add_dependency(task_id, blocker_id)
    console.print(f"Dependency added:\n[cyan]task:[/cyan]{task_id} -> [red]blocker:{blocker_id}[/red]")


@app.command(name="rmdep", help="Remove a dependency")
def remove_dependency(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID")],
    blocker_id: Annotated[UUID, typer.Argument(help="Blocker UUID")],
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """Removes a dependency between two tasks."""
    TaskDependencyRepository(db_path).remove_dependency(task_id, blocker_id)
    console.print(f"Dependency removed:\n[cyan]task:[/cyan]{task_id} -> [red]blocker:{blocker_id}[/red]")


@app.command(name="blocker", help="List all of the blockers of a task.")
def blockers(
    task_id: Annotated[UUID, typer.Argument(help="Task UUID")],
    db_path: Annotated[Path, typer.Option("--db", help="Database file path")] = DEFAULT_DB,
) -> None:
    """List all of the blockers of a task."""
    blockers: list[Task] = TaskDependencyRepository(db_path).get_blockers(task_id)
    table = Table(show_header=True, title=f"📋 Task: {task_id} blockers", show_lines=True)
    table.add_column("Blockers ID", style="bold cyan")
    table.add_column("Blocker Title", style="bold cyan")
    for blocker in blockers:
        table.add_row(str(blocker.task_id), blocker.title)
    console.print(table)


@app.command(name="setup", help="Run first-time setup wizard")
def setup_command() -> None:
    """Run interactive first-time setup wizard to configure API keys."""
    run_first_time_setup()


@app.command(name="info", help="Show configuration and data locations")
def info_command() -> None:
    """Display TaskWeaver configuration, data locations, and statistics."""
    paths = get_paths()
    config = get_config()

    console.print("\n[bold cyan]📊 TaskWeaver Information[/bold cyan]\n")

    # Data Locations
    console.print("[yellow]Data Locations:[/yellow]")
    console.print(f"  Database:  {paths.database_file}")
    console.print(f"  Qdrant:    {paths.qdrant_dir}")
    console.print(f"  Config:    {paths.config_file}")
    console.print(f"  API Keys:  {paths.env_file}")
    console.print(f"  Logs:      {paths.log_file}")

    # File Status
    console.print("\n[yellow]Status:[/yellow]")
    db_exists = paths.database_file.exists()
    qdrant_exists = paths.qdrant_dir.exists()
    config_exists = paths.config_file.exists()
    env_exists = paths.env_file.exists()

    console.print(f"  Database:  {'✅ exists' if db_exists else '❌ not found'}")
    console.print(f"  Qdrant:    {'✅ exists' if qdrant_exists else '❌ not found'}")
    console.print(f"  Config:    {'✅ exists' if config_exists else '❌ not found'}")
    console.print(f"  API Keys:  {'✅ exists' if env_exists else '❌ not found (run: taskweaver setup)'}")

    # Configuration
    console.print("\n[yellow]Configuration:[/yellow]")
    console.print(f"  LLM Model:       {config.llm_model}")
    console.print(f"  Memory Provider: {config.mem0_llm_provider}")
    console.print(f"  Memory Limit:    {config.mem0_max_memories}")
    if config.github_repos:
        console.print(f"  GitHub Repos:    {', '.join(config.github_repos)}")

    # Task Statistics
    if db_exists:
        try:
            repo = TaskRepository(paths.database_file)
            all_tasks = repo.list_tasks()
            pending = [t for t in all_tasks if t.status == TaskStatus.PENDING]
            in_progress = [t for t in all_tasks if t.status == TaskStatus.IN_PROGRESS]
            completed = [t for t in all_tasks if t.status == TaskStatus.COMPLETED]
            cancelled = [t for t in all_tasks if t.status == TaskStatus.CANCELLED]

            console.print("\n[yellow]Task Statistics:[/yellow]")
            console.print(f"  Total:       {len(all_tasks)}")
            console.print(f"  Pending:     {len(pending)}")
            console.print(f"  In Progress: {len(in_progress)}")
            console.print(f"  Completed:   {len(completed)}")
            console.print(f"  Cancelled:   {len(cancelled)}")

            # Database size
            db_size = paths.database_file.stat().st_size
            size_str = f"{db_size / 1024:.1f} KB" if db_size < 1024 * 1024 else f"{db_size / (1024 * 1024):.1f} MB"
            console.print(f"\n[dim]Database size: {size_str}[/dim]")
        except (OSError, ValueError) as e:
            logger.warning(f"Failed to read task statistics: {e}")

    console.print()


def main() -> None:
    """Main entry point for CLI."""
    logger.debug("TaskWeaver CLI starting")
    app()


if __name__ == "__main__":
    main()
