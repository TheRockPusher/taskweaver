"""Tests for shared utilities."""

from pathlib import Path

import pytest

import taskweaver.agents.shared as shared_module
from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.shared import create_agent, get_model_name, load_prompt


class TestLoadPrompt:
    """Tests for load_prompt function."""

    def test_load_existing_prompt(self) -> None:
        """Test loading an existing prompt file."""
        # orchestrator.md should exist after Phase 4
        content = load_prompt("orchestrator.md")
        assert "TaskWeaver" in content

    def test_load_nonexistent_prompt(self) -> None:
        """Test loading a non-existent prompt raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_prompt("nonexistent.md")


class TestGetModelName:
    """Tests for get_model_name function."""

    def test_returns_prefixed_model(self) -> None:
        """Test model name has provider prefix."""
        model_name = get_model_name()
        assert ":" in model_name


class TestCreateAgent:
    """Tests for create_agent factory function."""

    def test_creates_agent_with_tools(self, tmp_path: Path) -> None:
        """Test agent creation with tools."""
        # Create temp prompt
        prompts_dir = tmp_path / "prompts"
        prompts_dir.mkdir()
        (prompts_dir / "test.md").write_text("Test prompt")

        # Patch PROMPTS_DIR
        original = shared_module.PROMPTS_DIR
        shared_module.PROMPTS_DIR = prompts_dir

        try:

            def dummy_tool() -> str:
                return "test"

            agent = create_agent("test", [dummy_tool], TaskDependencies)
            assert agent is not None
        finally:
            shared_module.PROMPTS_DIR = original
