"""Tests for ResearchAgent."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from pydantic_ai import RunContext

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.research import RESEARCH_TOOLS, github_import_tool, research_agent
from taskweaver.database.completion_repository import CompletionRepository
from taskweaver.database.dependency_repository import TaskDependencyRepository
from taskweaver.database.repository import TaskRepository


class TestResearchAgent:
    """Tests for ResearchAgent configuration."""

    def test_research_agent_exists(self) -> None:
        """Test ResearchAgent instance is created."""
        assert research_agent is not None

    def test_research_agent_has_2_tools(self) -> None:
        """Test ResearchAgent has 2 tools (web search + GitHub)."""
        assert len(RESEARCH_TOOLS) == 2

    def test_github_import_tool_exists(self) -> None:
        """Test github_import_tool is defined."""
        assert github_import_tool is not None
        assert callable(github_import_tool)


class TestGitHubImportTool:
    """Tests for github_import_tool function."""

    @pytest.fixture
    def mock_ctx(self, tmp_path: Path) -> Mock:
        """Create mock RunContext."""
        db_path = tmp_path / "test.db"
        deps = TaskDependencies(
            task_repo=TaskRepository(db_path),
            dep_repo=TaskDependencyRepository(db_path),
            completion_repo=CompletionRepository(db_path),
            memories="",
            user_id="test",
        )
        ctx = Mock(spec=RunContext)
        ctx.deps = deps
        return ctx

    @patch("taskweaver.agents.research.get_config")
    def test_github_import_tool_no_repos_configured(self, mock_get_config: Mock, mock_ctx: Mock) -> None:
        """Test github_import_tool when no repos are configured."""
        mock_config = Mock()
        mock_config.github_repos = []
        mock_get_config.return_value = mock_config

        result = github_import_tool(mock_ctx)

        assert "No GitHub repositories configured" in result

    @patch("taskweaver.agents.research.get_github_issues")
    @patch("taskweaver.agents.research.get_config")
    def test_github_import_tool_no_issues_found(
        self, mock_get_config: Mock, mock_get_issues: Mock, mock_ctx: Mock
    ) -> None:
        """Test github_import_tool when no issues are found."""
        mock_config = Mock()
        mock_config.github_repos = ["owner/repo"]
        mock_get_config.return_value = mock_config
        mock_get_issues.return_value = []

        result = github_import_tool(mock_ctx)

        assert "No open issues found" in result

    @patch("taskweaver.agents.research.get_github_issues")
    @patch("taskweaver.agents.research.get_config")
    def test_github_import_tool_returns_issues_json(
        self, mock_get_config: Mock, mock_get_issues: Mock, mock_ctx: Mock
    ) -> None:
        """Test github_import_tool returns JSON when issues are found."""
        mock_config = Mock()
        mock_config.github_repos = ["owner/repo"]
        mock_get_config.return_value = mock_config
        mock_issues = [
            {"number": 1, "title": "Test issue", "state": "open"},
            {"number": 2, "title": "Another issue", "state": "open"},
        ]
        mock_get_issues.return_value = mock_issues

        result = github_import_tool(mock_ctx)

        assert '"number": 1' in result
        assert '"title": "Test issue"' in result
        assert '"number": 2' in result
