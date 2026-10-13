"""Scrollable local task workflows; validation stays visible in the form."""

import asyncio
import sqlite3
from typing import ClassVar
from uuid import UUID

from textual.app import ComposeResult
from textual.binding import BindingType
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Markdown, Select, Static

from ..database.dependency_repository import TaskDependencyRepository
from ..database.exceptions import DependencyError, TaskNotFoundError
from ..database.models import CompletionStatus, Task, TaskCreate, TaskStatus, TaskUpdate
from ..database.planning import PlanningService
from ..database.repository import TaskRepository


class FormScreen(ModalScreen[object]):
    """Keep invalid input in place, with an actionable error and no partial UI success."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "dismiss", "Close")]

    def __init__(self) -> None:
        super().__init__()
        self._values: dict[str, str] = {}
        self._selections: dict[str, object] = {}
        self._saving = False
        self.dialog_title = "TaskWeaver"

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool:
        """Prevent leaving while an off-loop save is still committing."""
        return not (self._saving and action == "dismiss")

    def on_mount(self) -> None:
        """Title the dialog and start editing its first input."""
        self.query_one(".dialog").border_title = f"{self.dialog_title} · Esc to close"
        inputs = list(self.query(Input))
        if inputs:
            inputs[0].focus()

    def fields(self) -> ComposeResult:
        """Yield the inputs specific to this form."""
        raise NotImplementedError

    def compose(self) -> ComposeResult:
        """Keep fields scrollable and save errors visible above the buttons."""
        with Vertical(classes="dialog"):
            with VerticalScroll(classes="form-fields"):
                yield from self.fields()
            yield Static("", id="form-error", markup=False)
            with Horizontal(classes="dialog-buttons"):
                yield Button("Save", id="save", variant="primary")
                yield Button("Back", id="back")

    def save(self) -> object:
        """Validate and persist inputs, returning the saved result on success."""
        raise NotImplementedError

    def value(self, name: str) -> str:
        """Read a trimmed input value by its widget identifier."""
        return self._values[name]

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        """Capture input on-loop, persist off-loop, and keep failed drafts editable."""
        if self._saving:
            return
        if event.button.id == "back":
            self.dismiss()
        elif event.button.id == "save":
            self._values = {widget.id: widget.value.strip() for widget in self.query(Input) if widget.id}
            self._selections = {widget.id: widget.value for widget in self.query(Select) if widget.id}
            self._saving = True
            for button in self.query(Button):
                button.disabled = True
            try:
                result = await asyncio.to_thread(self.save)
            except (ValueError, TaskNotFoundError, DependencyError, sqlite3.Error, OSError) as error:
                self.query_one("#form-error", Static).update(f"Cannot save: {error}. Correct the fields and retry.")
            else:
                self.dismiss(result)
            finally:
                self._saving = False
                for button in self.query(Button):
                    button.disabled = False


class TaskFormScreen(FormScreen):
    """Create or edit; blank optional fields deliberately clear existing values."""

    def __init__(self, repo: TaskRepository, planning: PlanningService, task: Task | None = None) -> None:
        super().__init__()
        self.repo = repo
        self.planning = planning
        self.task_data = task

    def fields(self) -> ComposeResult:
        """Populate task fields, keeping optional clearing and score ranges explicit."""
        yield Label("Edit task" if self.task_data else "New task")
        yield Label("Blank description, goal, domain or level clears it on save.")
        defaults = {
            "title": "",
            "requirement": "",
            "description": "",
            "duration_min": "30",
            "llm_value": "50",
            "urgency": "3",
            "importance": "3",
            "effort": "3",
            "category": "general",
            "skill_domain": "",
            "required_skill_level": "",
        }
        labels = {
            "title": "Title",
            "requirement": "Done when",
            "description": "Description (optional)",
            "duration_min": "Working estimate (minutes)",
            "llm_value": "Value (0-100; CD3 numerator)",
            "urgency": "Urgency (1-5)",
            "importance": "Importance (1-5)",
            "effort": "Effort (1-5)",
            "category": "Category",
            "skill_domain": "Required skill domain (optional)",
            "required_skill_level": "Required skill level (1-5, optional)",
        }
        for name, default in defaults.items():
            value = getattr(self.task_data, name) if self.task_data else default
            yield Label(labels[name])
            yield Input(str(value) if value is not None else "", id=f"task-{name}")
        yield Label("Goal (optional)")
        yield Select([], prompt="Loading goals…", id="task-goal_id", disabled=True)

    async def on_mount(self) -> None:
        """Load goal choices without blocking rendering or input."""
        super().on_mount()
        goals = await asyncio.to_thread(self.planning.list_goals)
        selector = self.query_one("#task-goal_id", Select)
        selector.set_options([(goal.title, str(goal.goal_id)) for goal in goals])
        selector.prompt = "No goal"
        selector.value = str(self.task_data.goal_id) if self.task_data and self.task_data.goal_id else Select.BLANK
        selector.disabled = False

    def save(self) -> Task:
        """Validate all task fields and persist explicit optional-field clears."""
        data: dict[str, object] = {name: self.value(f"task-{name}") for name in ("title", "requirement", "category")}
        for name in ("description", "skill_domain"):
            data[name] = self.value(f"task-{name}") or None
        for name in ("duration_min", "urgency", "importance", "effort"):
            data[name] = int(self.value(f"task-{name}"))
        data["llm_value"] = float(self.value("task-llm_value"))
        level = self.value("task-required_skill_level")
        data["required_skill_level"] = int(level) if level else None
        goal = self._selections["task-goal_id"]
        data["goal_id"] = UUID(str(goal)) if goal is not Select.BLANK else None
        if self.task_data:
            return self.repo.update_task(self.task_data.task_id, TaskUpdate.model_validate(data))
        return self.repo.create_task(TaskCreate.model_validate(data))


class CompletionScreen(FormScreen):
    """Record actual effort and learning through the atomic completion service."""

    def __init__(self, planning: PlanningService, task: Task, *, cancelled: bool = False) -> None:
        super().__init__()
        self.planning = planning
        self.task_data = task
        self.status = CompletionStatus.CANCELLED if cancelled else CompletionStatus.COMPLETED
        self.dialog_title = "Cancel task" if cancelled else "Complete task"

    def fields(self) -> ComposeResult:
        """Collect actual effort and an optional learning conclusion."""
        action = "Cancel" if self.status == CompletionStatus.CANCELLED else "Complete"
        yield Label(f"{action}: {self.task_data.title}", markup=False)
        yield Label(
            "Actual minutes (positive integer; leave blank if unknown)"
            if self.status == CompletionStatus.CANCELLED
            else "Actual minutes spent (required, positive integer)"
        )
        yield Input(id="actual-minutes")
        yield Label("Conclusion / learning (optional)")
        yield Input(id="conclusion")

    def save(self) -> object:
        """Persist status, actual effort and learning through the completion service."""
        actual = self.value("actual-minutes")
        conclusion = self.value("conclusion") or None
        if not actual and self.status == CompletionStatus.CANCELLED:
            if conclusion:
                raise ValueError("A learning conclusion requires an actual duration")
            return TaskRepository(self.planning.db_path).update_task(
                self.task_data.task_id, TaskUpdate(status=TaskStatus.CANCELLED)
            )
        if not actual:
            raise ValueError("Enter the actual minutes spent before completing the task")
        return self.planning.complete_task(self.task_data.task_id, int(actual), conclusion, self.status)


class DependencyScreen(FormScreen):
    """Select a blocker and add/remove the edge; cycles are service errors."""

    def __init__(self, repo: TaskRepository, dependencies: TaskDependencyRepository, task: Task) -> None:
        super().__init__()
        self.repo = repo
        self.dependencies = dependencies
        self.task_data = task

    def fields(self) -> ComposeResult:
        """List eligible blockers and make the edge direction explicit."""
        yield Label(f"Dependencies for: {self.task_data.title}", markup=False)
        yield Static("Loading blockers…", id="current-blockers", markup=False)
        yield Label("Arrow direction: selected blocker → this task")
        yield Select([], id="dependency-blocker", prompt="Choose blocker", disabled=True)
        yield Select(
            [("Add edge", "add"), ("Remove edge", "remove")], value="add", allow_blank=False, id="dependency-operation"
        )

    async def on_mount(self) -> None:
        """Load dependency choices off-loop and focus the blocker selector."""
        self.query_one(".dialog").border_title = "TaskWeaver · Esc to close"
        blockers = await asyncio.to_thread(self.dependencies.get_blockers, self.task_data.task_id)
        tasks = await asyncio.to_thread(self.repo.list_tasks)
        self.query_one("#current-blockers", Static).update(
            "Current blockers: " + (", ".join(task.title for task in blockers) or "none")
        )
        selector = self.query_one("#dependency-blocker", Select)
        selector.set_options(
            [
                (f"{task.title} [{str(task.task_id)[:8]}]", str(task.task_id))
                for task in tasks
                if task.task_id != self.task_data.task_id
                and (
                    task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS)
                    or task.task_id in {blocker.task_id for blocker in blockers}
                )
            ]
        )
        selector.disabled = False
        selector.focus()

    def save(self) -> UUID:
        """Apply the selected edge operation through dependency validation."""
        selected = self._selections["dependency-blocker"]
        if selected is Select.BLANK:
            raise ValueError("Choose a blocker")
        blocker = UUID(str(selected))
        operation = self._selections["dependency-operation"]
        if operation == "add":
            self.dependencies.add_dependency(self.task_data.task_id, blocker)
        else:
            self.dependencies.remove_dependency(self.task_data.task_id, blocker)
        return self.task_data.task_id


class PlanningFormScreen(FormScreen):
    """Add a goal or append an evidence-backed skill assessment."""

    def __init__(self, planning: PlanningService, *, skill: bool = False) -> None:
        super().__init__()
        self.planning = planning
        self.skill = skill

    def fields(self) -> ComposeResult:
        """Collect goal metadata or a skill level with required evidence."""
        yield Label("Assess skill" if self.skill else "Create goal")
        yield Label("Domain" if self.skill else "Goal title")
        yield Input(id="planning-name")
        if self.skill:
            yield Label("Dreyfus level (1-5)")
            yield Input("1", id="planning-level")
        yield Label("Evidence (required)" if self.skill else "Description (optional)")
        yield Input(id="planning-evidence")

    def save(self) -> object:
        """Create a goal or append an evidence-backed skill assessment."""
        if self.skill:
            return self.planning.set_skill(
                self.value("planning-name"), int(self.value("planning-level")), self.value("planning-evidence")
            )
        return self.planning.create_goal(self.value("planning-name"), self.value("planning-evidence") or None)


class TaskDetailScreen(ModalScreen[None]):
    """Full UUID, requirements, separate scoring metrics and service-provided history."""

    BINDINGS: ClassVar[list[BindingType]] = [("escape", "dismiss", "Close")]

    def __init__(self, task: Task, details: str = "") -> None:
        super().__init__()
        self.task_data = task
        self.details = details or f"# {task.title}\n\n{task.task_id}\n\n{task.requirement}"

    def compose(self) -> ComposeResult:
        """Keep the complete task explanation scrollable within the modal."""
        with Vertical(classes="dialog"):
            with VerticalScroll(classes="form-fields"):
                yield Markdown(self.details, id="task-details")
            yield Button("Close", id="close-button")

    def on_mount(self) -> None:
        """Title the read-only explanation panel."""
        self.query_one(".dialog").border_title = "Task details · Esc to close"

    def on_button_pressed(self, _event: Button.Pressed) -> None:
        """Close the read-only detail view without modifying task state."""
        self.dismiss()
