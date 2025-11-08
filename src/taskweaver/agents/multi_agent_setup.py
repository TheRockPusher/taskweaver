"""Multi-agent system setup and integration.

This module provides easy integration of the multi-agent system with TaskWeaver.
It handles initialization, configuration, and provides a simple interface for
routing requests to specialist agents.
"""

import logging
from typing import Any

from taskweaver.agents.dependencies import TaskDependencies
from taskweaver.agents.multi_agent import (
    AgentRegistry,
    MultiAgentCoordinator,
)
from taskweaver.agents.multi_agent.coordinator import CoordinatorConfig
from taskweaver.agents.specialists import (
    DependencyAnalyzerAgent,
    EstimationAgent,
    LearningPathAgent,
    PriorityCalculatorAgent,
    SkillGapAnalyzerAgent,
    TaskDecomposerAgent,
)
from taskweaver.config import Config

logger = logging.getLogger(__name__)


def create_multi_agent_system(config: Config) -> MultiAgentCoordinator | None:
    """Create and configure the multi-agent system.

    Initializes the coordinator, registry, and all specialist agents
    based on configuration settings.

    Args:
        config: Application configuration

    Returns:
        Configured MultiAgentCoordinator, or None if multi-agent disabled
    """
    if not config.multi_agent_enabled:
        logger.info("Multi-agent system disabled in configuration")
        return None

    logger.info("Initializing multi-agent system")

    # Create coordinator config
    coordinator_config = CoordinatorConfig(
        enabled=config.multi_agent_enabled,
        parallel_execution=config.multi_agent_parallel,
        max_parallel_agents=config.multi_agent_max_parallel,
        fallback_to_general=config.multi_agent_fallback,
        min_confidence=config.multi_agent_min_confidence,
    )

    # Create registry
    registry = AgentRegistry()

    # Register TaskDecomposerAgent
    if config.agent_task_decomposer_enabled:
        try:
            agent = TaskDecomposerAgent(model=config.agent_task_decomposer_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create TaskDecomposerAgent: {e}")

    # Register DependencyAnalyzerAgent
    if config.agent_dependency_analyzer_enabled:
        try:
            agent = DependencyAnalyzerAgent(model=config.agent_dependency_analyzer_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create DependencyAnalyzerAgent: {e}")

    # Register EstimationAgent
    if config.agent_estimation_enabled:
        try:
            agent = EstimationAgent(model=config.agent_estimation_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create EstimationAgent: {e}")

    # Register PriorityCalculatorAgent
    if config.agent_priority_calculator_enabled:
        try:
            agent = PriorityCalculatorAgent(model=config.agent_priority_calculator_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create PriorityCalculatorAgent: {e}")

    # Register LearningPathAgent
    if config.agent_learning_path_enabled:
        try:
            agent = LearningPathAgent(model=config.agent_learning_path_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create LearningPathAgent: {e}")

    # Register SkillGapAnalyzerAgent
    if config.agent_skill_gap_enabled:
        try:
            agent = SkillGapAnalyzerAgent(model=config.agent_skill_gap_model)
            registry.register(agent, enabled=True)
            logger.info(f"Registered {agent.name}")
        except Exception as e:
            logger.error(f"Failed to create SkillGapAnalyzerAgent: {e}")

    # Create coordinator
    coordinator = MultiAgentCoordinator(registry=registry, config=coordinator_config)

    logger.info(f"Multi-agent system initialized with {len(registry)} agents")
    return coordinator


def process_with_multi_agent(
    coordinator: MultiAgentCoordinator | None, user_input: str, deps: TaskDependencies
) -> tuple[str, bool]:
    """Process user input through multi-agent system.

    Args:
        coordinator: Multi-agent coordinator (None if disabled)
        user_input: User's message
        deps: Task dependencies

    Returns:
        Tuple of (response_message, handled_by_specialist)
        - response_message: Agent's response
        - handled_by_specialist: True if handled by specialist, False if should fall back to general agent
    """
    if not coordinator or not coordinator.config.enabled:
        return "", False

    try:
        # Process through multi-agent system
        result = coordinator.process(user_input, deps)

        if result.success and result.final_result:
            # Specialist handled it successfully
            response = result.final_result.data.get("message", "")
            logger.info(f"Request handled by: {', '.join(result.agents_invoked)}")
            return response, True

        # Specialist couldn't handle or failed
        if result.errors:
            logger.warning(f"Multi-agent errors: {result.errors}")

        return "", False

    except Exception as e:
        logger.error(f"Multi-agent processing error: {e}", exc_info=True)
        return "", False


def get_multi_agent_stats(coordinator: MultiAgentCoordinator | None) -> dict[str, Any]:
    """Get statistics about the multi-agent system.

    Args:
        coordinator: Multi-agent coordinator

    Returns:
        Statistics dictionary
    """
    if not coordinator:
        return {"enabled": False, "reason": "Multi-agent system not initialized"}

    return coordinator.get_stats()
