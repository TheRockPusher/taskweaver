"""Tests for chat handler implementations."""

from unittest.mock import patch

import pytest

from taskweaver.agents.chat_handler import CliChatHandler


class TestCliChatHandler:
    """Tests for CliChatHandler."""

    @pytest.fixture
    def handler(self) -> CliChatHandler:
        """Create CliChatHandler instance."""
        return CliChatHandler()

    @pytest.mark.parametrize("exit_word", ["exit", "quit", "bye", "EXIT", "QUIT", "BYE"])
    def test_get_user_input_exits_on_keywords(self, handler: CliChatHandler, exit_word: str) -> None:
        """Test get_user_input returns None on exit keywords."""
        with patch.object(handler.console, "input", return_value=exit_word):
            result = handler.get_user_input("You: ")
            assert result is None

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
