"""Tests for TaskAgent."""

from taskweaver.agents.task_management import TASK_TOOLS, task_agent


class TestTaskAgent:
    """Tests for TaskAgent configuration."""

    def test_task_agent_exists(self) -> None:
        """Test TaskAgent instance is created."""
        assert task_agent is not None

    def test_task_agent_has_14_tools(self) -> None:
        """Test TaskAgent has all 14 task-related tools."""
        assert len(TASK_TOOLS) == 14

    def test_task_tools_list_complete(self) -> None:
        """Test TASK_TOOLS contains expected tool names."""
        tool_names = [tool.__name__ for tool in TASK_TOOLS]

        # CRUD (6 tools)
        assert "create_task_tool" in tool_names
        assert "update_task_tool" in tool_names
        assert "list_tasks_tool" in tool_names
        assert "search_tasks_tool" in tool_names
        assert "get_task_details_tool" in tool_names
        assert "update_task_status_tool" in tool_names

        # Dependencies (5 tools)
        assert "add_dependency_tool" in tool_names
        assert "remove_dependency_tool" in tool_names
        assert "get_blockers_tool" in tool_names
        assert "get_blocked_tool" in tool_names
        assert "list_open_tasks_full" in tool_names

        # Completions (2 tools)
        assert "mark_task_completed_tool" in tool_names
        assert "mark_task_cancelled_tool" in tool_names

        # Utilities (1 tool)
        assert "calculator_tool" in tool_names
