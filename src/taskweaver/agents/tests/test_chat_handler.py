"""Tests for chat handler implementations."""

from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console

from taskweaver.agents.chat_handler import CliChatHandler


class TestCliChatHandler:
    """Tests for CliChatHandler."""

    @pytest.fixture
    def handler(self) -> CliChatHandler:
        """Create CliChatHandler instance."""
        return CliChatHandler()

    def test_display_agent_message(self, handler: CliChatHandler) -> None:
        """Test displaying agent message with Rich markdown formatting."""
        output = StringIO()
        handler.console = Console(file=output, force_terminal=True, width=80)

        handler.display_agent_message("Hello **world**")

        result = output.getvalue()
        assert "TaskWeaver:" in result
        assert "Hello" in result

    def test_display_system_message(self, handler: CliChatHandler) -> None:
        """Test displaying system message with green formatting."""
        output = StringIO()
        handler.console = Console(file=output, force_terminal=True, width=80)

        handler.display_system_message("System ready")

        result = output.getvalue()
        assert "System ready" in result

    def test_display_error(self, handler: CliChatHandler) -> None:
        """Test displaying error message with red formatting."""
        output = StringIO()
        handler.console = Console(file=output, force_terminal=True, width=80)

        handler.display_error("Something went wrong")

        result = output.getvalue()
        assert "ERROR: Something went wrong" in result

    @pytest.mark.parametrize("exit_word", ["exit", "quit", "bye", "EXIT", "QUIT", "BYE"])
    def test_get_user_input_exits_on_keywords(self, handler: CliChatHandler, exit_word: str) -> None:
        """Test get_user_input returns None on exit keywords."""
        with patch.object(handler.console, "input", return_value=exit_word):
            result = handler.get_user_input("You: ")
            assert result is None

    def test_get_user_input_returns_text(self, handler: CliChatHandler) -> None:
        """Test get_user_input returns user text for normal input."""
        with patch.object(handler.console, "input", return_value="Hello agent"):
            result = handler.get_user_input("You: ")
            assert result == "Hello agent"

    def test_get_user_input_handles_eof(self, handler: CliChatHandler) -> None:
        """Test get_user_input returns None on EOFError."""
        with patch.object(handler.console, "input", side_effect=EOFError):
            result = handler.get_user_input("You: ")
            assert result is None

    def test_get_user_input_handles_keyboard_interrupt(self, handler: CliChatHandler) -> None:
        """Test get_user_input returns None on KeyboardInterrupt."""
        with patch.object(handler.console, "input", side_effect=KeyboardInterrupt):
            result = handler.get_user_input("You: ")
            assert result is None
