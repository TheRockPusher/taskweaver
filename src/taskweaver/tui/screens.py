"""Modal screens for TaskWeaver TUI.

This module provides modal dialog screens for displaying detailed information
about tasks in a focused, non-intrusive manner.
"""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static

from ..database.models import TaskWithPriority


class TaskDetailScreen(ModalScreen):
    """Modal screen displaying full task details.

    This screen shows complete task information without truncation, including:
    - Core fields (title, status, duration, values, priorities)
    - Dependency metrics (blockers, tasks blocked)
    - Multi-line fields (requirement, description)

    The modal dims the background and can be dismissed with Escape key or
    the Close button.

    Args:
        task: Task with priority information to display.

    Bindings:
        escape: Dismiss the modal

    Example:
        >>> task = TaskWithPriority(...)
        >>> app.push_screen(TaskDetailScreen(task))
    """

    DEFAULT_CSS = """
    TaskDetailScreen {
        align: center middle;
    }

    #detail-dialog {
        background: $surface;
        border: thick $primary;
        width: 80;
        height: auto;
        max-height: 90%;
        padding: 1 2;
    }

    .detail-field {
        margin: 1 0;
    }

    .field-label {
        color: $text-muted;
        text-style: bold;
    }

    .field-value {
        margin: 0 2;
    }

    #close-button {
        margin-top: 1;
    }
    """

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [("escape", "dismiss", "Close")]

    task_data: TaskWithPriority

    def __init__(self, task: TaskWithPriority) -> None:
        """Initialize modal with task data.

        Args:
            task: Task to display in modal.
        """
        super().__init__()
        self.task_data = task

    def compose(self) -> ComposeResult:
        """Build modal content.

        Yields:
            Container with task details and close button.
        """
        with Vertical(id="detail-dialog"):
            yield Static(f"[bold]{self.task_data.title}[/bold]", classes="detail-field")

            # Core fields
            yield Static("[b]Status:[/b]", classes="field-label")
            yield Static(self.task_data.status, classes="field-value")

            yield Static("[b]Duration:[/b]", classes="field-label")
            yield Static(f"{self.task_data.duration_min} minutes", classes="field-value")

            yield Static("[b]LLM Value:[/b]", classes="field-label")
            yield Static(f"{self.task_data.llm_value:.1f}", classes="field-value")

            yield Static("[b]Priority (Intrinsic):[/b]", classes="field-label")
            yield Static(f"{self.task_data.priority:.3f}", classes="field-value")

            yield Static("[b]Effective Priority:[/b]", classes="field-label")
            yield Static(f"{self.task_data.effective_priority:.3f}", classes="field-value")

            yield Static("[b]Active Blockers:[/b]", classes="field-label")
            yield Static(str(self.task_data.active_blocker_count), classes="field-value")

            yield Static("[b]Tasks Blocked:[/b]", classes="field-label")
            yield Static(str(self.task_data.tasks_blocked_count), classes="field-value")

            # Requirement (multi-line)
            yield Static("\n[b]Requirement:[/b]", classes="field-label")
            yield Static(self.task_data.requirement, classes="field-value")

            # Description (optional, multi-line)
            if self.task_data.description:
                yield Static("\n[b]Description:[/b]", classes="field-label")
                yield Static(self.task_data.description, classes="field-value")

            # Close button
            with Horizontal():
                yield Button("Close", id="close-button", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: Button press event.
        """
        if event.button.id == "close-button":
            self.dismiss()
