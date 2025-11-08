"""Multi-agent coordinator for TaskWeaver.

The coordinator routes user requests to appropriate specialist agents,
manages agent execution (sequential or parallel), and aggregates results.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.message import MessageBus
from taskweaver.agents.multi_agent.protocol import AgentResult, SpecialistAgent
from taskweaver.agents.multi_agent.registry import AgentRegistry

logger = logging.getLogger(__name__)


@dataclass
class CoordinatorConfig:
    """Configuration for multi-agent coordinator.

    Attributes:
        enabled: Whether multi-agent system is enabled
        parallel_execution: Allow parallel agent execution
        max_parallel_agents: Maximum number of agents to run in parallel
        fallback_to_general: Use general agent if specialist fails
        message_timeout_seconds: Timeout for agent messages
        min_confidence: Minimum confidence to route to specialist
        max_workflow_steps: Maximum steps in a workflow
    """

    enabled: bool = True
    parallel_execution: bool = True
    max_parallel_agents: int = 3
    fallback_to_general: bool = True
    message_timeout_seconds: int = 30
    min_confidence: float = 0.3
    max_workflow_steps: int = 10


@dataclass
class WorkflowResult:
    """Result from executing a workflow of agents.

    Attributes:
        success: Whether workflow completed successfully
        results: Results from each agent in execution order
        agents_invoked: Names of agents that were invoked
        total_time_ms: Total execution time in milliseconds
        parallel: Whether agents were executed in parallel
        errors: List of errors encountered
    """

    success: bool
    results: list[AgentResult]
    agents_invoked: list[str]
    total_time_ms: float
    parallel: bool = False
    errors: list[str] = field(default_factory=list)

    @property
    def final_result(self) -> AgentResult | None:
        """Get the final result from workflow."""
        return self.results[-1] if self.results else None


@dataclass
class MultiAgentCoordinator:
    """Coordinator for multi-agent system.

    Routes user requests to specialist agents, orchestrates execution,
    and aggregates results. Supports sequential and parallel execution.

    Attributes:
        registry: Agent registry for discovering specialists
        config: Coordinator configuration
        message_bus: Message bus for inter-agent communication
    """

    registry: AgentRegistry
    config: CoordinatorConfig = field(default_factory=CoordinatorConfig)
    message_bus: MessageBus = field(default_factory=MessageBus)

    def route_request(self, request: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> list[SpecialistAgent]:
        """Route a request to appropriate specialist agent(s).

        Uses intent classification to determine which agent(s) should handle
        the request. Returns a list of agents in execution order.

        Args:
            request: User request or prompt
            deps: Task dependencies
            context: Optional context dictionary

        Returns:
            List of specialist agents to execute (in order)
        """
        if not self.config.enabled:
            logger.info("Multi-agent system disabled, no routing")
            return []

        # Find best matching agent
        best_agent = self.registry.find_best_agent(request, context, self.config.min_confidence)

        if best_agent:
            logger.info(f"Routed request to: {best_agent.name}")
            return [best_agent]

        logger.info("No specialist agent matched request")
        return []

    def route_to_workflow(self, request: str, deps: TaskDependencies) -> list[SpecialistAgent]:
        """Route a complex request to a workflow of agents.

        Analyzes request to determine if it requires multiple agents
        to execute in sequence.

        Args:
            request: User request
            deps: Task dependencies

        Returns:
            List of agents forming a workflow
        """
        workflow: list[SpecialistAgent] = []

        # Check for multi-step patterns
        request_lower = request.lower()

        # Pattern: "Create and prioritize tasks"
        if any(word in request_lower for word in ["create", "add", "break down"]) and any(
            word in request_lower for word in ["prioritize", "priority", "rank"]
        ):
            decomposer = self.registry.get("TaskDecomposerAgent")
            priority_calc = self.registry.get("PriorityCalculatorAgent")
            if decomposer and priority_calc:
                workflow = [decomposer, priority_calc]
                logger.info("Routed to workflow: TaskDecomposer → PriorityCalculator")

        # Pattern: "Analyze dependencies and find blockers"
        elif "dependency" in request_lower or "blocker" in request_lower:
            dep_analyzer = self.registry.get("DependencyAnalyzerAgent")
            if dep_analyzer:
                workflow = [dep_analyzer]
                logger.info("Routed to workflow: DependencyAnalyzer")

        # Pattern: "Create tasks and estimate duration"
        elif any(word in request_lower for word in ["create", "add"]) and any(
            word in request_lower for word in ["estimate", "duration", "how long"]
        ):
            decomposer = self.registry.get("TaskDecomposerAgent")
            estimator = self.registry.get("EstimationAgent")
            if decomposer and estimator:
                workflow = [decomposer, estimator]
                logger.info("Routed to workflow: TaskDecomposer → Estimator")

        return workflow

    def execute_workflow(self, agents: list[SpecialistAgent], prompt: str, deps: TaskDependencies) -> WorkflowResult:
        """Execute a workflow of agents sequentially.

        Each agent executes in order, with results passed as context
        to subsequent agents.

        Args:
            agents: Ordered list of agents to execute
            prompt: User prompt
            deps: Task dependencies

        Returns:
            WorkflowResult containing all agent results
        """
        if not agents:
            return WorkflowResult(success=False, results=[], agents_invoked=[], total_time_ms=0.0, errors=["No agents to execute"])

        start_time = time.time()
        results: list[AgentResult] = []
        context: dict[str, Any] = {}
        agents_invoked: list[str] = []
        errors: list[str] = []

        for i, agent in enumerate(agents):
            if i >= self.config.max_workflow_steps:
                errors.append(f"Exceeded max workflow steps ({self.config.max_workflow_steps})")
                break

            try:
                logger.info(f"Executing agent {i + 1}/{len(agents)}: {agent.name}")
                result = agent.run(prompt, deps, context)
                results.append(result)
                agents_invoked.append(agent.name)

                # Pass successful results to next agent
                if result.success:
                    context[agent.name] = result.data
                else:
                    errors.append(f"{agent.name}: {result.error}")
                    if not self.config.fallback_to_general:
                        break

            except Exception as e:
                error_msg = f"Error executing {agent.name}: {e!s}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
                results.append(
                    AgentResult(success=False, data={}, error=str(e), agent_name=agent.name)
                )
                if not self.config.fallback_to_general:
                    break

        total_time = (time.time() - start_time) * 1000  # Convert to ms
        success = len(results) > 0 and all(r.success for r in results)

        return WorkflowResult(
            success=success,
            results=results,
            agents_invoked=agents_invoked,
            total_time_ms=total_time,
            parallel=False,
            errors=errors,
        )

    async def execute_parallel(self, agents: list[SpecialistAgent], prompt: str, deps: TaskDependencies) -> WorkflowResult:
        """Execute multiple agents in parallel.

        All agents execute concurrently, up to max_parallel_agents limit.

        Args:
            agents: List of agents to execute concurrently
            prompt: User prompt
            deps: Task dependencies

        Returns:
            WorkflowResult containing all agent results
        """
        if not agents:
            return WorkflowResult(success=False, results=[], agents_invoked=[], total_time_ms=0.0, parallel=True, errors=["No agents to execute"])

        if not self.config.parallel_execution:
            logger.info("Parallel execution disabled, falling back to sequential")
            return self.execute_workflow(agents, prompt, deps)

        # Limit concurrent agents
        agents_to_run = agents[: self.config.max_parallel_agents]
        if len(agents) > self.config.max_parallel_agents:
            logger.warning(f"Limiting parallel execution to {self.config.max_parallel_agents} agents")

        start_time = time.time()
        context: dict[str, Any] = {}

        # Create tasks for all agents
        tasks = [agent.run_async(prompt, deps, context) for agent in agents_to_run]

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        agent_results: list[AgentResult] = []
        agents_invoked: list[str] = []
        errors: list[str] = []

        for i, (agent, result) in enumerate(zip(agents_to_run, results)):
            agents_invoked.append(agent.name)

            if isinstance(result, Exception):
                error_msg = f"Error executing {agent.name}: {result!s}"
                logger.error(error_msg)
                errors.append(error_msg)
                agent_results.append(
                    AgentResult(success=False, data={}, error=str(result), agent_name=agent.name)
                )
            else:
                agent_results.append(result)
                if not result.success:
                    errors.append(f"{agent.name}: {result.error}")

        total_time = (time.time() - start_time) * 1000  # Convert to ms
        success = len(agent_results) > 0 and all(r.success for r in agent_results)

        return WorkflowResult(
            success=success,
            results=agent_results,
            agents_invoked=agents_invoked,
            total_time_ms=total_time,
            parallel=True,
            errors=errors,
        )

    def process(self, request: str, deps: TaskDependencies, force_agent: str | None = None) -> WorkflowResult:
        """Process a user request through the multi-agent system.

        Main entry point for coordinator. Routes to appropriate agent(s)
        and executes them.

        Args:
            request: User request
            deps: Task dependencies
            force_agent: Optionally force a specific agent by name

        Returns:
            WorkflowResult from execution
        """
        if not self.config.enabled:
            return WorkflowResult(
                success=False,
                results=[],
                agents_invoked=[],
                total_time_ms=0.0,
                errors=["Multi-agent system disabled"],
            )

        # Force specific agent if requested
        if force_agent:
            agent = self.registry.get(force_agent)
            if agent:
                logger.info(f"Forcing execution with: {force_agent}")
                return self.execute_workflow([agent], request, deps)
            logger.warning(f"Forced agent '{force_agent}' not found")

        # Try workflow routing first
        workflow = self.route_to_workflow(request, deps)
        if workflow:
            return self.execute_workflow(workflow, request, deps)

        # Fall back to single agent routing
        agents = self.route_request(request, deps)
        if agents:
            return self.execute_workflow(agents, request, deps)

        # No agents matched
        return WorkflowResult(
            success=False,
            results=[],
            agents_invoked=[],
            total_time_ms=0.0,
            errors=["No agent could handle request"],
        )

    async def process_async(self, request: str, deps: TaskDependencies, parallel: bool = False) -> WorkflowResult:
        """Async version of process() for parallel execution.

        Args:
            request: User request
            deps: Task dependencies
            parallel: Execute agents in parallel if multiple match

        Returns:
            WorkflowResult from execution
        """
        if not self.config.enabled:
            return WorkflowResult(
                success=False,
                results=[],
                agents_invoked=[],
                total_time_ms=0.0,
                errors=["Multi-agent system disabled"],
            )

        # Get workflow or single agent
        workflow = self.route_to_workflow(request, deps)
        if not workflow:
            agents = self.route_request(request, deps)
            if agents:
                workflow = agents

        if not workflow:
            return WorkflowResult(
                success=False,
                results=[],
                agents_invoked=[],
                total_time_ms=0.0,
                errors=["No agent could handle request"],
            )

        # Execute
        if parallel and len(workflow) > 1:
            return await self.execute_parallel(workflow, request, deps)
        return self.execute_workflow(workflow, request, deps)

    def get_stats(self) -> dict[str, Any]:
        """Get coordinator statistics.

        Returns:
            Statistics about agents, workflows, etc.
        """
        return {
            "enabled": self.config.enabled,
            "registered_agents": len(self.registry),
            "enabled_agents": len(self.registry.enabled_agents),
            "parallel_execution": self.config.parallel_execution,
            "max_parallel_agents": self.config.max_parallel_agents,
            "capabilities": self.registry.get_capabilities(),
        }
