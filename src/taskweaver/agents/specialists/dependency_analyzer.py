"""DependencyAnalyzerAgent - Analyzes and validates task dependencies."""

import logging
from pathlib import Path
from typing import Any

from pydantic_ai import Agent

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.base_agent import BaseSpecialistAgent
from taskweaver.agents.tools import (
    add_dependency_tool,
    get_blocked_tool,
    get_blockers_tool,
    remove_dependency_tool,
)

logger = logging.getLogger(__name__)


class DependencyAnalyzerAgent(BaseSpecialistAgent):
    """Specialist agent for analyzing task dependencies and relationships.

    Optimized for:
    - DAG (Directed Acyclic Graph) reasoning
    - Cycle detection
    - Critical path identification
    - Dependency validation and optimization
    """

    def __init__(self, model: str = "openai:gpt-4o"):
        """Initialize DependencyAnalyzerAgent.

        Args:
            model: PydanticAI model identifier (uses stronger model for graph reasoning)
        """
        prompt_path = Path(__file__).parent.parent / "prompts" / "specialists" / "dependency_analyzer.md"
        super().__init__(model=model, system_prompt_path=prompt_path)

        # Create PydanticAI agent with dependency tools
        self._agent: Agent[TaskDependencies, str] = Agent(
            model=self.model,
            deps_type=TaskDependencies,
            result_type=str,
            tools=[add_dependency_tool, remove_dependency_tool, get_blockers_tool, get_blocked_tool],
        )

        if self._system_prompt:

            @self._agent.system_prompt
            def get_prompt(ctx) -> str:
                return self._system_prompt

    @property
    def name(self) -> str:
        return "DependencyAnalyzerAgent"

    @property
    def description(self) -> str:
        return "Analyzes task dependencies, detects cycles, and identifies critical paths"

    @property
    def capabilities(self) -> list[str]:
        return [
            "dependency_analysis",
            "cycle_detection",
            "critical_path",
            "blocker_identification",
            "dependency_optimization",
        ]

    def can_handle(self, request: str, context: dict[str, Any] | None = None) -> float:
        """Check if this agent can handle the request."""
        keywords = [
            "dependency",
            "dependencies",
            "depends on",
            "blocker",
            "blocked",
            "prerequisite",
            "requires",
            "before",
            "after",
            "order",
        ]

        # High confidence for explicit dependency language
        if any(phrase in request.lower() for phrase in ["add dependency", "remove dependency", "find blockers"]):
            return 0.95

        return self._keyword_match_score(request, keywords)

    def _execute(self, prompt: str, deps: TaskDependencies, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute dependency analysis."""
        logger.info(f"[{self.name}] Analyzing dependencies for: {prompt[:100]}...")

        try:
            result = self._agent.run_sync(prompt, deps=deps)

            return {
                "message": result.data,
                "analysis_complete": True,
            }

        except Exception as e:
            logger.error(f"[{self.name}] Execution error: {e}", exc_info=True)
            raise
