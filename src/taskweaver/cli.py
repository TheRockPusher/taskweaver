"""CLI commands for TaskWeaver."""

from uuid import UUID

import typer
from loguru import logger
from rich import print  # noqa: A004
from rich.console import Console
from rich.table import Table
from pathlib import Path


from .database.models import TaskCreate, TaskStatus, TaskUpdate, Task
from .database.repository import TaskRepository

app = typer.Typer(help="🧵 TaskWeaver - AI-powered task management")
console = Console()
DEFAULT_DB = Path.home() / ".taskweaver" / "tasks.db"

@app.command()
def create(title: str, description: str | None = None) -> None:
    task_create = TaskCreate(title=title, description=description)
    task: Task = TaskRepository().create_task(task_create)
    print(f"Task {task} Created")


@app.command()
def update(uuid: UUID, title: str | None = None, description: str | None = None, status: TaskStatus | None = None) -> None:
    task_update = TaskUpdate(title=title, description=description, status=status)
    task = TaskRepository().update_task(uuid,task_update)
    print(f"Task {task} Updated")


@app.command()
def list_task(status: TaskStatus | None = None) -> None:
    # Get field names from Task model
    columns = list(Task.model_fields.keys())

    # Create table with all Task fields as columns
    table = Table(*columns, title="Tasks")

    task_list: list[Task] = TaskRepository().list_tasks(status=status)

    # Add rows with values in field order
    for task in task_list:
        row_values = [str(getattr(task, field)) for field in columns]
        table.add_row(*row_values)

    console.print(table)

@app.command()
def delete_task(uuid: UUID) -> None:
    TaskRepository().delete_task(task_id=uuid)
    print(f"Task with {uuid} deleted")





def main() -> None:
    """Main entry point."""
    logger.debug("App starting")
    app()


if __name__ == "__main__":
    main()
