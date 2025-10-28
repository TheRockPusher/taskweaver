"""Terminal User Interface for TaskWeaver using Textual.

This module provides a rich TUI for interacting with TaskWeaver, featuring:
- Interactive chat interface with AI agent
- Live task tables showing open and unblocked tasks
- Real-time priority updates
- Terminal theme colors for consistent appearance
"""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import ClassVar

from loguru import logger
from pydantic_ai.exceptions import (
    AgentRunError,
    ModelHTTPError,
    UnexpectedModelBehavior,
    UsageLimitExceeded,
)
from textual import work
from textual.app import App, ComposeResult
from textual.binding import BindingType
from textual.containers import Container, VerticalScroll
from textual.widgets import DataTable, Footer, Header, Markdown, Static, TextArea
from textual.worker import Worker, get_current_worker

from ..agents.chat_handler import TuiChatHandler
from ..agents.task_agent import run_chat
from ..database.dependency_repository import TaskDependencyRepository
from ..database.exceptions import DependencyError, TaskNotFoundError
from ..database.models import TaskWithPriority
from ..database.repository import TaskRepository
from .constants import (
    EDITOR_FALLBACK_CHAIN,
    MAX_CHAT_MESSAGES,
    MAX_TITLE_LENGTH,
    REFRESH_INTERVAL_SECONDS,
    WidgetIDs,
)


class TaskWeaverApp(App):
    """Main Textual TUI Application for TaskWeaver.

    Features:
    - Chat interface for AI agent interaction
    - Live task tables with priority sorting
    - Automatic refresh every 5 seconds
    - Keyboard shortcuts (q to quit, Ctrl+C to exit)
    """

    TITLE = "🧵 TaskWeaver"
    SUB_TITLE = "AI Task Manager"

    BINDINGS: ClassVar[list[BindingType]] = [
        ("q", "quit", "Quit"),
        ("ctrl+c", "quit", "Quit"),
        ("ctrl+e", "open_editor", "Open Editor"),
        ("ctrl+enter", "submit_text", "Submit"),
        ("f2", "submit_text", "Submit"),
    ]

    CSS_PATH = "styles.tcss"

    def __init__(self, db_path: Path) -> None:
        """Initialize the TaskWeaver TUI application.

        Args:
            db_path: Path to the SQLite database file.
        """
        super().__init__()
        self.db_path = db_path

        # Set up repositories for task display only
        self.task_repo = TaskRepository(db_path)
        self.dep_repo = TaskDependencyRepository(db_path)

        # Create TUI chat handler (run_chat will use this)
        self.chat_handler = TuiChatHandler(self)

        logger.info(f"TaskWeaver TUI initialized with database: {db_path}")

    def compose(self) -> ComposeResult:
        """Build UI layout.

        Yields:
            UI components in hierarchical order.
        """
        # Header with clock
        yield Header(show_clock=True)

        # Chat section (top 60%)
        with Container(id=WidgetIDs.CHAT_CONTAINER), VerticalScroll(id=WidgetIDs.CHAT_VIEW):
            yield Markdown("Type a message below to interact with TaskWeaver.")

        # Tasks section (bottom 40%)
        with Container(id=WidgetIDs.TASKS_CONTAINER):
            with Container(id=WidgetIDs.OPEN_TASKS):
                yield Static("Open Tasks (by Effective Priority)", classes="task-header")
                yield DataTable(id=WidgetIDs.OPEN_TASKS_TABLE)
            with Container(id=WidgetIDs.UNBLOCKED_TASKS):
                yield Static("Unblocked Tasks", classes="task-header")
                yield DataTable(id=WidgetIDs.UNBLOCKED_TASKS_TABLE)

        # TextArea at bottom (multiline input)
        yield TextArea(
            id="input-field",
            language=None,  # No syntax highlighting
            show_line_numbers=False,
            soft_wrap=True,
        )

        # Footer with keybindings
        yield Footer()

    def on_mount(self) -> None:
        """Initialize widgets and start chat worker."""
        logger.debug("TUI mounted, initializing widgets")

        self.setup_task_tables()
        self.refresh_tasks()
        # Refresh task data periodically
        self.set_interval(REFRESH_INTERVAL_SECONDS, self.refresh_tasks)

        # Start run_chat() in background worker thread
        self.start_chat_worker()

    @work(thread=True, exclusive=True)
    def start_chat_worker(self) -> None:
        """Run agent loop with cancellation support.

        This runs the same agent loop as CLI, bridging blocking I/O
        with event-driven TUI via TuiChatHandler's queue.

        Worker can be cancelled cleanly via on_unmount or app exit.
        """
        worker: Worker = get_current_worker()
        logger.info("Starting chat worker thread")

        try:
            run_chat(self.chat_handler, self.db_path, worker)
        except (ModelHTTPError, AgentRunError, UsageLimitExceeded, UnexpectedModelBehavior) as e:
            # AI model errors
            logger.error(f"Chat worker AI model error: {e}")
            if not worker.is_cancelled:
                self.call_from_thread(self.post_error_message, f"AI error: {e}")
        except (TaskNotFoundError, DependencyError, OSError) as e:
            # Database and file system errors
            logger.error(f"Chat worker database error: {e}")
            if not worker.is_cancelled:
                self.call_from_thread(self.post_error_message, f"Database error: {e}")
        except (ValueError, TypeError, RuntimeError) as e:
            # Runtime errors and validation failures
            logger.error(f"Chat worker runtime error: {e}")
            if not worker.is_cancelled:
                self.call_from_thread(self.post_error_message, f"Runtime error: {e}")
        finally:
            logger.info("Chat worker thread ended")

    def setup_task_tables(self) -> None:
        """Configure DataTable columns for both task tables."""
        open_table = self.query_one(f"#{WidgetIDs.OPEN_TASKS_TABLE}", DataTable)
        open_table.add_columns(
            "Title",
            "Duration",
            "Priority",
            "Eff. Priority",
            "Status",
            "Blocked By",
        )

        unblocked_table = self.query_one(f"#{WidgetIDs.UNBLOCKED_TASKS_TABLE}", DataTable)
        unblocked_table.add_columns(
            "Title",
            "Duration",
            "Requirement",
            "Priority",
            "Eff. Priority",
            "Status",
        )
        logger.debug("Task tables configured with duration and requirement columns")

    def refresh_tasks(self) -> None:
        """Refresh task data from database and update UI tables.

        Uses repository methods for business logic, keeping UI layer focused
        on display responsibilities only.
        """
        try:
            # Get all open tasks sorted by effective priority (repository handles business logic)
            open_tasks = self.dep_repo.get_open_tasks_sorted()

            # Filter to unblocked tasks (repository handles filtering logic)
            unblocked_tasks = self.dep_repo.get_unblocked_tasks(open_tasks)

            # Update tables (UI responsibility)
            self.update_open_tasks_table(open_tasks)
            self.update_unblocked_tasks_table(unblocked_tasks)

            logger.debug(f"Refreshed tasks: {len(open_tasks)} open, {len(unblocked_tasks)} unblocked")
        except (TaskNotFoundError, DependencyError) as e:
            logger.error(f"Database error refreshing tasks: {e}")
            self.post_error_message(f"Failed to refresh tasks: {e}")
        except OSError as e:
            logger.error(f"File system error refreshing tasks: {e}")
            self.post_error_message(f"Database access error: {e}")

    def update_open_tasks_table(self, tasks: list[TaskWithPriority]) -> None:
        """Update open tasks DataTable with duration column.

        Args:
            tasks: List of tasks with priority information.
        """
        table = self.query_one(f"#{WidgetIDs.OPEN_TASKS_TABLE}", DataTable)
        table.clear()
        for task in tasks:
            table.add_row(
                task.title[:MAX_TITLE_LENGTH],  # Truncate long titles
                str(task.duration_min),
                f"{task.priority:.3f}",
                f"{task.effective_priority:.3f}",
                task.status,
                str(task.active_blocker_count),
            )

    def update_unblocked_tasks_table(self, tasks: list[TaskWithPriority]) -> None:
        """Update unblocked tasks DataTable with duration and requirement.

        Args:
            tasks: List of unblocked tasks with priority information.
        """
        table = self.query_one(f"#{WidgetIDs.UNBLOCKED_TASKS_TABLE}", DataTable)
        table.clear()
        for task in tasks:
            table.add_row(
                task.title[:MAX_TITLE_LENGTH],
                str(task.duration_min),
                task.requirement[:MAX_TITLE_LENGTH],
                f"{task.priority:.3f}",
                f"{task.effective_priority:.3f}",
                task.status,
            )

    def action_submit_text(self) -> None:
        """Submit TextArea content (Ctrl+Enter or F2)."""
        text_area = self.query_one(TextArea)
        user_input = text_area.text.strip()

        if not user_input:
            return

        # Clear TextArea
        text_area.clear()

        # Display user message
        chat_view = self.query_one(f"#{WidgetIDs.CHAT_VIEW}", VerticalScroll)
        chat_view.mount(Markdown(f"**You:** {user_input}", classes="user-message"))
        chat_view.scroll_end(animate=False)

        # Check for exit commands
        if user_input.lower() in ("exit", "quit", "bye"):
            logger.info("User requested exit via input")
            self.chat_handler.should_exit = True
            self.chat_handler.input_queue.put(None)
            self.exit()
            return

        # Put input in queue for run_chat() worker to process
        self.chat_handler.input_queue.put(user_input)
        logger.debug(f"User input queued for agent: {user_input[:50]}...")

    def action_open_editor(self) -> None:
        """Open external editor (Ctrl+E).

        Uses EDITOR environment variable, falls back to vim → nano → vi.
        Suspends TUI while editor is open, then loads content back.
        """
        # Get editor command
        editor = self._get_editor_command()
        if not editor:
            self.post_error_message("No suitable editor found (tried: vim, nano, vi)")
            return

        # Get current TextArea content
        text_area = self.query_one(TextArea)
        current_text = text_area.text

        # Create temp file
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tf:
                tf.write(current_text)
                temp_path = Path(tf.name)
        except OSError as e:
            logger.error(f"Failed to create temp file: {e}")
            self.post_error_message(f"Failed to create temp file: {e}")
            return

        # Suspend TUI and open editor
        try:
            with self.suspend():
                result = subprocess.call([editor, str(temp_path)])  # noqa: S603

            if result != 0:
                logger.warning(f"Editor exited with code {result}")
                self.post_system_message(f"Editor exited with code {result}")

            # Read back edited content
            try:
                edited_text = temp_path.read_text(encoding="utf-8")
                text_area.text = edited_text
                logger.info(f"Loaded {len(edited_text)} characters from editor")
            except OSError as e:
                logger.error(f"Failed to read edited file: {e}")
                self.post_error_message(f"Failed to read edited file: {e}")

        finally:
            # Clean up temp file
            try:
                temp_path.unlink()
            except OSError as e:
                logger.warning(f"Failed to delete temp file: {e}")

    def _get_editor_command(self) -> str | None:
        """Get editor command from environment or fallback chain.

        Returns:
            Editor command if found, None otherwise.
        """
        # Try EDITOR environment variable
        editor = os.environ.get("EDITOR")
        if editor:
            # Verify it exists in PATH
            if self._command_exists(editor):
                return editor
            logger.warning(f"EDITOR={editor} not found in PATH, trying fallbacks")

        # Try fallback chain
        for fallback in EDITOR_FALLBACK_CHAIN:
            if self._command_exists(fallback):
                return fallback

        return None

    def _command_exists(self, cmd: str) -> bool:
        """Check if command exists in PATH.

        Args:
            cmd: Command to check.

        Returns:
            True if command exists, False otherwise.
        """
        return subprocess.call(["which", cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0  # noqa: S603, S607

    def _post_message_with_limit(self, message: str, classes: str) -> None:
        """Post message with history limit (DRY helper).

        Adds message to chat view and prunes oldest messages if history
        exceeds MAX_CHAT_MESSAGES to prevent memory leak.

        Args:
            message: Formatted message text (may contain markdown).
            classes: CSS classes to apply to message widget.
        """
        chat_view = self.query_one(f"#{WidgetIDs.CHAT_VIEW}", VerticalScroll)

        # Add new message
        chat_view.mount(Markdown(message, classes=classes))

        # Prune if over limit (FIFO)
        messages = list(chat_view.children)
        if len(messages) > MAX_CHAT_MESSAGES:
            # Remove oldest message
            messages[0].remove()

        chat_view.scroll_end(animate=False)

    def post_agent_message(self, message: str) -> None:
        """Display agent message in chat view.

        Args:
            message: Agent's response message, may contain markdown.
        """
        self._post_message_with_limit(f"**TaskWeaver:** {message}", "agent-message")

    def post_system_message(self, message: str) -> None:
        """Display system message in chat view.

        Args:
            message: System notification message.
        """
        self._post_message_with_limit(f"*{message}*", "system-message")

    def post_error_message(self, message: str) -> None:
        """Display error message in chat view.

        Args:
            message: Error message text.
        """
        self._post_message_with_limit(f"**ERROR:** {message}", "error-message")

    def on_unmount(self) -> None:
        """Clean up resources on app exit.

        Pushes sentinel (None) into input queue to wake up blocked worker thread,
        then cancels workers. This prevents thread leak on exit.
        """
        # Signal exit and wake up blocked worker
        self.chat_handler.should_exit = True
        self.chat_handler.input_queue.put(None)

        # Cancel all workers to ensure clean exit
        self.workers.cancel_all()
        logger.debug("TUI unmounted, workers cancelled")


def run_tui(db_path: Path) -> None:
    """Entry point to run the TUI application.

    Args:
        db_path: Path to the SQLite database file.
    """
    # Configure loguru to write to file only (prevents terminal corruption)
    logger.remove()  # Remove all handlers including default stderr

    # Set up log file
    log_dir = Path.home() / ".taskweaver"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "tui.log"

    logger.add(
        log_file,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.info("Starting TaskWeaver TUI")
    app = TaskWeaverApp(db_path)
    app.run()
