"""Agent registry for discovering and managing specialist agents."""

import logging
from dataclasses import dataclass, field
from typing import Any

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent.protocol import SpecialistAgent

logger = logging.getLogger(__name__)


@dataclass
class AgentRegistry:
    """Registry for specialist agents.

    Manages registration, discovery, and retrieval of specialist agents.
    Supports intent-based routing to find the best agent for a request.

    Attributes:
        agents: Map of agent name to agent instance
        enabled_agents: Set of agent names that are currently enabled
    """

    agents: dict[str, SpecialistAgent] = field(default_factory=dict)
    enabled_agents: set[str] = field(default_factory=set)

    def register(self, agent: SpecialistAgent, enabled: bool = True) -> None:
        """Register a specialist agent.

        Args:
            agent: Specialist agent to register
            enabled: Whether agent is enabled (default: True)
        """
        if agent.name in self.agents:
            logger.warning(f"Agent '{agent.name}' already registered, replacing")

        self.agents[agent.name] = agent
        if enabled:
            self.enabled_agents.add(agent.name)

        logger.info(f"Registered agent: {agent.name} ({agent.description})")

    def unregister(self, agent_name: str) -> None:
        """Unregister an agent.

        Args:
            agent_name: Name of agent to remove
        """
        if agent_name in self.agents:
            del self.agents[agent_name]
            self.enabled_agents.discard(agent_name)
            logger.info(f"Unregistered agent: {agent_name}")
        else:
            logger.warning(f"Cannot unregister unknown agent: {agent_name}")

    def get(self, agent_name: str) -> SpecialistAgent | None:
        """Get an agent by name.

        Args:
            agent_name: Name of agent to retrieve

        Returns:
            Agent instance or None if not found
        """
        return self.agents.get(agent_name)

    def list_agents(self, enabled_only: bool = True) -> list[SpecialistAgent]:
        """List all registered agents.

        Args:
            enabled_only: Only return enabled agents (default: True)

        Returns:
            List of agent instances
        """
        if enabled_only:
            return [agent for name, agent in self.agents.items() if name in self.enabled_agents]
        return list(self.agents.values())

    def enable(self, agent_name: str) -> None:
        """Enable an agent.

        Args:
            agent_name: Name of agent to enable
        """
        if agent_name in self.agents:
            self.enabled_agents.add(agent_name)
            logger.info(f"Enabled agent: {agent_name}")
        else:
            logger.warning(f"Cannot enable unknown agent: {agent_name}")

    def disable(self, agent_name: str) -> None:
        """Disable an agent.

        Args:
            agent_name: Name of agent to disable
        """
        self.enabled_agents.discard(agent_name)
        logger.info(f"Disabled agent: {agent_name}")

    def find_best_agent(self, request: str, context: dict[str, Any] | None = None, min_confidence: float = 0.3) -> SpecialistAgent | None:
        """Find the best agent to handle a request.

        Args:
            request: User request or prompt
            context: Optional context dictionary
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            Best matching agent or None if no agent exceeds threshold
        """
        best_agent: SpecialistAgent | None = None
        best_score: float = min_confidence

        for agent in self.list_agents(enabled_only=True):
            score = agent.can_handle(request, context)
            if score > best_score:
                best_score = score
                best_agent = agent

        if best_agent:
            logger.info(f"Best agent for request: {best_agent.name} (confidence: {best_score:.2f})")
        else:
            logger.info(f"No agent found for request (threshold: {min_confidence})")

        return best_agent

    def find_all_matching(
        self, request: str, context: dict[str, Any] | None = None, min_confidence: float = 0.3
    ) -> list[tuple[SpecialistAgent, float]]:
        """Find all agents that can handle a request.

        Args:
            request: User request or prompt
            context: Optional context dictionary
            min_confidence: Minimum confidence threshold (0-1)

        Returns:
            List of (agent, confidence) tuples, sorted by confidence descending
        """
        matches: list[tuple[SpecialistAgent, float]] = []

        for agent in self.list_agents(enabled_only=True):
            score = agent.can_handle(request, context)
            if score >= min_confidence:
                matches.append((agent, score))

        # Sort by confidence descending
        matches.sort(key=lambda x: x[1], reverse=True)

        logger.info(f"Found {len(matches)} agents matching request (threshold: {min_confidence})")
        return matches

    def get_capabilities(self) -> dict[str, list[str]]:
        """Get all capabilities across all agents.

        Returns:
            Map of agent name to list of capabilities
        """
        return {agent.name: agent.capabilities for agent in self.list_agents(enabled_only=True)}

    def __len__(self) -> int:
        """Number of registered agents."""
        return len(self.agents)

    def __contains__(self, agent_name: str) -> bool:
        """Check if agent is registered."""
        return agent_name in self.agents
