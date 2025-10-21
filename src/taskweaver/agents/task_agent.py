"""PydanticAI agent for task orchestration."""

from functools import lru_cache
from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, AgentRunResult, ModelMessage

from ..config import get_config
from ..database.dependency_repository import TaskDependencyRepository
from ..database.repository import TaskRepository
from .chat_handler import ChatHandler
from .dependencies import TaskDependencies
from .tools import (
    add_dependency_tool,
    create_task_tool,
    get_blocked_tool,
    get_blockers_tool,
    get_task_details_tool,
    list_open_tasks_dep_count_tool,
    list_tasks_tool,
    mark_task_cancelled_tool,
    mark_task_completed_tool,
    mark_task_in_progress_tool,
    remove_dependency_tool,
)

# Prompts directory
PROMPTS_DIR = Path(__file__).parent / "prompts"


def load_prompt(name: str) -> str:
    """Load prompt from markdown file.

    Args:
        name: Prompt filename without .md extension.

    Returns:
        Prompt content as string.

    Raises:
        FileNotFoundError: If prompt file doesn't exist.

    """
    prompt_path = PROMPTS_DIR / f"{name}.md"
    return prompt_path.read_text(encoding="utf-8")


@lru_cache
def get_orchestrator_agent() -> Agent[TaskDependencies, str]:
    """Get cached orchestrator agent instance.

    Lazy initialization ensures agent is only created when needed,
    avoiding import-time API key requirements for tests.

    Returns:
        Cached Agent instance with TaskDependencies and registered tools.

    """
    config = get_config()
    system_prompt = load_prompt("orchestrator_prompt")

    # Add provider prefix to model name (openai:gpt-4o-mini)
    model_name = config.model
    if ":" not in model_name:
        model_name = f"openai:{model_name}"

    agent: Agent[TaskDependencies, str] = Agent[TaskDependencies, str](
        model_name,
        deps_type=TaskDependencies,
        system_prompt=system_prompt,
    )

    # Register tools
    agent.tool(create_task_tool)
    agent.tool(list_tasks_tool)
    agent.tool(mark_task_completed_tool)
    agent.tool(mark_task_in_progress_tool)
    agent.tool(mark_task_cancelled_tool)
    agent.tool(get_task_details_tool)
    agent.tool(list_open_tasks_dep_count_tool)
    agent.tool(add_dependency_tool)
    agent.tool(remove_dependency_tool)
    agent.tool(get_blocked_tool)
    agent.tool(get_blockers_tool)

    return agent


def run_chat(handler: ChatHandler, db_path: Path) -> None:
    """Run interactive chat loop with the orchestrator agent.

    Args:
        handler: ChatHandler implementation for I/O operations.
        db_path: Path to the task database for agent operations.
    """
    logger.info(f"Starting chat session with database: {db_path}")
    handler.display_system_message(f"Current database path: {db_path}")
    message_history: list[ModelMessage] = []
    handler.display_system_message("🧵 TaskWeaver Chat - Type 'exit', 'quit', or Ctrl+C to end")

    # Get agent instance (lazy initialization)
    agent = get_orchestrator_agent()

    # Create both repository instances for agent tools
    task_repo = TaskRepository(db_path)
    dep_repo = TaskDependencyRepository(db_path)

    # Wrap repositories in dependencies container
    dependencies = TaskDependencies(task_repo=task_repo, dep_repo=dep_repo)

    turn_count = 0
    while True:
        user_input = handler.get_user_input()

        if user_input is None:
            logger.info(f"Chat session ended after {turn_count} turns")
            break
        if not user_input.strip():
            continue

        try:
            # Pass dependencies container to agent
            result: AgentRunResult[str] = agent.run_sync(
                user_input,
                message_history=message_history,
                deps=dependencies,
            )
            handler.display_agent_message(result.output)
            message_history = result.all_messages()
            turn_count += 1
        except Exception as e:
            logger.error(f"Chat error on turn {turn_count}: {e}")
            handler.display_error(str(e))
            raise
