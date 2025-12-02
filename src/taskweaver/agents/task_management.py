"""Task management agent - handles all task domain operations."""

from .dependencies import TaskDependencies
from .shared import create_agent
from .tools import (
    # Dependencies (5 tools)
    add_dependency_tool,
    # Task CRUD (6 tools)
    create_task_tool,
    get_blocked_tool,
    get_blockers_tool,
    get_task_details_tool,
    list_open_tasks_full,
    list_tasks_tool,
    mark_task_cancelled_tool,
    # Completions (2 tools)
    mark_task_completed_tool,
    remove_dependency_tool,
    search_tasks_tool,
    update_task_status_tool,
    update_task_tool,
)

# All task-related tools
TASK_TOOLS = [
    # CRUD
    create_task_tool,
    update_task_tool,
    list_tasks_tool,
    search_tasks_tool,
    get_task_details_tool,
    update_task_status_tool,
    # Dependencies
    add_dependency_tool,
    remove_dependency_tool,
    get_blockers_tool,
    get_blocked_tool,
    list_open_tasks_full,
    # Completions
    mark_task_completed_tool,
    mark_task_cancelled_tool,
]

# Create TaskAgent using factory (composition!)
task_agent = create_agent(
    prompt_name="task",
    tools=TASK_TOOLS,
    deps_type=TaskDependencies,
)
