"""Protocol definitions for the multi-agent system."""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID, uuid4

from taskweaver.agents.dependencies import TaskDependencies


@dataclass
class AgentResult:
    """Result from a specialist agent execution.

    Attributes:
        success: Whether the agent execution succeeded
        data: Result data (structure depends on agent type)
        error: Error message if failed
        agent_name: Name of the agent that produced this result
        execution_time_ms: Time taken to execute in milliseconds
        confidence: Confidence score (0-1) if applicable
        metadata: Additional metadata about execution
    """

    success: bool
    data: dict[str, Any]
    error: str | None = None
    agent_name: str = ""
    execution_time_ms: float = 0.0
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)
    execution_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        """String representation of result."""
        status = "SUCCESS" if self.success else "FAILED"
        time_str = f"{self.execution_time_ms:.1f}ms"
        return f"[{self.agent_name}] {status} ({time_str})"


class SpecialistAgent(Protocol):
    """Protocol for specialist agents in the multi-agent system.

    All specialist agents must implement this protocol to be registered
    and coordinated by the MultiAgentCoordinator.
    """

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
            Confidence score (0-1) indicating ability to handle request.
            0 = cannot handle, 1 = perfect match
        """
        ...

    @abstractmethod
    def run(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> AgentResult:
        """Execute the agent with the given prompt.

        Args:
            prompt: User request or instruction
            deps: TaskDependencies container with repositories and memory
            context: Optional shared context from other agents

        Returns:
            AgentResult containing execution outcome
        """
        ...

    @abstractmethod
    async def run_async(
        self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None
    ) -> AgentResult:
        """Async version of run() for parallel execution.

        Args:
            prompt: User request or instruction
            deps: TaskDependencies container with repositories and memory
            context: Optional shared context from other agents

        Returns:
            AgentResult containing execution outcome
        """
        ...


@dataclass
class AgentCapability:
    """Definition of an agent capability.

    Attributes:
        name: Capability identifier (e.g., "task_decomposition")
        description: What this capability does
        keywords: Keywords that trigger this capability
        priority: Priority when multiple agents match (higher = preferred)
    """

    name: str
    description: str
    keywords: list[str] = field(default_factory=list)
    priority: int = 0


class AgentCoordinator(Protocol):
    """Protocol for agent coordinators.

    Coordinators route requests to appropriate specialist agents,
    manage agent lifecycle, and aggregate results.
    """

    @abstractmethod
    def route_request(self, request: str, deps: TaskDependencies) -> list[SpecialistAgent]:
        """Route a request to appropriate specialist agent(s).

        Args:
            request: User request
            deps: Task dependencies

        Returns:
            List of specialist agents to handle the request (in execution order)
        """
        ...

    @abstractmethod
    def execute_workflow(
        self, agents: list[SpecialistAgent], prompt: str, deps: TaskDependencies
    ) -> list[AgentResult]:
        """Execute a workflow of agents sequentially.

        Args:
            agents: Ordered list of agents to execute
            prompt: User prompt
            deps: Task dependencies

        Returns:
            List of results from each agent
        """
        ...

    @abstractmethod
    async def execute_parallel(
        self, agents: list[SpecialistAgent], prompt: str, deps: TaskDependencies
    ) -> list[AgentResult]:
        """Execute multiple agents in parallel.

        Args:
            agents: List of agents to execute concurrently
            prompt: User prompt
            deps: Task dependencies

        Returns:
            List of results from each agent
        """
        ...
