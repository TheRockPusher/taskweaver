"""Chat handler implementations for agent-user communication.

This module provides abstractions for handling conversational I/O between
the AI agent and users across different interfaces (CLI, web, etc.).
"""

import asyncio
from collections.abc import Callable
from typing import Protocol

from rich.console import Console
from rich.markdown import Markdown


class ChatOutput(Protocol):
    """Messages shared by synchronous CLI and same-loop asynchronous TUI chat."""

    def display_agent_message(self, message: str) -> None:
        """Display an agent response."""
        ...

    def display_system_message(self, message: str) -> None:
        """Display a system notice."""
        ...

    def display_error(self, message: str) -> None:
        """Display an operational error."""
        ...


class ChatHandler(ChatOutput, Protocol):
    """Synchronous input used by the interactive CLI."""

    def get_user_input(self, prompt: str = "") -> str | None:
        """Read a user message, or None to end the conversation."""
        ...


class AsyncChatHandler(ChatOutput, Protocol):
    """Cancellable input consumed on the UI's event loop."""

    async def get_user_input(self, prompt: str = "") -> str | None:
        """Await a user message, or None to end the conversation."""
        ...


class ChatUI(Protocol):
    """Only the message destinations needed by the TUI chat handler."""

    def post_agent_message(self, message: str) -> None:
        """Render an agent response."""
        ...

    def post_system_message(self, message: str) -> None:
        """Render a system notice."""
        ...

    def post_error_message(self, message: str) -> None:
        """Render an operational error."""
        ...


class CliChatHandler:
    """Chat Handler for CLI usage."""

    def __init__(self) -> None:
        self.console = Console()

    def display_agent_message(self, message: str) -> None:
        """Displays the message coming from the AI agent."""
        self.console.print("[cyan]TaskWeaver:[/cyan]", end=" ")
        self.console.print(Markdown(message))
        self.console.print()  # Blank line

    def get_user_input(self, prompt: str = "") -> str | None:
        """Agent can use this to get the user input."""
        try:
            user_input = self.console.input(f"[bold green]{prompt}[/bold green]")
            if user_input.lower() in ("exit", "quit", "bye"):
                self.console.print("\n[blue]GOODBYE[/blue]")
                return None
            return user_input
        except (EOFError, KeyboardInterrupt):
            self.console.print("\n[blue]GOODBYE[/blue]")
            return None

    def display_system_message(self, message: str) -> None:
        """Display a message from the system."""
        self.console.print(f"[green]{message}[/green]")

    def display_error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(f"[red]ERROR: {message}[/red]")


class TuiChatHandler:
    """Keep UI callbacks on the input loop, including output from local-work threads."""

    def __init__(self, app: ChatUI) -> None:
        self.app = app
        self.input_queue: asyncio.Queue[str | None] = asyncio.Queue()
        self.should_exit = False
        try:
            self._loop: asyncio.AbstractEventLoop | None = asyncio.get_running_loop()
        except RuntimeError:
            self._loop = None

    def _display(self, destination: Callable[[str], None], message: str) -> None:
        if self.should_exit:
            return
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None
        if self._loop is None:
            self._loop = current_loop

        def deliver() -> None:
            # Shutdown may begin after a thread schedules this callback.
            if not self.should_exit:
                destination(message)

        if self._loop is not None and current_loop is not self._loop:
            if not self._loop.is_closed():
                try:
                    self._loop.call_soon_threadsafe(deliver)
                except RuntimeError:
                    if not self.should_exit and not self._loop.is_closed():
                        raise
        else:
            deliver()

    def display_agent_message(self, message: str) -> None:
        """Display an agent response unless shutdown has started."""
        self._display(self.app.post_agent_message, message)

    async def get_user_input(self, prompt: str = "") -> str | None:  # noqa: ARG002
        """Await queued input without leaving an uncancellable reader thread."""
        self._loop = asyncio.get_running_loop()
        if self.should_exit:
            return None
        input_text = await self.input_queue.get()
        return None if self.should_exit else input_text

    def display_system_message(self, message: str) -> None:
        """Display a system notice unless shutdown has started."""
        self._display(self.app.post_system_message, message)

    def display_error(self, message: str) -> None:
        """Display an operational error unless shutdown has started."""
        self._display(self.app.post_error_message, message)

    def shutdown(self) -> None:
        """Wake a queued reader and forbid callbacks before the UI unmounts."""
        if not self.should_exit:
            self.should_exit = True
            self.input_queue.put_nowait(None)
