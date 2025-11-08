"""Base class for specialist agents."""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.protocol import AgentResult

logger = logging.getLogger(__name__)


class BaseSpecialistAgent(ABC):
    """Base class for specialist agents.

    Provides common functionality for all specialist agents including:
    - Agent initialization with PydanticAI
    - Timing and logging
    - Result wrapping
    - Async execution support
    - System prompt loading

    Subclasses must implement:
    - name property
    - description property
    - capabilities property
    - can_handle() method
    - _execute() method
    """

    def __init__(self, model: str = "openai:gpt-4o-mini", system_prompt_path: Path | None = None):
        """Initialize base specialist agent.

        Args:
            model: PydanticAI model identifier
            system_prompt_path: Path to system prompt file (optional)
        """
        self.model = model
        self._system_prompt: str = ""

        # Load system prompt if provided
        if system_prompt_path and system_prompt_path.exists():
            self._system_prompt = system_prompt_path.read_text()
            logger.info(f"Loaded system prompt from {system_prompt_path}")

        # Create PydanticAI agent (subclasses can override)
        self._agent: Agent[TaskDependencies, str] | None = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name identifying this agent."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Description of what this agent does."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of capabilities/intents this agent can handle."""
        ...

    @abstractmethod
    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Determine if this agent can handle the request.

        Args:
            request: User request or prompt
            context: Optional context dictionary

        Returns:
            Confidence score (0-1) indicating ability to handle request
        """
        ...

    @abstractmethod
    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the agent logic.

        Subclasses implement their specific logic here.

        Args:
            prompt: User request or instruction
            deps: TaskDependencies container
            context: Optional shared context

        Returns:
            Result data dictionary

        Raises:
            Exception if execution fails
        """
        ...

    def run(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute the agent with the given prompt.

        Wraps _execute() with timing, logging, and error handling.

        Args:
            prompt: User request or instruction
            deps: TaskDependencies container
            context: Optional shared context

        Returns:
            AgentResult containing execution outcome
        """
        logger.info(f"[{self.name}] Starting execution")
        start_time = time.time()

        try:
            # Execute agent logic
            data = self._execute(prompt, deps, context or {})

            execution_time = (time.time() - start_time) * 1000  # Convert to ms
            logger.info(f"[{self.name}] Completed in {execution_time:.1f}ms")

            return AgentResult(
                success=True,
                data=data,
                agent_name=self.name,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            error_msg = f"Execution failed: {e!s}"
            logger.error(f"[{self.name}] {error_msg}", exc_info=True)

            return AgentResult(
                success=False,
                data={},
                error=error_msg,
                agent_name=self.name,
                execution_time_ms=execution_time,
            )

    async def run_async(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> AgentResult:
        """Async version of run() for parallel execution.

        Args:
            prompt: User request or instruction
            deps: TaskDependencies container
            context: Optional shared context

        Returns:
            AgentResult containing execution outcome
        """
        # Run synchronous _execute() in thread pool
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.run, prompt, deps, context)

    def _keyword_match_score(self, request: str, keywords: list[str]) -> float:
        """Calculate keyword match score.

        Helper method for can_handle() implementations.

        Args:
            request: User request
            keywords: Keywords to match

        Returns:
            Score (0-1) based on keyword matches
        """
        if not keywords:
            return 0.0

        request_lower = request.lower()
        matches = sum(1 for kw in keywords if kw.lower() in request_lower)

        # Return normalized score
        return min(matches / len(keywords), 1.0)

    def _load_system_prompt(self, prompt_path: Path) -> str:
        """Load system prompt from file.

        Args:
            prompt_path: Path to prompt file

        Returns:
            Prompt text

        Raises:
            FileNotFoundError if prompt doesn't exist
        """
        if not prompt_path.exists():
            raise FileNotFoundError(f"System prompt not found: {prompt_path}")

        return prompt_path.read_text()

    def __str__(self) -> str:
        """String representation."""
        return f"{self.name} (model: {self.model})"

    def __repr__(self) -> str:
        """Developer representation."""
        return f"{self.__class__.__name__}(name='{self.name}', model='{self.model}')"
