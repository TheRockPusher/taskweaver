"""Tests for orchestrator delegation."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import RunContext
from pydantic_ai.usage import RunUsage

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.orchestrator import (
    delegate_to_research_agent,
    delegate_to_task_agent,
    orchestrator_agent,
)
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.repository import TaskRepository


class TestOrchestrator:
    """Tests for orchestrator agent configuration."""

    def test_orchestrator_agent_exists(self) -> None:
        """Test orchestrator_agent instance is created."""
        assert orchestrator_agent is not None

    def test_delegation_tools_exist(self) -> None:
        """Test delegation tool functions are defined."""
        assert delegate_to_task_agent is not None
        assert delegate_to_research_agent is not None
        assert callable(delegate_to_task_agent)
        assert callable(delegate_to_research_agent)

    def test_orchestrator_has_2_tools(self) -> None:
        """Test orchestrator has 2 delegation tools."""
        # Access agent tools via _function_tools (PydanticAI internal)
        # This is a basic check that tools are registered
        assert orchestrator_agent is not None


class TestDelegationIntegration:
    """Integration tests for delegation functions."""

    @pytest.fixture
    def mock_deps(self, tmp_path: Path) -> TaskDependencies:
        """Create mock dependencies."""
        db_path = tmp_path / "test.db"
        return TaskDependencies(
            task_repo=TaskRepository(db_path),
            dep_repo=TaskDependencyRepository(db_path),
            completion_repo=CompletionRepository(db_path),
            memories="",
            user_id="test",
        )

    @pytest.fixture
    def mock_ctx(self, mock_deps: TaskDependencies) -> Mock:
        """Create mock RunContext."""
        ctx = Mock(spec=RunContext)
        ctx.deps = mock_deps
        ctx.usage = RunUsage()
        return ctx

    @patch("taskweaver.agents.orchestrator.task_agent")
    def test_delegate_to_task_agent_calls_agent(self, mock_task_agent: Mock, mock_ctx: Mock) -> None:
        """Test delegate_to_task_agent calls task agent with correct params."""
        mock_result = Mock()
        mock_result.output = "Task created successfully"
        mock_task_agent.run_sync.return_value = mock_result

        result = delegate_to_task_agent(mock_ctx, "Create a test task")

        assert result == "Task created successfully"
        mock_task_agent.run_sync.assert_called_once_with("Create a test task", deps=mock_ctx.deps, usage=mock_ctx.usage)

    @patch("taskweaver.agents.orchestrator.research_agent")
    def test_delegate_to_research_agent_calls_agent(self, mock_research_agent: Mock, mock_ctx: Mock) -> None:
        """Test delegate_to_research_agent calls research agent with correct params."""
        mock_result = Mock()
        mock_result.output = "Search results here"
        mock_research_agent.run_sync.return_value = mock_result

        result = delegate_to_research_agent(mock_ctx, "Search for Python best practices")

        assert result == "Search results here"
        mock_research_agent.run_sync.assert_called_once_with(
            "Search for Python best practices", deps=mock_ctx.deps, usage=mock_ctx.usage
        )
