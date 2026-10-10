"""TaskWeaver CLI: local task workflows with opt-in AI and integrations."""

import sys
from collections.abc import Sequence
from enum import Enum
from importlib.metadata import version
from typing import Annotated
from uuid import UUID

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table
from rich.text import Text

from .cli_integrations import github, memory
from .cli_planning import DB, app, command_errors, render_priority, resolve_db
from .config import get_config, get_paths
from .database.connection import init_database
from .database.dependency_repository import TaskDependencyRepository
from .database.models import Task, TaskCreate, TaskStatus, TaskUpdate, TaskWithDependencies
from .database.planning import PlanningService
from .database.priority_service import PriorityService
from .database.repository import TaskRepository

app.info.help = "TaskWeaver — local task planning with optional AI assistance"
app.add_typer(memory, name="memory")
app.add_typer(github, name="github")
console = Console()


class TaskSort(str, Enum):
    """Explicitly distinct intrinsic, inherited, and value/time orderings."""

    CREATED = "created"
    PRIORITY = "priority"
    SCORE = "score"
    CD3 = "cd3"


def _version(value: bool) -> None:
    if value:
        console.print(f"TaskWeaver {version('taskweaver')}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def root(
    ctx: typer.Context,
    db_path: DB = None,
    _show_version: Annotated[bool, typer.Option("--version", callback=_version, is_eager=True)] = False,
) -> None:
    """Root --db supplies the default for every command; command-local --db wins."""
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    ctx.obj = {"db": db_path}
    if ctx.invoked_subcommand is not None:
        return
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        console.print(ctx.get_help())
        return
    from .setup import check_configuration, run_first_time_setup  # noqa: PLC0415

    if not check_configuration() and not run_first_time_setup():
        raise typer.Exit(1)
    from .tui import run_tui  # noqa: PLC0415

    with command_errors():
        run_tui(resolve_db(ctx, None))


def _print_tasks(tasks: Sequence[Task], sort: TaskSort = TaskSort.SCORE) -> None:
    """Render compact summaries; detailed fields remain available via show."""
    if not tasks:
        console.print("[yellow]No tasks found[/yellow]")
        return
    show_dependencies = isinstance(tasks[0], TaskWithDependencies)
    table = Table(title="Tasks", show_lines=True, header_style="bold blue")
    table.add_column("Title", min_width=12, ratio=1, overflow="fold")
    table.add_column("Status", no_wrap=True)
    table.add_column("Estimate", justify="right", no_wrap=True)
    table.add_column("CD3" if sort == TaskSort.CD3 else "MCDA", justify="right", no_wrap=True)
    if show_dependencies:
        table.add_column("Blocks", justify="right", no_wrap=True)
        table.add_column("Blockers", justify="right", no_wrap=True)
    for task in tasks:
        score = (
            f"{task.priority:.3f}"
            if sort == TaskSort.CD3
            else (f"{task.priority_score:.1f}" if task.priority_score is not None else "—")
        )
        row: list[str | Text] = [Text(task.title), task.status.value, f"{task.duration_min}m", score]
        if isinstance(task, TaskWithDependencies):
            row.extend([str(task.tasks_blocked_count), str(task.active_blocker_count)])
        table.add_row(*row)
    console.print(table)
    console.print(f"\n[dim]Total: {len(tasks)} task(s)[/dim]")


@app.command(name="create")
def create(
    ctx: typer.Context,
    title: str,
    duration_min: Annotated[int, typer.Option("--duration", "-t", min=1)],
    llm_value: Annotated[float, typer.Option("--value", "-v", min=0, max=100)],
    requirement: Annotated[str, typer.Option("--req", "-r")],
    description: Annotated[str | None, typer.Option("--desc", "-d")] = None,
    urgency: Annotated[int, typer.Option(min=1, max=5)] = 3,
    importance: Annotated[int, typer.Option(min=1, max=5)] = 3,
    effort: Annotated[int, typer.Option(min=1, max=5)] = 3,
    category: str = "general",
    goal: UUID | None = None,
    domain: str | None = None,
    required_skill_level: Annotated[int | None, typer.Option(min=1, max=5)] = None,
    db_path: DB = None,
) -> None:
    """Create a task; durations are raw estimates before category adjustment."""
    with command_errors():
        task = TaskRepository(resolve_db(ctx, db_path)).create_task(
            TaskCreate(
                title=title,
                description=description,
                duration_min=duration_min,
                llm_value=llm_value,
                requirement=requirement,
                urgency=urgency,
                importance=importance,
                effort=effort,
                category=category,
                goal_id=goal,
                skill_domain=domain,
                required_skill_level=required_skill_level,
            )
        )
        console.print(f"Created task: {task.task_id} - {task.title}", markup=False)


@app.command(name="ls")
def list_tasks(
    ctx: typer.Context,
    status: Annotated[TaskStatus | None, typer.Option("--status", "-s")] = None,
    sort: TaskSort = TaskSort.CREATED,
    limit: Annotated[int | None, typer.Option(min=0)] = None,
    match_skills: bool = False,
    db_path: DB = None,
) -> None:
    """List tasks. priority=inherited MCDA, score=intrinsic MCDA, cd3=value/minute."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        repo = TaskRepository(path)
        service = PriorityService(path)
        if sort == TaskSort.SCORE:
            tasks = repo.list_tasks_by_priority(status)
        else:
            tasks = repo.list_tasks(status)
            if sort == TaskSort.PRIORITY:
                scores = service.calculate_effective_priorities(status)
                tasks.sort(key=lambda task: (-scores.get(task.task_id, 0), task.created_at, str(task.task_id)))
            elif sort == TaskSort.CD3:
                tasks.sort(key=lambda task: (-task.priority, task.created_at, str(task.task_id)))
        if match_skills:
            ready = {task.task_id for task in PlanningService(path).recommendations().ready}
            tasks = [task for task in tasks if task.task_id in ready]
        if limit is not None:
            tasks = tasks[:limit]
        _print_tasks(tasks, sort)


@app.command(name="lso")
def list_open(ctx: typer.Context, db_path: DB = None) -> None:
    """List compact open tasks with dependency counts."""
    with command_errors():
        _print_tasks(TaskRepository(resolve_db(ctx, db_path)).list_tasks_with_deps())


@app.command(name="edit")
def update(
    ctx: typer.Context,
    task_id: UUID,
    title: str | None = None,
    description: Annotated[str | None, typer.Option("--desc", "-d")] = None,
    status: Annotated[TaskStatus | None, typer.Option("--status", "-s")] = None,
    duration_min: Annotated[int | None, typer.Option("--duration", "-t", min=1)] = None,
    llm_value: Annotated[float | None, typer.Option("--value", "-v", min=0, max=100)] = None,
    requirement: Annotated[str | None, typer.Option("--req", "-r")] = None,
    urgency: Annotated[int | None, typer.Option(min=1, max=5)] = None,
    importance: Annotated[int | None, typer.Option(min=1, max=5)] = None,
    effort: Annotated[int | None, typer.Option(min=1, max=5)] = None,
    category: str | None = None,
    goal: UUID | None = None,
    domain: str | None = None,
    required_skill_level: Annotated[int | None, typer.Option(min=1, max=5)] = None,
    clear_description: bool = False,
    clear_goal: bool = False,
    clear_domain: bool = False,
    clear_required_skill_level: bool = False,
    db_path: DB = None,
) -> None:
    """Edit supplied fields only. Working duration edits preserve the raw baseline."""
    with command_errors():
        fields = {
            name: value
            for name, value in {
                "title": title,
                "description": description,
                "status": status,
                "duration_min": duration_min,
                "llm_value": llm_value,
                "requirement": requirement,
                "urgency": urgency,
                "importance": importance,
                "effort": effort,
                "category": category,
                "goal_id": goal,
                "skill_domain": domain,
                "required_skill_level": required_skill_level,
            }.items()
            if value is not None
        }
        for name, clear in (
            ("description", clear_description),
            ("goal_id", clear_goal),
            ("skill_domain", clear_domain),
            ("required_skill_level", clear_required_skill_level),
        ):
            if clear:
                if name in fields:
                    raise ValueError(f"Cannot set and clear {name} together")
                fields[name] = None
        if not fields:
            raise ValueError("Must specify at least one field to update")
        task = TaskRepository(resolve_db(ctx, db_path)).update_task(task_id, TaskUpdate.model_validate(fields))
        console.print(f"Updated task: {task.task_id} - {task.title}", markup=False)


@app.command(name="rm")
def delete(
    ctx: typer.Context, task_id: UUID, force: Annotated[bool, typer.Option("--force", "-f")] = False, db_path: DB = None
) -> None:
    """Delete a task; use --force to skip confirmation."""
    if not force and not typer.confirm(f"Delete task {task_id}?"):
        console.print("Cancelled")
        raise typer.Abort()
    with command_errors():
        TaskRepository(resolve_db(ctx, db_path)).delete_task(task_id)
        console.print(f"Deleted task: {task_id}")


@app.command(name="show")
def show(ctx: typer.Context, task_id: UUID, explain_priority: bool = False, db_path: DB = None) -> None:
    """Show all task fields, optionally exact priority components and history."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        task = TaskRepository(path).get_task(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        table = Table(show_header=False, title=f"Task: {task.task_id}", show_lines=True)
        table.add_column("Field", style="bold cyan")
        table.add_column("Value")
        for field, value in task.model_dump(mode="json").items():
            table.add_row(field.replace("_", " ").title(), Text(str(value)))
        table.add_row("CD3 (value/minute)", str(task.priority))
        console.print(table)
        if explain_priority:
            render_priority(PriorityService(path), task_id)


@app.command()
def chat(
    ctx: typer.Context,
    db_path: DB = None,
    langfuse: Annotated[bool, typer.Option("--o", help="Enable observability explicitly")] = False,
) -> None:
    """Start the shared interactive AI conversation."""
    from .agents.chat_handler import CliChatHandler  # noqa: PLC0415
    from .agents.orchestrator import run_chat  # noqa: PLC0415

    with command_errors():
        if langfuse:
            from .observability import start_langfuse  # noqa: PLC0415

            start_langfuse()
        run_chat(CliChatHandler(), resolve_db(ctx, db_path))


@app.command()
def tui(
    ctx: typer.Context,
    db_path: DB = None,
    langfuse: Annotated[bool, typer.Option("--o", help="Enable observability explicitly")] = False,
) -> None:
    """Launch the terminal UI, without requiring provider credentials."""
    from .tui import run_tui  # noqa: PLC0415

    with command_errors():
        if langfuse:
            from .observability import start_langfuse  # noqa: PLC0415

            start_langfuse()
        run_tui(resolve_db(ctx, db_path))


@app.command(name="restartDB")
def restart(
    ctx: typer.Context, db_path: DB = None, delete: Annotated[bool, typer.Option("--delete", "-d")] = False
) -> None:
    """Reinitialize schema, preserving data unless --delete is explicit."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        if delete and path.exists():
            console.print(f"Deleting existing database: {path}")
            path.unlink()
            console.print("Database deleted")
        init_database(path)
        console.print(f"Database initialized: {path}")


@app.command(name="createDep")
def create_dependency(ctx: typer.Context, task_id: UUID, blocker_id: UUID, db_path: DB = None) -> None:
    """Add a dependency; cycles and missing tasks are errors."""
    with command_errors():
        TaskDependencyRepository(resolve_db(ctx, db_path)).add_dependency(task_id, blocker_id)
        console.print(f"Dependency added: task {task_id} -> blocker {blocker_id}")


@app.command(name="rmdep")
def remove_dependency(ctx: typer.Context, task_id: UUID, blocker_id: UUID, db_path: DB = None) -> None:
    """Remove one dependency."""
    with command_errors():
        TaskDependencyRepository(resolve_db(ctx, db_path)).remove_dependency(task_id, blocker_id)
        console.print(f"Dependency removed: task {task_id} -> blocker {blocker_id}")


@app.command(name="blocker")
def blockers(ctx: typer.Context, task_id: UUID, db_path: DB = None) -> None:
    """Show a task's blockers."""
    with command_errors():
        path = resolve_db(ctx, db_path)
        if TaskRepository(path).get_task(task_id) is None:
            raise ValueError(f"Task not found: {task_id}")
        table = Table(title=f"Task: {task_id} blockers")
        table.add_column("Blocker ID")
        table.add_column("Blocker Title")
        for blocker in TaskDependencyRepository(path).get_blockers(task_id):
            table.add_row(str(blocker.task_id), Text(blocker.title))
        console.print(table)


@app.command(name="setup")
def setup_command() -> None:
    """Rerun the interactive wizard, preserving unrelated configuration."""
    from .setup import run_first_time_setup  # noqa: PLC0415

    if not run_first_time_setup(force=True):
        console.print("Setup requires an interactive terminal", style="red")
        raise typer.Exit(1)


@app.command(name="info")
def info_command(ctx: typer.Context) -> None:
    """Show resolved data locations, configuration, and local task counts."""
    with command_errors():
        paths = get_paths()
        config = get_config()
        path = resolve_db(ctx, None)
        for name, value in (
            ("Database", path),
            ("Config", paths.config_file),
            ("API keys", paths.env_file),
            ("Logs", paths.log_file),
            ("LLM model", config.llm_model),
            ("Semantic memory enabled", config.memory_enabled),
            ("User", config.user_id),
        ):
            console.print(f"{name}: {value}", markup=False)
        if path.exists():
            tasks = TaskRepository(path).list_tasks()
            console.print(f"Total: {len(tasks)}")
            for status in TaskStatus:
                console.print(f"{status.value}: {sum(task.status == status for task in tasks)}")


def main() -> None:
    """Packaged CLI entry point."""
    app()


if __name__ == "__main__":
    main()
