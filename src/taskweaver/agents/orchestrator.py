"""Orchestrator agent with delegation to specialized agents."""

import json
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from pydantic_ai import AgentRunResult, ModelMessage, RunContext

from taskweaver.config import Config

from ..config import get_config

if TYPE_CHECKING:
    from textual.worker import Worker

from ..database.completion_repository import CompletionRepository
from ..database.connection import mem0_memory
from ..database.dependency_repository import TaskDependencyRepository
from ..database.repository import TaskRepository
from .chat_handler import ChatHandler
from .dependencies import TaskDependencies
from .research import research_agent
from .shared import create_agent
from .task_management import task_agent


# Delegation tools for orchestrator
def delegate_to_task_agent(
    ctx: RunContext[TaskDependencies],
    user_request: str,
) -> str:
    """Delegate task management operations to TaskAgent.

    Use when user wants to:
    - Create, update, or search tasks
    - Manage dependencies between tasks
    - Mark tasks complete or cancelled
    - View task details or priorities

    Args:
        ctx: Runtime context with dependencies
        user_request: User's request for task operations

    Returns:
        TaskAgent response
    """
    result = task_agent.run_sync(
        user_request,
        deps=ctx.deps,
    )
    return result.output


def delegate_to_research_agent(
    ctx: RunContext[TaskDependencies],
    user_request: str,
) -> str:
    """Delegate research operations to ResearchAgent.

    Use when user wants to:
    - Search the web for information
    - Import GitHub issues
    - Research best practices or technologies

    Args:
        ctx: Runtime context with dependencies
        user_request: User's research request

    Returns:
        ResearchAgent response
    """
    result = research_agent.run_sync(
        user_request,
        deps=ctx.deps,
    )
    return result.output


# Orchestrator agent (lightweight - just routes to sub-agents)
orchestrator_agent = create_agent(
    prompt_name="orchestrator",
    tools=[
        delegate_to_task_agent,
        delegate_to_research_agent,
    ],
    deps_type=TaskDependencies,
)


@orchestrator_agent.system_prompt
def add_memories(ctx: RunContext[TaskDependencies]) -> str:
    """Load memory into sys prompt."""
    return f"\n## MEMORIES\n{ctx.deps.memories}"


def run_chat(handler: ChatHandler, db_path: Path, worker: "Worker | None" = None) -> None:
    """Run interactive chat loop with the orchestrator agent.

    Args:
        handler: ChatHandler implementation for I/O operations.
        db_path: Path to the task database for agent operations.
        worker: Optional worker for cancellation checking (TUI mode only).
    """
    logger.info(f"Starting chat session with database: {db_path}")
    handler.display_system_message(f"Current database path: {db_path}")
    message_history: list[ModelMessage] = []
    handler.display_system_message("🧵 TaskWeaver Chat - Type 'exit', 'quit', or Ctrl+C to end")

    # Create repository instances for agent tools
    task_repo = TaskRepository(db_path)
    dep_repo = TaskDependencyRepository(db_path)
    completion_repo = CompletionRepository(db_path)
    config: Config = get_config()

    # Initialize mem0 memory (optional - only if API key available)
    try:
        memory = mem0_memory(config)
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
        completion_repo=completion_repo,
        memories="",
        user_id="default",
    )

    turn_count = 0
    while True:
        # Check if worker was cancelled (TUI mode)
        if worker is not None and hasattr(worker, "is_cancelled") and worker.is_cancelled:
            logger.info("Chat loop cancelled by worker")
            break

        user_input = handler.get_user_input()
        command = False
        if user_input is None:
            logger.info(f"Chat session ended after {turn_count} turns")
            break
        if not (stripped_input := user_input.strip()):
            continue

        try:
            if stripped_input.startswith("/github"):
                # Pass to research agent via orchestrator
                stripped_input = "Import GitHub issues from configured repositories"
                command = True

            # Add user input to memory if available
            if memory is not None and not command:
                memory_added = memory.add(stripped_input, user_id=dependencies.user_id)
                logger.info(f"Memory added: {memory_added}")
                dependencies.memories = json.dumps(
                    memory.search(stripped_input, user_id=dependencies.user_id, limit=config.mem0_max_memories)
                )
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
