"""Protocols for TUI interfaces.

This module defines protocols (interfaces) for TUI components to enable
dependency injection, loose coupling, and easier testing.
"""

from collections.abc import Callable
from typing import Protocol


class MessageDisplay(Protocol):
    """Protocol for displaying messages in UI.

    Enables dependency injection and testing by defining
    the minimal interface needed for message display.

    This protocol allows TuiChatHandler to depend on an interface
    rather than the concrete TaskWeaverApp class, following the
    Dependency Inversion Principle.
    """

    def post_agent_message(self, message: str) -> None:
        """Display agent message.

        Args:
            message: Agent's response message, may contain markdown.
        """
        ...

    def post_system_message(self, message: str) -> None:
        """Display system message.

        Args:
            message: System notification message.
        """
        ...

    def post_error_message(self, message: str) -> None:
        """Display error message.

        Args:
            message: Error message text.
        """
        ...

    def call_from_thread(self, func: Callable[..., object], *args: object) -> None:
        """Call a function from worker thread (thread-safe UI update).

        Args:
            func: Function to call in main thread.
            args: Arguments to pass to function.
        """
        ...
