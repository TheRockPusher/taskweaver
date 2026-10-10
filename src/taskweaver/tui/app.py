"""Credential-free local workspace with optional shared conversational assistance."""

import sqlite3
from pathlib import Path
from typing import ClassVar
from uuid import UUID

from github import GithubException
from loguru import logger
from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Horizontal, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Markdown, Static, TabbedContent, TabPane, TextArea
from textual.worker import get_current_worker

from ..agents.chat_handler import TuiChatHandler
from ..agents.github_sync import GitHubSyncError, run_github_sync
from ..agents.orchestrator import run_chat_async
from ..config import get_config, get_paths
from ..database.completion_repository import CompletionRepository
from ..database.dependency_repository import TaskDependencyRepository
from ..database.exceptions import DependencyError, TaskNotFoundError
from ..database.models import Task, TaskStatus, TaskUpdate
from ..database.planning import PlanningService, WorkAnalysis
from ..database.priority_service import PriorityService
from ..database.repository import TaskRepository
from .constants import MAX_CHAT_MESSAGES, MAX_TITLE_LENGTH, REFRESH_INTERVAL_SECONDS, VIEW_IDS
from .screens import CompletionScreen, DependencyScreen, PlanningFormScreen, TaskDetailScreen, TaskFormScreen

_UI_ERRORS = (ValueError, TaskNotFoundError, DependencyError, sqlite3.Error, OSError)
_HIGH_PRIORITY = 70
_MEDIUM_PRIORITY = 40


class TaskWeaverApp(App):
    """Five deliberate views, with one stable UUID selection across refreshes."""

    TITLE = "TaskWeaver"
    SUB_TITLE = "Local tasks · optional AI"
    CSS_PATH = "styles.tcss"
    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("1", "view('list-view')", "List"),
        ("2", "view('board-view')", "Board"),
        ("3", "view('graph-view')", "Graph"),
        ("4", "view('chat-tab')", "Chat"),
        ("5", "view('insights-view')", "Insights"),
        Binding("ctrl+tab", "next_view", "Next view", priority=True),
        ("j", "move(1)", "Down"),
        ("k", "move(-1)", "Up"),
        ("enter", "detail", "Detail"),
        ("space", "start_task", "Start/pause"),
        ("n", "new_task", "New"),
        ("e", "edit_task", "Edit"),
        ("c", "complete_task", "Complete"),
        ("x", "cancel_task", "Cancel"),
        ("d", "dependencies", "Edges"),
        ("f", "focus_tasks", "Focus"),
        ("g", "new_goal", "Goal"),
        ("s", "assess_skill", "Skill"),
        ("r", "refresh", "Refresh"),
        ("ctrl+enter", "submit_text", "Send"),
        ("f2", "submit_text", "Send"),
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
        self._pending_insights: str | None = None
        self._insights_queued = False

    def compose(self) -> ComposeResult:
        """Compose five views with distinct MCDA and CD3 displays."""
        yield Header()
        with TabbedContent(initial="list-view", id="views"):
            with TabPane("List", id="list-view"):
                yield Static("MCDA = weighted factors; eff. = inherited MCDA; CD3 = value/minute", classes="legend")
                yield DataTable(id="task-table", cursor_type="row")
            with TabPane("Board", id="board-view"), Horizontal(id="board"):
                for status in TaskStatus:
                    with VerticalScroll(classes="board-column"):
                        yield Static(status.value.replace("_", " ").title(), classes="legend")
                        yield DataTable(id=f"board-{status.value}", cursor_type="row")
            with TabPane("Graph", id="graph-view"), VerticalScroll():
                yield Static("Active DAG: blocker → blocked; learning gaps are separate requirements", classes="legend")
                yield Static("", id="dependency-graph", markup=False)
                yield DataTable(id="graph-tasks", cursor_type="row")
            with TabPane("Chat", id="chat-tab"):
                with VerticalScroll(id="chat-view"):
                    yield Markdown("Local `/help` and `/focus` work offline; `/review UUID` uses AI. Ctrl+Enter sends.")
                yield TextArea(id="input-field", soft_wrap=True, show_line_numbers=False)
            with TabPane("Insights", id="insights-view"), VerticalScroll(id="insights-scroll"):
                yield Markdown("", id="insights")
        yield Static("n new · e edit · c complete · d edges · f focus · Enter details", id="notice", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        """Initialize tables and refresh periodically without changing UUID selection."""
        self.query_one("#task-table", DataTable).add_columns("Task", "State", "Min", "MCDA", "Eff.", "CD3")
        self.query_one("#graph-tasks", DataTable).add_columns("Task", "Readiness", "MCDA")
        for status in TaskStatus:
            self.query_one(f"#board-{status.value}", DataTable).add_column("Task")
        self.refresh_tasks()
        self.set_interval(REFRESH_INTERVAL_SECONDS, self.refresh_tasks)
        self.query_one("#task-table", DataTable).focus()
        config = get_config()
        if config.github_repos:
            self.github_repos = tuple(config.github_repos)
            self.sync_github()
            self.set_interval(config.github_sync_interval_seconds, self.sync_github)

    def check_action(self, action: str, _parameters: tuple[object, ...]) -> bool | None:
        """Keep editing keystrokes local and block background actions under modals."""
        if isinstance(self.focused, TextArea) and action not in ("quit", "next_view", "submit_text"):
            return False
        return not (len(self.screen_stack) > 1 and action not in ("quit",))

    def _table(self) -> DataTable | None:
        if isinstance(self.focused, DataTable):
            return self.focused
        active = self.query_one("#views", TabbedContent).active
        selector = {"list-view": "#task-table", "board-view": "#board-pending", "graph-view": "#graph-tasks"}.get(
            active
        )
        return self.query_one(selector, DataTable) if selector else None

    def _fill_table(self, table: DataTable, tasks: list[Task], rows: list[tuple[str, ...]]) -> None:
        previous_row = table.cursor_row
        table.clear()
        for task, row in zip(tasks, rows, strict=True):
            table.add_row(*row, key=str(task.task_id))
        if tasks:
            selected = next((index for index, task in enumerate(tasks) if task.task_id == self.selected_task_id), None)
            table.move_cursor(row=selected if selected is not None else min(previous_row, len(tasks) - 1))

    def refresh_tasks(self) -> None:
        """Read real services; keep selection by identity, not a changing row number."""
        self._refreshing = True
        try:
            tasks = self.task_repo.list_tasks_by_priority()
            self.tasks = {task.task_id: task for task in tasks}
            effective = self.priority.calculate_effective_priorities()
            cd3 = self.dep_repo.calculate_effective_priorities()
            active = self.task_repo.list_tasks_with_deps()
            matches = {match.task_id: match for match in self.planning.match_tasks(active)}
            recommendations = self.planning.recommendations()
            ready = {task.task_id for task in recommendations.ready}
            visible = [task for task in tasks if not self.focus_only or task.task_id in ready]
            if self.selected_task_id not in {task.task_id for task in visible}:
                self.selected_task_id = visible[0].task_id if visible else None
            self._fill_table(
                self.query_one("#task-table", DataTable),
                visible,
                [
                    (
                        task.title[:MAX_TITLE_LENGTH],
                        task.status.value.replace("in_progress", "active"),
                        str(task.duration_min),
                        self._score(task.priority_score),
                        self._score(effective.get(task.task_id)),
                        f"{cd3.get(task.task_id, task.priority):.2f}",
                    )
                    for task in visible
                ],
            )
            for status in TaskStatus:
                column = [task for task in visible if task.status == status]
                self._fill_table(
                    self.query_one(f"#board-{status.value}", DataTable),
                    column,
                    [(f"{self._score(task.priority_score)} {escape(task.title[:10])}",) for task in column],
                )
            graph_tasks = [task for task in visible if task.task_id in matches]
            self._fill_table(
                self.query_one("#graph-tasks", DataTable),
                graph_tasks,
                [
                    (
                        task.title[:MAX_TITLE_LENGTH],
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
            self.query_one("#dependency-graph", Static).update("\n".join(graph))
            self._queue_insights(self._insights(analysis))
        except _UI_ERRORS as error:
            self.post_error_message(f"Cannot refresh: {error}. Check the configured database and retry with r.")
        finally:
            self._refreshing = False

    def _queue_insights(self, content: str) -> None:
        self._pending_insights = content
        if not self._insights_queued:
            self._insights_queued = True
            self.call_later(self._render_insights)

    async def _render_insights(self) -> None:
        """Serialize widget replacement; cancelling it can cancel child message pumps."""
        try:
            while self._pending_insights is not None:
                content, self._pending_insights = self._pending_insights, None
                await self.query_one("#insights", Markdown).update(content)
        finally:
            self._insights_queued = False

    @staticmethod
    def _score(value: float | None) -> str:
        if value is None:
            return "—"
        color = "red" if value >= _HIGH_PRIORITY else "yellow" if value >= _MEDIUM_PRIORITY else "green"
        return f"[{color}]{value:.1f}[/]"

    def _insights(self, analysis: WorkAnalysis) -> str:
        lines = ["# Goals · skills · completion learning", "## Goal progress"]
        for goal in self.planning.list_goals():
            progress = self.planning.goal_progress(goal.goal_id)
            lines.append(
                f"- **{goal.title}**: {progress.completed}/{progress.total} "
                f"({progress.fraction:.0%}); cancelled {progress.cancelled} · `{goal.goal_id}`"
            )
        lines.append("Create a goal with g; link it in the task edit form.")
        lines.append("## Quick wins · ready work up to 30 minutes")
        lines.extend(
            f"- {task.title} · {task.duration_min} min · {task.priority:.2f} value/min · `{task.task_id}`"
            for task in analysis.quick_wins
        )
        if not analysis.quick_wins:
            lines.append("No dependency- and skill-ready short tasks.")
        lines.append("## Skills and assessment history")
        for skill in self.planning.list_skills():
            lines.append(f"### {skill.domain} · level {int(skill.level)}")
            lines.extend(
                f"- {event.assessed_at.isoformat()} · level {int(event.level)} · {event.evidence}"
                for event in self.planning.skill_history(skill.domain)
            )
        lines.append("Append evidence-backed assessments with s.")
        lines.append("## Category duration confidence")
        for insight in self.planning.insights():
            confidence = insight.estimate.confidence
            lines.append(
                f"- **{insight.category}**: completed {insight.completed}, cancelled {insight.cancelled}; "
                f"samples {confidence.sample_count}, median actual/raw {confidence.median_ratio}, "
                f"MAD {confidence.median_absolute_deviation}; multiplier {insight.estimate.multiplier:.2f}; "
                f"automatic adjustment {'on' if confidence.automatic_adjustment else 'off (needs 3 samples)'}. "
                "Confidence describes evidence, not a success probability."
            )
        lines.append("## Completion history")
        for completion in self.completions.list_completions():
            task = self.tasks.get(completion.task_id)
            lines.append(
                f"- {task.title if task else completion.task_id} · {completion.status.value} · "
                f"{completion.duration_actual}/{completion.duration_expected} min actual/expected · "
                f"{completion.conclusion or 'No conclusion'}"
            )
        lines.append("Enter on a selected task shows exact scoring components and score history.")
        return "\n\n".join(lines)

    @on(DataTable.RowHighlighted)
    def select_row(self, event: DataTable.RowHighlighted) -> None:
        """Track UUID selection only from the focused table outside refreshes."""
        if self._refreshing or event.data_table is not self.focused:
            return
        self.selected_task_id = UUID(str(event.row_key.value))

    @on(DataTable.RowSelected)
    def show_row(self, event: DataTable.RowSelected) -> None:
        """Open details for the activated row's UUID."""
        self.selected_task_id = UUID(str(event.row_key.value))
        self.action_detail()

    def action_view(self, view: str) -> None:
        """Switch views and restore the appropriate focus after layout."""
        self.query_one("#views", TabbedContent).active = view
        self.call_after_refresh(self._focus_view, view)

    def _focus_view(self, view: str) -> None:
        selector = {
            "list-view": "#task-table",
            "board-view": "#board-pending",
            "graph-view": "#graph-tasks",
            "chat-tab": "#input-field",
            "insights-view": "#insights-scroll",
        }[view]
        if view == "board-view" and self.selected_task_id is not None and self.selected_task_id in self.tasks:
            selector = f"#board-{self.tasks[self.selected_task_id].status.value}"
        self.query_one(selector).focus()

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
        task = self._selected()
        if task and task.status in (TaskStatus.PENDING, TaskStatus.IN_PROGRESS):
            try:
                if task.status == TaskStatus.PENDING and not self.planning.match(task.task_id).ready:
                    self.post_error_message(
                        "Task is not ready. Resolve dependency/skill gaps shown in Graph or /focus first."
                    )
                    return
                status = TaskStatus.PENDING if task.status == TaskStatus.IN_PROGRESS else TaskStatus.IN_PROGRESS
                self._changed(self.task_repo.update_task(task.task_id, TaskUpdate(status=status)))
            except _UI_ERRORS as error:
                self.post_error_message(str(error))

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
        task = self._selected()
        if task is None:
            return
        try:
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
            lines.append(
                f"Weights: {explanation['preference_source']}; learning samples {explanation['learning_samples']}"
            )
            lines.append("## Score history · " + self.priority.trend(task.task_id))
            lines.extend(
                f"- {event['recorded_at']}: {event['score']:.4f}" for event in self.priority.history(task.task_id)
            )
            lines.append("## Blockers → this task")
            lines.extend(
                f"- {blocker.title} · `{blocker.task_id}`" for blocker in self.dep_repo.get_blockers(task.task_id)
            )
            self.push_screen(TaskDetailScreen(task, "\n\n".join(lines)))
        except _UI_ERRORS as error:
            self.post_error_message(f"Cannot open details: {error}. Refresh and retry.")

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

    @work(exclusive=True)
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
            self._stop_chat()
            self.exit()
            return
        self._post_message_with_limit(f"**You:** {text}", "user-message")
        self.chat_handler.input_queue.put_nowait(text)
        if not self.chat_started:
            self.chat_started = True
            self.start_chat_worker()

    def _post_message_with_limit(self, message: str, classes: str) -> None:
        view = self.query_one("#chat-view", VerticalScroll)
        view.mount(Markdown(message, classes=classes))
        for child in list(view.children)[: max(0, len(view.children) - MAX_CHAT_MESSAGES + 1)]:
            child.remove()
        view.scroll_end(animate=False)

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
        """Unblock queued chat input and cancel workers before exiting."""
        self._stop_chat()
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
