"""Credential-free local workspace with optional shared conversational assistance."""

import asyncio
import sqlite3
from dataclasses import dataclass
from datetime import UTC
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from github import GithubException
from loguru import logger
from rich.text import Text
from textual import events, on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Grid, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Input, Markdown, Static, TabbedContent, TabPane, TextArea
from textual.worker import get_current_worker

from ..agents.chat_handler import TuiChatHandler
from ..agents.github_sync import GitHubSyncError, run_github_sync
from ..agents.orchestrator import run_chat_async
from ..config import get_config, get_paths
from ..database.completion_repository import CompletionRepository
from ..database.dependency_repository import TaskDependencyRepository
from ..database.exceptions import DependencyError, TaskNotFoundError
from ..database.models import Task, TaskStatus, TaskUpdate
from ..database.planning import PlanningService, SkillMatch, WorkAnalysis
from ..database.priority_service import PriorityService
from ..database.repository import TaskRepository
from .constants import MAX_CHAT_MESSAGES, REFRESH_INTERVAL_SECONDS, VIEW_IDS
from .screens import CompletionScreen, DependencyScreen, PlanningFormScreen, TaskDetailScreen, TaskFormScreen

_UI_ERRORS = (ValueError, TaskNotFoundError, DependencyError, sqlite3.Error, OSError)
_HIGH_PRIORITY = 70
_MEDIUM_PRIORITY = 40
_COMPACT_BOARD_WIDTH = 100


@dataclass
class Workspace:
    """Database work collected off-loop; widgets consume only this result."""

    tasks: list[Task]
    effective: dict[UUID, float]
    cd3: dict[UUID, float]
    matches: dict[UUID, SkillMatch]
    ready: set[UUID]
    graph: str
    insights: tuple[str, ...]


class WorkspaceViews(TabbedContent):
    """Only explicit tab selection changes views, never stale descendant focus."""

    def _on_tab_pane_focused(self, event: TabPane.Focused) -> None:
        # Focus messages can arrive after a pane was hidden by a newer tab change.
        event.prevent_default()
        event.stop()


class WorkspaceTable(DataTable):
    """Use the actual widget viewport, not the previous virtual table width."""

    def on_resize(self) -> None:
        """Resize after this widget receives its final layout dimensions."""
        self.call_after_refresh(self.fit_title)

    def fit_title(self) -> None:
        """Expand the first column while retaining stable rows and the cursor."""
        columns = self.ordered_columns
        if not columns or not self.content_size.width:
            return
        width = max(
            1,
            self.content_size.width
            - (self.scrollbar_size_vertical if self.show_vertical_scrollbar else 0)
            - sum(column.get_render_width(self) for column in columns[1:])
            - 2 * self.cell_padding,
        )
        title = columns[0]
        if not title.auto_width and title.width == width:
            return
        rows = [(row.key.value, self.get_row(row.key), row.height) for row in self.ordered_rows]
        cursor = self.cursor_row
        title.auto_width = False
        title.width = width
        with self.prevent(DataTable.RowHighlighted):
            self.clear()
            for key, cells, height in rows:
                self.add_row(*cells, key=key, height=height)
            if rows:
                self.move_cursor(row=min(cursor, len(rows) - 1))


class TaskWeaverApp(App):
    """Five deliberate views, with one stable UUID selection across refreshes."""

    TITLE = "TaskWeaver"
    SUB_TITLE = "Local tasks · optional AI"
    CSS_PATH = "styles.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        Binding("ctrl+c", "quit", "Quit", show=False),
        Binding("1", "view('list-view')", "List", show=False),
        Binding("2", "view('board-view')", "Board", show=False),
        Binding("3", "view('graph-view')", "Graph", show=False),
        Binding("4", "view('chat-tab')", "Chat", show=False),
        Binding("5", "view('insights-view')", "Insights", show=False),
        Binding("ctrl+tab", "next_view", "Next view", priority=True),
        Binding("j", "move(1)", "Down", show=False),
        Binding("k", "move(-1)", "Up", show=False),
        ("enter", "detail", "Detail"),
        Binding("space", "start_task", "Start/pause", show=False),
        ("n", "new_task", "New"),
        Binding("e", "edit_task", "Edit", show=False),
        ("c", "complete_task", "Complete"),
        Binding("x", "cancel_task", "Cancel", show=False),
        Binding("d", "dependencies", "Edges", show=False),
        Binding("f", "focus_tasks", "Focus", show=False),
        Binding("g", "new_goal", "Goal", show=False),
        Binding("s", "assess_skill", "Skill", show=False),
        Binding("r", "refresh", "Refresh", show=False),
        ("ctrl+enter", "submit_text", "Send"),
        Binding("f2", "submit_text", "Send", show=False),
    ]

    def __init__(self, db_path: Path) -> None:
        super().__init__()
        self.db_path = db_path
        self.task_repo = TaskRepository(db_path)
        self.dep_repo = TaskDependencyRepository(db_path)
        self.planning = PlanningService(db_path)
        self.priority = PriorityService(db_path)
        self.completions = CompletionRepository(db_path)
        self.chat_handler = TuiChatHandler(self)
        self.chat_started = False
        self.selected_task_id: UUID | None = None
        self.tasks: dict[UUID, Task] = {}
        self.focus_only = False
        self._refreshing = False
        self.github_repos: tuple[str, ...] = ()
        self.github_syncing = False
        self._pending_insights: tuple[str, ...] | None = None
        self._insights_queued = False
        self._refresh_requested = False
        self._refresh_running = False
        self._status_lock = asyncio.Lock()

    def compose(self) -> ComposeResult:
        """Compose five views with distinct MCDA and CD3 displays."""
        yield Header()
        with WorkspaceViews(initial="list-view", id="views"):
            with TabPane("1 List", id="list-view"):
                yield Static("MCDA = weighted factors; eff. = inherited MCDA; CD3 = value/minute", classes="legend")
                yield Static("No tasks yet. Press n to plan your first outcome.", id="empty-state")
                yield WorkspaceTable(id="task-table", cursor_type="row", zebra_stripes=True, cell_padding=1)
            with TabPane("2 Board", id="board-view"), Grid(id="board"):
                for status in TaskStatus:
                    yield WorkspaceTable(
                        id=f"board-{status.value}",
                        classes="board-column",
                        cursor_type="row",
                        zebra_stripes=True,
                        show_header=False,
                        show_cursor=False,
                    )
            with TabPane("3 Graph", id="graph-view"), VerticalScroll():
                yield Static("Active DAG: blocker → blocked; learning gaps are separate requirements", classes="legend")
                yield Static("", id="dependency-graph", markup=False)
                yield WorkspaceTable(id="graph-tasks", cursor_type="row", zebra_stripes=True)
            with TabPane("4 Chat", id="chat-tab"):
                with VerticalScroll(id="chat-view"):
                    yield Markdown("Local `/help` and `/focus` work offline; `/review UUID` uses AI. Ctrl+Enter sends.")
                yield TextArea(id="input-field", soft_wrap=True, show_line_numbers=False)
            with TabPane("5 Insights", id="insights-view"), VerticalScroll(id="insights-scroll"):
                for panel in ("insights", "insights-quick", "insights-skills", "insights-duration", "insights-history"):
                    yield Markdown("", id=panel, classes="insight-panel")
        yield Static("n new · e edit · c complete · d edges · f focus · Enter details", id="notice", markup=False)
        yield Footer()

    async def on_mount(self) -> None:
        """Initialize tables and refresh periodically without changing UUID selection."""
        self.query_one("#task-table", DataTable).add_columns("Task", "State", "Min", "MCDA", "Eff.", "CD3")
        self.query_one("#graph-tasks", DataTable).add_columns("Task", "Readiness", "MCDA")
        for status in TaskStatus:
            self.query_one(f"#board-{status.value}", DataTable).add_column("Task", width=22)
        self.query_one("#task-table", DataTable).border_title = "Task list"
        self.query_one("#graph-tasks", DataTable).border_title = "Readiness"
        self.query_one("#dependency-graph", Static).border_title = "Dependency map"
        self.query_one("#chat-view", VerticalScroll).border_title = "Conversation · local commands work offline"
        self.query_one("#input-field", TextArea).border_title = "Message · Ctrl+Enter / F2 sends"
        self.query_one("#insights-scroll", VerticalScroll).border_title = "Planning insights"
        for status in TaskStatus:
            self.query_one(f"#board-{status.value}", DataTable).border_title = status.value.replace("_", " ").title()
        self.refresh_tasks()
        await self.workers.wait_for_complete([worker for worker in self.workers if worker.group == "workspace-refresh"])
        self.set_interval(REFRESH_INTERVAL_SECONDS, self.refresh_tasks)
        self.screen.set_focus(self.query_one("#task-table", DataTable))
        config = await asyncio.to_thread(get_config)
        if config.github_repos:
            self.github_repos = tuple(config.github_repos)
            self.sync_github()
            self.set_interval(config.github_sync_interval_seconds, self.sync_github)

    def on_resize(self) -> None:
        """Keep every status column visible on narrower terminals."""
        if self.is_mounted:
            board = self.query_one("#board", Grid)
            board.styles.grid_size_columns = 2 if self.size.width < _COMPACT_BOARD_WIDTH else 4
            board.styles.grid_size_rows = 2 if self.size.width < _COMPACT_BOARD_WIDTH else 1
            self.call_after_refresh(self._resize_tables)

    def _resize_tables(self) -> None:
        """Give titles the remaining cell width, preserving all row keys and cursors."""
        for table in self.query(WorkspaceTable):
            table.fit_title()

    def on_descendant_focus(self, _event: events.DescendantFocus) -> None:
        """Only the focused Board column displays a selected card."""
        for table in self.query(".board-column"):
            if isinstance(table, DataTable):
                with table.prevent(DataTable.RowHighlighted):
                    table.show_cursor = table is self.focused
        focused = self.focused
        if (
            not self._refreshing
            and _event.widget is focused
            and isinstance(focused, DataTable)
            and "board-column" in focused.classes
            and focused.row_count
        ):
            key = focused.coordinate_to_cell_key(focused.cursor_coordinate).row_key.value
            self.selected_task_id = UUID(str(key))

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
        """Keep editing keystrokes local and block background actions under modals."""
        if len(self.screen_stack) > 1:
            return False
        if isinstance(self.focused, (TextArea, Input)):
            return action in ("next_view", "submit_text")
        if action == "submit_text":
            return self.query_one("#views", TabbedContent).active == "chat-tab"
        return True

    def _table(self) -> DataTable | None:
        if isinstance(self.focused, DataTable):
            return self.focused
        active = self.query_one("#views", TabbedContent).active
        selector = {"list-view": "#task-table", "board-view": "#board-pending", "graph-view": "#graph-tasks"}.get(
            active
        )
        return self.query_one(selector, DataTable) if selector else None

    def _fill_table(self, table: DataTable, tasks: list[Task], rows: list[tuple[Text | str, ...]]) -> None:
        previous_row = table.cursor_row
        with table.prevent(DataTable.RowHighlighted):
            table.clear()
            for task, row in zip(tasks, rows, strict=True):
                table.add_row(*row, key=str(task.task_id), height=3 if "board-column" in table.classes else 1)
            if tasks:
                selected = next(
                    (index for index, task in enumerate(tasks) if task.task_id == self.selected_task_id), None
                )
                table.move_cursor(row=selected if selected is not None else min(previous_row, len(tasks) - 1))

    def refresh_tasks(self) -> None:
        """Coalesce refresh requests; SQLite and scoring never block the UI loop."""
        self._refresh_requested = True
        if not self._refresh_running:
            self._refresh_running = True
            self._refresh_worker()

    @work(group="workspace-refresh")
    async def _refresh_worker(self) -> None:
        try:
            while self._refresh_requested:
                self._refresh_requested = False
                workspace = await asyncio.to_thread(self._load_workspace)
                if not self._refresh_requested:
                    self._apply_workspace(workspace)
        except _UI_ERRORS as error:
            self.post_error_message(f"Cannot refresh: {error}. Check the configured database and retry with r.")
        finally:
            self._refresh_running = False

    def _load_workspace(self) -> Workspace:
        tasks = self.task_repo.list_tasks_by_priority()
        effective = self.priority.calculate_effective_priorities()
        cd3 = self.dep_repo.calculate_effective_priorities()
        active = self.task_repo.list_tasks_with_deps()
        matches = {match.task_id: match for match in self.planning.match_tasks(active)}
        ready = {task.task_id for task in self.planning.recommendations().ready}
        analysis = self.planning.work_analysis()
        path = " → ".join(f"{task.title} [{str(task.task_id)[:8]}]" for task in analysis.critical_path)
        graph = [
            f"Critical path: {analysis.critical_path_minutes} working minutes · {path or 'no active tasks'}",
            "Independent branches may run in parallel; learning time and resource limits are not included.",
            "",
        ]
        for task in active:
            blockers = self.dep_repo.get_blockers(task.task_id)
            graph.extend(
                f"{blocker.title} [{str(blocker.task_id)[:8]}] → {task.title} [{str(task.task_id)[:8]}]"
                for blocker in blockers
            )
            match = matches[task.task_id]
            if match.learning_gap:
                graph.append(
                    f"Learning gap → {task.title}: {task.skill_domain} "
                    f"level {match.known_level or 'unassessed'} / required {match.required_level or 1}"
                )
            elif not blockers and not self.dep_repo.get_blocked(task.task_id):
                graph.append(f"{task.title} [{str(task.task_id)[:8]}] (independent)")
        return Workspace(
            tasks, effective, cd3, matches, ready, "\n".join(graph), self._insights(analysis, tasks, matches)
        )

    def _apply_workspace(self, workspace: Workspace) -> None:
        self._refreshing = True
        try:
            tasks, effective, cd3, matches, ready = (
                workspace.tasks,
                workspace.effective,
                workspace.cd3,
                workspace.matches,
                workspace.ready,
            )
            self.tasks = {task.task_id: task for task in tasks}
            visible = [task for task in tasks if not self.focus_only or task.task_id in ready]
            empty = self.query_one("#empty-state", Static)
            empty.display = not visible
            empty.update(
                "No ready tasks. Press f to show all tasks, or g / s to plan."
                if self.focus_only
                else "No tasks yet. Press n to plan your first outcome."
            )
            if self.selected_task_id not in {task.task_id for task in visible}:
                self.selected_task_id = visible[0].task_id if visible else None
            self._fill_table(
                self.query_one("#task-table", DataTable),
                visible,
                [
                    (
                        Text(task.title, overflow="ellipsis", no_wrap=True),
                        self._status(task.status),
                        Text(str(task.duration_min), justify="right"),
                        self._score(task.priority_score),
                        self._score(effective.get(task.task_id)),
                        Text(f"{cd3.get(task.task_id, task.priority):.2f}", justify="right"),
                    )
                    for task in visible
                ],
            )
            for status in TaskStatus:
                column = [task for task in visible if task.status == status]
                self._fill_table(
                    self.query_one(f"#board-{status.value}", DataTable),
                    column,
                    [(Text.assemble(self._score(task.priority_score), "  ", task.title),) for task in column],
                )
                self.query_one(f"#board-{status.value}", DataTable).border_subtitle = (
                    f"{len(column)} {'task' if len(column) == 1 else 'tasks'}" if column else "No tasks"
                )
            graph_tasks = [task for task in visible if task.task_id in matches]
            self._fill_table(
                self.query_one("#graph-tasks", DataTable),
                graph_tasks,
                [
                    (
                        Text(task.title, overflow="ellipsis", no_wrap=True),
                        "blocked"
                        if matches[task.task_id].blocked
                        else "learning gap"
                        if matches[task.task_id].learning_gap
                        else "ready",
                        self._score(task.priority_score),
                    )
                    for task in graph_tasks
                ],
            )
            self.query_one("#dependency-graph", Static).update(workspace.graph)
            self._queue_insights(workspace.insights)
            if self.query_one("#views", TabbedContent).active == "board-view" and isinstance(self.focused, DataTable):
                self._focus_view("board-view")
            self.call_after_refresh(self._resize_tables)
        finally:
            self._refreshing = False

    def _queue_insights(self, content: tuple[str, ...]) -> None:
        self._pending_insights = content
        if not self._insights_queued:
            self._insights_queued = True
            self.call_later(self._render_insights)

    async def _render_insights(self) -> None:
        """Serialize widget replacement; cancelling it can cancel child message pumps."""
        try:
            while self._pending_insights is not None:
                content, self._pending_insights = self._pending_insights, None
                panels = ("insights", "insights-quick", "insights-skills", "insights-duration", "insights-history")
                for panel, text in zip(panels, content, strict=True):
                    if self.chat_handler.should_exit:
                        return
                    await self.query_one(f"#{panel}", Markdown).update(text)
        finally:
            self._insights_queued = False

    @staticmethod
    def _score(value: float | None) -> Text:
        if value is None:
            return Text("—", justify="right")
        color = "red" if value >= _HIGH_PRIORITY else "yellow" if value >= _MEDIUM_PRIORITY else "green"
        return Text(f"{value:.1f}", style=color, justify="right")

    @staticmethod
    def _status(status: TaskStatus) -> Text:
        labels = {
            TaskStatus.PENDING: ("○ pending", "yellow"),
            TaskStatus.IN_PROGRESS: ("▶ active", "cyan"),
            TaskStatus.COMPLETED: ("✓ done", "green"),
            TaskStatus.CANCELLED: ("x cancelled", "dim"),
        }
        label, color = labels[status]
        return Text(label, style=color)

    def _insights(self, analysis: WorkAnalysis, tasks: list[Task], matches: dict[UUID, SkillMatch]) -> tuple[str, ...]:
        lines = ["## Goal progress"]
        panels: list[str] = []
        goals = self.planning.list_goals()
        for goal in goals:
            progress = self.planning.goal_progress(goal.goal_id)
            lines.append(
                f"- **{goal.title}**: {progress.completed}/{progress.total} "
                f"({progress.fraction:.0%}); cancelled {progress.cancelled} · `{goal.goal_id}`"
            )
        if not goals:
            lines.append("Create a goal with g; link it in the task edit form.")
        panels.append("\n\n".join(lines))
        lines = ["## Quick wins · ready work up to 30 minutes"]
        lines.extend(
            f"- {task.title} · {task.duration_min} min · {task.priority:.2f} value/min · `{task.task_id}`"
            for task in analysis.quick_wins
        )
        if not analysis.quick_wins:
            lines.append("No dependency- and skill-ready short tasks.")
        panels.append("\n\n".join(lines))
        lines = ["## Skills and assessment history"]
        skills = self.planning.list_skills()
        for skill in skills:
            lines.append(f"### {skill.domain} · level {int(skill.level)}")
            lines.extend(
                f"- {event.assessed_at.astimezone(UTC):%Y-%m-%d %H:%M UTC} · "
                f"level {int(event.level)} · {event.evidence}"
                for event in self.planning.skill_history(skill.domain)
            )
        if not skills:
            lines.append("Append evidence-backed assessments with s.")
        gaps = [
            (task, matches[task.task_id])
            for task in tasks
            if task.task_id in matches and matches[task.task_id].learning_gap
        ]
        lines.append("### Learning gaps")
        lines.extend(
            f"- {task.title} · {task.skill_domain}: assessed {match.known_level or 'unassessed'}, "
            f"required {match.required_level}"
            for task, match in gaps
        )
        if not gaps:
            lines.append("No active tasks with unmet skill requirements.")
        panels.append("\n\n".join(lines))
        lines = ["## Category duration confidence"]
        for insight in self.planning.insights():
            confidence = insight.estimate.confidence
            lines.append(
                f"- **{insight.category}**: completed {insight.completed}, cancelled {insight.cancelled}; "
                f"samples {confidence.sample_count}, median actual/raw {confidence.median_ratio}, "
                f"MAD {confidence.median_absolute_deviation}; multiplier {insight.estimate.multiplier:.2f}; "
                f"automatic adjustment {'on' if confidence.automatic_adjustment else 'off (needs 3 samples)'}. "
                "Confidence describes evidence, not a success probability."
            )
        panels.append("\n\n".join(lines))
        lines = ["## Completion history"]
        task_map = {task.task_id: task for task in tasks}
        for completion in self.completions.list_completions():
            task = task_map.get(completion.task_id)
            lines.append(
                f"- {task.title if task else completion.task_id} · {completion.status.value} · "
                f"{completion.duration_actual}/{completion.duration_expected} min actual/expected · "
                f"{completion.conclusion or 'No conclusion'}"
            )
        lines.append("Enter on a selected task shows exact scoring components and score history.")
        panels.append("\n\n".join(lines))
        return tuple(panels)

    @on(DataTable.RowHighlighted)
    def select_row(self, event: DataTable.RowHighlighted) -> None:
        """Track UUID selection only from the focused table outside refreshes."""
        if self._refreshing or event.data_table is not self.focused or not event.data_table.row_count:
            return
        key = event.data_table.coordinate_to_cell_key(event.data_table.cursor_coordinate).row_key.value
        if event.row_key.value == key:
            self.selected_task_id = UUID(str(key))

    @on(DataTable.RowSelected)
    def show_row(self, event: DataTable.RowSelected) -> None:
        """Open details for the activated row's UUID."""
        self.selected_task_id = UUID(str(event.row_key.value))
        self.action_detail()

    def action_view(self, view: str) -> None:
        """Switch views and restore the appropriate focus after layout."""
        self.query_one("#views", TabbedContent).active = view

    @on(TabbedContent.TabActivated, "#views")
    def view_activated(self, event: TabbedContent.TabActivated) -> None:
        """Restore workspace focus for mouse-driven as well as keyboard tab changes."""
        if event.pane.id:
            hints = {
                "chat-tab": "Ctrl+Enter/F2 send · Ctrl+Tab next view",
                "insights-view": "g create goal · s assess skill · r refresh · Ctrl+Tab next view",
            }
            self.query_one("#notice", Static).update(
                hints.get(event.pane.id, "n new · e edit · c complete · d edges · f focus · Enter details")
            )
            self.call_after_refresh(self._focus_view, event.pane.id)
            self.call_after_refresh(self._resize_tables)

    def _focus_view(self, view: str) -> None:
        if len(self.screen_stack) > 1 or view != self.query_one("#views", TabbedContent).active:
            return
        selector = {
            "list-view": "#task-table",
            "board-view": "#board-pending",
            "graph-view": "#graph-tasks",
            "chat-tab": "#input-field",
            "insights-view": "#insights-scroll",
        }[view]
        if view == "board-view" and self.selected_task_id is not None and self.selected_task_id in self.tasks:
            selector = f"#board-{self.tasks[self.selected_task_id].status.value}"
        target = self.query_one(selector)
        if target is not self.focused and isinstance(target, DataTable) and self.selected_task_id is not None:
            key = str(self.selected_task_id)
            if key in target.rows:
                with target.prevent(DataTable.RowHighlighted):
                    target.move_cursor(row=target.get_row_index(key))
        self.screen.set_focus(target)

    def action_next_view(self) -> None:
        """Cycle through all five views in their displayed order."""
        current = self.query_one("#views", TabbedContent).active
        self.action_view(VIEW_IDS[(VIEW_IDS.index(current) + 1) % len(VIEW_IDS)])

    def action_move(self, delta: int) -> None:
        """Move within the current table without passing its row bounds."""
        table = self._table()
        if table and table.row_count:
            table.move_cursor(row=max(0, min(table.cursor_row + delta, table.row_count - 1)))

    def _selected(self) -> Task | None:
        table = self._table()
        if table and table.row_count:
            key = table.coordinate_to_cell_key(table.cursor_coordinate).row_key.value
            self.selected_task_id = UUID(str(key))
        return self.tasks.get(self.selected_task_id) if self.selected_task_id else None

    def _changed(self, result: object) -> None:
        if result is not None:
            if isinstance(result, Task):
                self.selected_task_id = result.task_id
            self.refresh_tasks()
            self.query_one("#notice", Static).update("Saved locally. Enter shows details; r refreshes.")

    def action_new_task(self) -> None:
        """Open a task form and refresh only after a successful save."""
        self.push_screen(TaskFormScreen(self.task_repo, self.planning), self._changed)

    def action_edit_task(self) -> None:
        """Edit the selected task while preserving its UUID."""
        if task := self._selected():
            self.push_screen(TaskFormScreen(self.task_repo, self.planning, task), self._changed)

    def action_complete_task(self) -> None:
        """Record actual effort and learning for the selected task."""
        if task := self._selected():
            self.push_screen(CompletionScreen(self.planning, task), self._changed)

    def action_cancel_task(self) -> None:
        """Record cancellation through the same completion workflow."""
        if task := self._selected():
            self.push_screen(CompletionScreen(self.planning, task, cancelled=True), self._changed)

    def action_dependencies(self) -> None:
        """Manage blocker edges for the selected task."""
        if task := self._selected():
            self.push_screen(DependencyScreen(self.task_repo, self.dep_repo, task), self._changed)

    def action_start_task(self) -> None:
        """Toggle active work, refusing to start tasks with readiness gaps."""
        if task := self._selected():
            self._toggle_task(task.task_id)

    def _toggle_task_in_database(self, task_id: UUID) -> Task | None:
        task = self.task_repo.get_task(task_id)
        if task is None:
            # Another process may delete the task between refresh and keypress.
            raise TaskNotFoundError(task_id)
        if task.status not in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            return None
        if task.status == TaskStatus.PENDING and not self.planning.match(task_id).ready:
            raise ValueError("Task is not ready. Resolve dependency/skill gaps shown in Graph or /focus first.")
        status = TaskStatus.PENDING if task.status == TaskStatus.IN_PROGRESS else TaskStatus.IN_PROGRESS
        return self.task_repo.update_task(task_id, TaskUpdate(status=status))

    @work(group="task-status")
    async def _toggle_task(self, task_id: UUID) -> None:
        try:
            async with self._status_lock:
                self._changed(await asyncio.to_thread(self._toggle_task_in_database, task_id))
        except _UI_ERRORS as error:
            self.post_error_message(str(error))
            self.refresh_tasks()

    def action_focus_tasks(self) -> None:
        """Toggle the dependency- and skill-ready task filter."""
        self.focus_only = not self.focus_only
        self.refresh_tasks()
        self.query_one("#notice", Static).update(
            "Focus: dependency- and skill-ready tasks" if self.focus_only else "All tasks"
        )

    def action_new_goal(self) -> None:
        """Open a local goal creation form."""
        self.push_screen(PlanningFormScreen(self.planning), self._changed)

    def action_assess_skill(self) -> None:
        """Open an evidence-backed skill assessment form."""
        self.push_screen(PlanningFormScreen(self.planning, skill=True), self._changed)

    def action_refresh(self) -> None:
        """Reload task views from the local services."""
        self.refresh_tasks()

    def action_detail(self) -> None:
        """Show requirements, readiness and separate MCDA/CD3 explanations."""
        if task := self._selected():
            self._open_detail(task)

    @work(group="task-detail", exclusive=True)
    async def _open_detail(self, task: Task) -> None:
        try:
            details = await asyncio.to_thread(self._task_details, task)
            if len(self.screen_stack) == 1:
                self.push_screen(TaskDetailScreen(task, details))
        except _UI_ERRORS as error:
            self.post_error_message(f"Cannot open details: {error}. Refresh and retry.")

    def _task_details(self, task: Task) -> str:
        explanation = self.priority.explain(task.task_id)
        cd3 = self.dep_repo.calculate_effective_priorities().get(task.task_id, task.priority)
        match = self.planning.match(task.task_id)
        lines = [
            f"# {task.title}",
            f"UUID: `{task.task_id}`",
            f"Status: {task.status.value}",
            f"## Requirements\n{task.requirement}",
            task.description or "",
            f"Category: {task.category} · goal: {task.goal_id or 'none'}",
            f"Skill: {task.skill_domain or 'none'} / {task.required_skill_level or 'none'} · {match.reason}",
            f"Working estimate: {task.duration_min} min · immutable raw baseline: {task.raw_duration_min} min",
            f"MCDA: {explanation['score']:.4f} · effective MCDA: {explanation['effective_score']:.4f}",
            f"CD3 value/min: {task.priority:.4f} · inherited CD3: {cd3:.4f}",
            "## MCDA components",
        ]
        for name, component in explanation["components"].items():
            bar = "█" * round(component["contribution"] / 2)
            lines.append(
                f"**{name}**: raw {component['raw']}, normalized {component['normalized']:.4f}, "
                f"weight {component['weight']:.4f}, contribution {component['contribution']:.4f}\n\n`{bar}`"
            )
        lines.append(f"Weights: {explanation['preference_source']}; learning samples {explanation['learning_samples']}")
        lines.append("## Score history · " + self.priority.trend(task.task_id))
        lines.extend(f"- {event['recorded_at']}: {event['score']:.4f}" for event in self.priority.history(task.task_id))
        lines.append("## Blockers → this task")
        lines.extend(f"- {blocker.title} · `{blocker.task_id}`" for blocker in self.dep_repo.get_blockers(task.task_id))
        return "\n\n".join(lines)

    @work(group="github-sync")
    async def sync_github(self) -> None:
        """Pull configured repositories without overlapping work or remote writes."""
        if self.github_syncing or not self.github_repos:
            return
        self.github_syncing = True
        try:
            result = await run_github_sync(self.db_path, self.github_repos)
            if not self.chat_handler.should_exit:
                self.refresh_tasks()
                self.query_one("#notice", Static).update(
                    f"GitHub pull: {result.imported} new, {result.updated} updated, "
                    f"{len(result.conflicts)} conflicts. Local edits are preserved."
                )
        except (GithubException, OSError, ValueError, GitHubSyncError) as error:
            if not self.chat_handler.should_exit:
                self.post_error_message(str(error))
        finally:
            self.github_syncing = False

    @work(group="chat", exclusive=True)
    async def start_chat_worker(self) -> None:
        """Keep input and SDK requests on the UI loop so quit cancels both."""
        worker = get_current_worker()
        try:
            await run_chat_async(self.chat_handler, self.db_path, worker)
        finally:
            self.chat_started = False

    def action_submit_text(self) -> None:
        """Queue nonempty input and start a single chat worker when needed."""
        text_area = self.query_one("#input-field", TextArea)
        text = text_area.text.strip()
        if not text:
            return
        text_area.clear()
        if text.lower() in ("exit", "quit", "bye"):
            self.call_later(self.action_quit)
            return
        self._post_message_with_limit(f"**You:** {text}", "user-message")
        self.chat_handler.input_queue.put_nowait(text)
        if not self.chat_started:
            self.chat_started = True
            self.start_chat_worker()

    def _post_message_with_limit(self, message: str, classes: str) -> None:
        view = self.query_one("#chat-view", VerticalScroll)
        view.mount(Markdown(message, classes=classes))
        for child in list(view.children)[: max(0, len(view.children) - MAX_CHAT_MESSAGES)]:
            child.remove()
        self.call_after_refresh(view.scroll_end, animate=False)

    def post_agent_message(self, message: str) -> None:
        """Display an agent response and refresh any changed task state."""
        self._post_message_with_limit(f"**TaskWeaver:** {message}", "agent-message")
        self.refresh_tasks()

    def post_system_message(self, message: str) -> None:
        """Display a system notice and reload local task state."""
        self._post_message_with_limit(message, "system-message")
        self.refresh_tasks()

    def post_error_message(self, message: str) -> None:
        """Show an actionable error in both the notice and chat history."""
        self.query_one("#notice", Static).update(message)
        self._post_message_with_limit(f"**Error:** {message}", "error-message")

    def _stop_chat(self) -> None:
        self.chat_handler.shutdown()
        self.workers.cancel_all()

    async def action_quit(self) -> None:
        """Cancel workers and let them reap owned subprocesses (bounded escalation) before exiting."""
        workers = list(self.workers)
        self._stop_chat()
        # Cancelled workers raise WorkerCancelled from wait(); only their completion matters here.
        await asyncio.gather(*(worker.wait() for worker in workers), return_exceptions=True)
        self.exit()

    def on_unmount(self) -> None:
        """Stop chat workers when the app leaves the screen."""
        self._stop_chat()


def run_tui(db_path: Path) -> None:
    """Run with the supplied/configured database and native application log path."""
    logger.remove()
    log_file = get_paths().log_file
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger.add(log_file, rotation="10 MB", retention="7 days", level="INFO")
    TaskWeaverApp(db_path).run()
