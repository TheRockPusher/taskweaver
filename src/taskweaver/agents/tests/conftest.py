"""Shared fixtures for agents tests."""

import os
from pathlib import Path
from unittest.mock import Mock

import pytest
from pydantic_ai import Agent

# Set dummy API keys BEFORE importing task_agent to prevent client initialization errors
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-for-testing")
os.environ.setdefault("OPENROUTER_API_KEY", "sk-or-test-dummy-key-for-testing")

from taskweaver.agents import task_agent
from taskweaver.database import connection


class MockChatHandler:
    """Mock ChatHandler for testing."""

    def __init__(self, inputs: list[str | None]) -> None:
        self.inputs = inputs
        self.input_index = 0
        self.system_messages: list[str] = []
        self.agent_messages: list[str] = []
        self.errors: list[str] = []

    def display_system_message(self, message: str) -> None:
        self.system_messages.append(message)

    def display_agent_message(self, message: str) -> None:
        self.agent_messages.append(message)

    def display_error(self, error: str) -> None:
        self.errors.append(error)

    def get_user_input(self, prompt: str = "") -> str | None:
        _ = prompt
        if self.input_index >= len(self.inputs):
            return None
        result = self.inputs[self.input_index]
        self.input_index += 1
        return result


@pytest.fixture
def mock_agent(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock orchestrator agent to avoid API calls.

    Patches the module-level orchestrator_agent instance following
    PydanticAI's recommended pattern of global agent instantiation.

    """
    agent = Mock(spec=Agent)
    monkeypatch.setattr(task_agent, "orchestrator_agent", agent)
    return agent


@pytest.fixture
def mock_mem0_memory(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Mock mem0_memory function to prevent API calls during tests.

    Returns None to simulate memory not being available, which is
    the graceful degradation path in production.

    """
    mock_memory_func = Mock(return_value=None)
    monkeypatch.setattr(connection, "mem0_memory", mock_memory_func)
    return mock_memory_func


@pytest.fixture
def mock_handler() -> type[MockChatHandler]:
    """Provide MockChatHandler class."""
    return MockChatHandler


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    """Provide temporary database path."""
    return tmp_path / "test.db"
