"""Conversation orchestration with local commands and invocation-scoped context."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

from pydantic_ai import AgentRunResult, ModelMessage, RunContext
from pydantic_ai.exceptions import AgentRunError

from ..config import get_config
from ..database.completion_repository import CompletionRepository
from ..database.connection import close_mem0_memory, mem0_memory
from ..database.dependency_repository import TaskDependencyRepository
from ..database.planning import PlanningService
from ..database.repository import TaskRepository
from .chat_handler import AsyncChatHandler, ChatHandler, ChatOutput
from .commands import CommandError, CommandResult, parse_command, process_command
from .dependencies import TaskDependencies
from .memory import BACKEND_OPERATION_ERRORS, MemoryService, SemanticBackend
from .research import research_agent
from .semantic_worker import SemanticWorker
from .shared import close_model, create_agent, get_model, load_prompt
from .task_management import task_agent

if TYPE_CHECKING:
    from mem0 import Memory


class CancellationState(Protocol):
    """Cancellation flag consumed by chat, independent of the UI framework."""

    @property
    def is_cancelled(self) -> bool:
        """Whether the owning worker has requested cancellation."""
        ...


def _request_context(deps: TaskDependencies) -> str:
    """Recomputed each run; never freeze memory or modes into conversation history."""
    return "\n\n".join(part for part in (deps.request_instructions, deps.memories) if part)


async def delegate_to_task_agent(ctx: RunContext[TaskDependencies], user_request: str) -> str:
    """Delegate persisted task/planning work with this turn's model and context."""
    instructions = load_prompt("task.md") + "\n\n" + _request_context(ctx.deps)
    with task_agent.override(instructions=instructions):
        result = await task_agent.run(user_request, deps=ctx.deps, model=ctx.model, usage=ctx.usage)
        return result.output


async def delegate_to_research_agent(ctx: RunContext[TaskDependencies], user_request: str) -> str:
    """Delegate research with the same fresh provider and scoped instructions."""
    instructions = load_prompt("research.md") + "\n\n" + _request_context(ctx.deps)
    with research_agent.override(instructions=instructions):
        result = await research_agent.run(user_request, deps=ctx.deps, model=ctx.model, usage=ctx.usage)
        return result.output


orchestrator_agent = create_agent(
    prompt_name="orchestrator",
    tools=[delegate_to_task_agent, delegate_to_research_agent],
    deps_type=TaskDependencies,
)


@orchestrator_agent.instructions
def request_instructions(ctx: RunContext[TaskDependencies]) -> str:
    """Append fresh request data to the immutable base instructions."""
    return _request_context(ctx.deps)


class _ObservedMemoryBackend:
    """Report real semantic failures without exposing private facts or credentials."""

    def __init__(self, backend: SemanticBackend, handler: ChatOutput) -> None:
        self.backend = backend
        self.handler = handler
        self.reported = False

    def _call(self, operation: Callable[[], object]) -> object:
        try:
            return operation()
        except BACKEND_OPERATION_ERRORS as exc:
            if not self.reported:
                self.handler.display_error(
                    f"Semantic memory unavailable ({type(exc).__name__}). Local facts remain available. "
                    "Check the configured embedding endpoint/API key or disable memory_enabled."
                )
                self.reported = True
            raise

    def add(self, value: str, *, user_id: str, metadata: dict[str, object], infer: bool) -> object:
        return self._call(lambda: self.backend.add(value, user_id=user_id, metadata=metadata, infer=infer))

    def delete(self, identifier: str) -> object:
        return self._call(lambda: self.backend.delete(identifier))

    def get_all(self, *, user_id: str) -> object:
        return self._call(lambda: self.backend.get_all(user_id=user_id))

    def search(self, query: str, *, user_id: str, limit: int) -> object:
        return self._call(lambda: self.backend.search(query, user_id=user_id, limit=limit))


@dataclass
class _ChatSession:
    """Per-conversation dependencies and owned semantic transport."""

    dependencies: TaskDependencies
    handler: ChatOutput
    semantic_worker: SemanticWorker | None


async def _run_ai_turn(
    text: str,
    command: CommandResult | None,
    session: _ChatSession,
    history: list[ModelMessage],
) -> AgentRunResult[str] | None:
    """Run one scoped request, closing its fresh provider on every exit."""
    dependencies = session.dependencies
    handler = session.handler
    semantic_worker = session.semantic_worker
    try:
        model = get_model()
    except (*BACKEND_OPERATION_ERRORS, ValueError, RuntimeError) as exc:
        handler.display_error(
            f"AI provider configuration unavailable ({type(exc).__name__}). Run taskweaver setup "
            "or check the selected model, API key and endpoint. Local /help and /focus still work."
        )
        return None
    try:
        memory = dependencies.memory or MemoryService(dependencies.task_repo.db_path, dependencies.user_id)
        if semantic_worker is None:
            memories = memory.retrieval_context(text, limit=get_config().mem0_max_memories)
        else:
            memories = await semantic_worker.run(
                lambda: memory.retrieval_context(text, limit=get_config().mem0_max_memories)
            )
        request_deps = replace(
            dependencies,
            request_mode=command.mode if command is not None else None,
            request_instructions=command.instructions if command is not None else "",
            memories=memories,
        )
        prompt = command.prompt if command is not None and command.prompt is not None else text
        return await orchestrator_agent.run(prompt, message_history=history, deps=request_deps, model=model)
    except (*BACKEND_OPERATION_ERRORS, AgentRunError) as exc:
        handler.display_error(
            f"AI request failed ({type(exc).__name__}). Check provider availability, API key and endpoint, "
            "then retry. No response was generated; the chat session is still open."
        )
        return None
    finally:
        try:
            await close_model(model)
        except BACKEND_OPERATION_ERRORS as exc:
            handler.display_error(
                f"AI provider cleanup failed ({type(exc).__name__}). "
                "Close the session before requesting another response."
            )


def _dispatch_command(
    text: str,
    dependencies: TaskDependencies,
    handler: ChatOutput,
) -> tuple[bool, CommandResult | None]:
    """Handle local replies and failures before allowing an AI-backed command."""
    try:
        command = parse_command(text)
        result = process_command(command, dependencies, get_config()) if command else None
    except CommandError as exc:
        handler.display_error(str(exc))
        return True, None
    except (*BACKEND_OPERATION_ERRORS, RuntimeError) as exc:
        handler.display_error(
            f"Command failed ({type(exc).__name__}). Check network access and service credentials, then retry."
        )
        return True, None
    if result is not None and result.message is not None:
        handler.display_agent_message(result.message)
        return True, result
    return False, result


def run_chat(handler: ChatHandler, db_path: Path, worker: CancellationState | None = None) -> None:
    """Run synchronous CLI input with one event loop for the entire conversation."""

    async def read_input() -> str | None:
        return handler.get_user_input()

    # Runner.run installs a SIGINT handler that cannot interrupt blocking terminal
    # input. Drive its public loop directly to preserve CliChatHandler's Ctrl+C.
    with asyncio.Runner() as runner:
        runner.get_loop().run_until_complete(_run_chat(handler, db_path, read_input, worker))


async def run_chat_async(handler: AsyncChatHandler, db_path: Path, worker: CancellationState | None = None) -> None:
    """Run TUI input/model requests on its loop, isolating synchronous semantic work."""
    await _run_chat(handler, db_path, handler.get_user_input, worker, async_memory=True)


async def _open_memory_backend(
    handler: ChatOutput, db_path: Path, *, async_memory: bool
) -> tuple[SemanticBackend | None, SemanticWorker | None]:
    """Start only enabled semantic storage; preserve local-only startup on failure."""
    config = get_config()
    if not config.memory_enabled:
        return None, None
    config = config.model_copy(update={"database_file": db_path})
    try:
        if async_memory:
            worker = await SemanticWorker.open(config)
            return worker, worker
        return mem0_memory(config), None
    except (*BACKEND_OPERATION_ERRORS, RuntimeError, ImportError) as exc:
        handler.display_error(
            f"Semantic memory could not start ({type(exc).__name__}). Local facts remain available. "
            "Install the memory extra and check memory provider/embedding settings, or disable memory_enabled."
        )
        return None, None


async def _close_memory_backend(
    backend: SemanticBackend | None, semantic_worker: SemanticWorker | None, handler: ChatOutput
) -> None:
    """Release this session's storage without hiding programming errors."""
    if backend is None:
        return
    try:
        if semantic_worker is not None:
            await semantic_worker.close()
        else:
            close_mem0_memory(cast("Memory", backend))
    except BACKEND_OPERATION_ERRORS as exc:
        handler.display_error(
            f"Semantic memory cleanup failed ({type(exc).__name__}). Close the session before reopening its storage."
        )


async def _run_chat(
    handler: ChatOutput,
    db_path: Path,
    read_input: Callable[[], Awaitable[str | None]],
    worker: CancellationState | None,
    *,
    async_memory: bool = False,
) -> None:
    """Share local commands, scoped context and history across both interfaces.

    Local commands never resolve a model. Optional semantic storage is owned by this
    session and closed on every exit, including cancellation and exceptions.
    Failed AI turns leave successful history intact and allow the next turn.
    Async chat cancels owned semantic SDK work by terminating its subprocess.
    """
    handler.display_system_message(f"Current database path: {db_path}")
    handler.display_system_message("TaskWeaver Chat — /help for commands; exit or quit to end")
    config = get_config()
    backend = None
    semantic_worker = None
    try:
        backend, semantic_worker = await _open_memory_backend(handler, db_path, async_memory=async_memory)
        memory = MemoryService(
            db_path,
            user_id=config.user_id,
            semantic_backend=_ObservedMemoryBackend(backend, handler) if backend is not None else None,
        )
        dependencies = TaskDependencies(
            task_repo=TaskRepository(db_path),
            dep_repo=TaskDependencyRepository(db_path),
            completion_repo=CompletionRepository(db_path),
            memories="",
            user_id=config.user_id,
            planning=PlanningService(db_path),
            memory=memory,
        )
        session = _ChatSession(dependencies, handler, semantic_worker)
        message_history: list[ModelMessage] = []
        while worker is None or not worker.is_cancelled:
            user_input = await read_input()
            if user_input is None or (worker is not None and worker.is_cancelled):
                break
            stripped_input = user_input.strip()
            if not stripped_input:
                continue
            if stripped_input.casefold() in {"exit", "quit", "bye"}:
                break
            command_name = stripped_input.split(maxsplit=1)[0].casefold()
            if semantic_worker is not None and command_name in {"/remember", "/forget"}:
                handled, result = await semantic_worker.run(
                    partial(_dispatch_command, stripped_input, dependencies, handler)
                )
            else:
                handled, result = _dispatch_command(stripped_input, dependencies, handler)
            if handled:
                continue
            response = await _run_ai_turn(stripped_input, result, session, message_history)
            if response is None:
                continue
            if worker is not None and worker.is_cancelled:
                break
            handler.display_agent_message(response.output)
            message_history = response.all_messages()
    finally:
        await _close_memory_backend(backend, semantic_worker, handler)
