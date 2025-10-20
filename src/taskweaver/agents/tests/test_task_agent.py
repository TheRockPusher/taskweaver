"""Tests for task_agent module."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from taskweaver.agents import task_agent

from ..task_agent import load_prompt, run_chat


class TestLoadPrompt:
    """Tests for load_prompt function."""

    def test_load_prompt_success(self, tmp_path: Path) -> None:
        """Test loading a prompt file successfully."""
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        prompt_file = prompts_dir / "test_prompt.md"
        prompt_content = "# Test Prompt\n\nThis is a test prompt."
        prompt_file.write_text(prompt_content, encoding="utf-8")

        original = task_agent.PROMPTS_DIR
        task_agent.PROMPTS_DIR = prompts_dir
        try:
            assert load_prompt("test_prompt") == prompt_content
        finally:
            task_agent.PROMPTS_DIR = original

    def test_load_prompt_file_not_found(self) -> None:
        """Test loading a non-existent prompt file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent_prompt")


class TestRunChat:
    """Tests for run_chat function."""

    def test_exits_on_none_input(self, mock_agent, mock_handler, db_path):  # type: ignore[no-untyped-def]
        """Test chat exits when handler returns None."""
        handler = mock_handler([None])
        run_chat(handler, db_path)  # type: ignore[arg-type]
        expected_system_messages = 2  # Welcome + goodbye
        assert len(handler.system_messages) == expected_system_messages
        assert mock_agent.run_sync.call_count == 0

    def test_skips_empty_input(self, mock_agent, mock_handler, db_path):  # type: ignore[no-untyped-def]
        """Test chat skips empty/whitespace-only inputs."""
        handler = mock_handler(["", "   ", "\t", None])
        run_chat(handler, db_path)  # type: ignore[arg-type]
        assert mock_agent.run_sync.call_count == 0

    def test_processes_user_input(self, mock_agent, mock_handler, db_path):  # type: ignore[no-untyped-def]
        """Test chat processes valid user input."""
        mock_result = Mock(output="Hello, user!", all_messages=lambda: [Mock(), Mock()])
        mock_agent.run_sync.return_value = mock_result

        handler = mock_handler(["Hello, agent!", None])
        run_chat(handler, db_path)  # type: ignore[arg-type]

        assert mock_agent.run_sync.call_count == 1
        assert mock_agent.run_sync.call_args[0][0] == "Hello, agent!"
        assert handler.agent_messages[0] == "Hello, user!"

    def test_maintains_message_history(self, mock_agent, mock_handler, db_path):  # type: ignore[no-untyped-def]
        """Test chat maintains message history across turns."""
        mock_agent.run_sync.side_effect = [
            Mock(output="Response 1", all_messages=lambda: [Mock(), Mock()]),
            Mock(output="Response 2", all_messages=lambda: [Mock(), Mock(), Mock(), Mock()]),
        ]

        handler = mock_handler(["First", "Second", None])
        run_chat(handler, db_path)  # type: ignore[arg-type]

        expected_turns = 2
        first_turn_messages = 0  # First turn has no history
        second_turn_messages = 2  # Second turn has 2 messages from first turn
        assert mock_agent.run_sync.call_count == expected_turns
        assert len(mock_agent.run_sync.call_args_list[0][1]["message_history"]) == first_turn_messages
        assert len(mock_agent.run_sync.call_args_list[1][1]["message_history"]) == second_turn_messages

    def test_handles_agent_error(self, mock_agent, mock_handler, db_path):  # type: ignore[no-untyped-def]
        """Test chat handles agent errors correctly."""
        mock_agent.run_sync.side_effect = RuntimeError("API error")

        handler = mock_handler(["Cause error"])
        with pytest.raises(RuntimeError, match="API error"):
            run_chat(handler, db_path)  # type: ignore[arg-type]

        assert "API error" in handler.errors[0]
