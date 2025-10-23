"""PydanticAI agent for task orchestration."""

import json
from pathlib import Path

from loguru import logger
from pydantic_ai import Agent, AgentRunResult, FunctionToolset, ModelMessage, RunContext
from pydantic_ai.common_tools.duckduckgo import duckduckgo_search_tool

from taskweaver.config import Config

from ..config import get_config
from ..database.connection import mem0_memory
from ..database.dependency_repository import TaskDependencyRepository
from ..database.repository import TaskRepository
from .chat_handler import ChatHandler
from .dependencies import TaskDependencies
from .github_issues import get_github_issues
from .tools import (
    add_dependency_tool,
    create_task_tool,
    get_blocked_tool,
    get_blockers_tool,
    get_task_details_tool,
    list_open_tasks_full,
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


# Prepare model name with provider prefix
def _get_model_name() -> str:
    """Get model name with provider prefix for agent initialization.

    Returns:
        Model name with provider prefix (e.g., 'openai:gpt-4o-mini').

    """
    config: Config = get_config()
    model_name = config.model
    if ":" not in model_name:
        model_name = f"openai:{model_name}"
    return model_name


# Toolset 1: Task Management CRUD
_task_toolset = FunctionToolset(
    tools=[
        create_task_tool,
        list_tasks_tool,
        get_task_details_tool,
        mark_task_completed_tool,
        mark_task_in_progress_tool,
        mark_task_cancelled_tool,
    ]
)

# Toolset 2: Dependency Management DAG
_dependency_toolset = FunctionToolset(
    tools=[
        list_open_tasks_full,
        add_dependency_tool,
        remove_dependency_tool,
        get_blockers_tool,
        get_blocked_tool,
    ]
)

# Module-level agent instance (PydanticAI recommended pattern)
# Instantiated once and reused throughout the application, similar to FastAPI.
# defer_model_check=True prevents API key validation at import time (enables testing)
orchestrator_agent: Agent[TaskDependencies, str] = Agent[TaskDependencies, str](
    _get_model_name(),
    deps_type=TaskDependencies,
    system_prompt=load_prompt("orchestrator_prompt"),
    tools=[duckduckgo_search_tool()],
    toolsets=[_task_toolset, _dependency_toolset],
    defer_model_check=True,
)


@orchestrator_agent.system_prompt
def add_memories(ctx: RunContext[TaskDependencies]) -> str:
    """Load memory into sys prompt."""
    return f"\n## MEMORIES\n{ctx.deps.memories}"


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

    # Create repository instances for agent tools
    task_repo = TaskRepository(db_path)
    dep_repo = TaskDependencyRepository(db_path)

    # Initialize mem0 memory (optional - only if API key available)
    try:
        memory = mem0_memory()
        logger.info("Mem0 memory initialized successfully")
    except (KeyError, RuntimeError) as e:
        # KeyError: Missing API keys (OPENROUTER_API_KEY)
        # RuntimeError: Qdrant file locking issues in CI/CD
        logger.error(f"Mem0 memory not available: {e}")
        memory = None

    # Wrap repositories and memory in dependencies container
    dependencies = TaskDependencies(
        task_repo=task_repo,
        dep_repo=dep_repo,
        memories="",
        user_id="default",
    )

    turn_count = 0
    while True:
        user_input = handler.get_user_input()

        if user_input is None:
            logger.info(f"Chat session ended after {turn_count} turns")
            break
        if not (stripped_input := user_input.strip()):
            continue
        if stripped_input.startswith("/github"):
            config: Config = get_config()
            stripped_input += f"Open Issues: {
                json.dumps(
                    get_github_issues(config.github_repo),
                    indent=2,
                    default=str,  # Handles datetime, UUID, etc.
                )
            }"

        try:
            # Use module-level agent instance (PydanticAI recommended pattern)

            # Add user input to memory if available
            if memory is not None:
                memory_added = memory.add(stripped_input, user_id=dependencies.user_id)
                logger.info(f"Memory added: {memory_added}")
                dependencies.memories = json.dumps(memory.search(stripped_input, user_id=dependencies.user_id))
                logger.info(f"Retrieved memories:{dependencies.memories}")

            result: AgentRunResult[str] = orchestrator_agent.run_sync(
                stripped_input,
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
