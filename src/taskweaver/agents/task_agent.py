"""PydanticAI agent for task orchestration."""

from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, AgentRunResult, ModelMessage

from ..config import Config, get_config
from ..database.repository import TaskRepository
from .chat_handler import ChatHandler
from .tools import (
    create_task_tool,
    get_task_details_tool,
    list_tasks_tool,
    mark_task_cancelled_tool,
    mark_task_completed_tool,
    mark_task_in_progress_tool,
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


# Load system prompt
system_prompt = load_prompt("orchestrator_prompt")

# Initialize agent with TaskRepository as dependencies
config: Config = get_config()
orchestrator_agent: Agent[TaskRepository, str] = Agent[TaskRepository, str](
    config.model,
    deps_type=TaskRepository,
    system_prompt=system_prompt,
)

# Register tools
orchestrator_agent.tool(create_task_tool)
orchestrator_agent.tool(list_tasks_tool)
orchestrator_agent.tool(mark_task_completed_tool)
orchestrator_agent.tool(mark_task_in_progress_tool)
orchestrator_agent.tool(mark_task_cancelled_tool)
orchestrator_agent.tool(get_task_details_tool)


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

    # Create repository instance for agent tools
    repository = TaskRepository(db_path)

    turn_count = 0
    while True:
        user_input = handler.get_user_input()

        if user_input is None:
            logger.info(f"Chat session ended after {turn_count} turns")
            break
        if not user_input.strip():
            continue

        try:
            # Pass repository as dependencies to agent
            result: AgentRunResult[str] = orchestrator_agent.run_sync(
                user_input,
                message_history=message_history,
                deps=repository,
            )
            handler.display_agent_message(result.output)
            message_history = result.all_messages()
            turn_count += 1
        except Exception as e:
            logger.error(f"Chat error on turn {turn_count}: {e}")
            handler.display_error(str(e))
            raise
