"""Tests for multi-agent framework core components."""

import pytest

from taskweaver.agents.multi_agent import AgentRegistry, MultiAgentCoordinator
from taskweaver.agents.multi_agent.coordinator import CoordinatorConfig
from taskweaver.agents.multi_agent.message import AgentMessage, MessageBus, MessageType
from taskweaver.agents.multi_agent.protocol import AgentResult


class MockAgent:
    """Mock agent for testing."""

    def __init__(self, name: str, capabilities: list[str] | None = None):
        self._name = name
        self._capabilities = capabilities or []

    @property
    def name(self) -> str:
        return self._name

    @property
    def description(self) -> str:
        return f"Mock agent: {self._name}"

    @property
    def capabilities(self) -> list[str]:
        return self._capabilities

    def can_handle(self, request: str, context=None) -> float:
        """Return high confidence if request mentions agent name."""
        return 0.9 if self._name.lower() in request.lower() else 0.1

    def run(self, prompt: str, deps, context=None) -> AgentResult:
        """Mock run that returns success."""
        return AgentResult(
            success=True, data={"message": f"{self._name} handled: {prompt}"}, agent_name=self._name, execution_time_ms=10.0
        )

    async def run_async(self, prompt: str, deps, context=None) -> AgentResult:
        """Mock async run."""
        return self.run(prompt, deps, context)


# ============================================================================
# Registry Tests
# ============================================================================


def test_registry_register_agent():
    """Test registering an agent."""
    registry = AgentRegistry()
    agent = MockAgent("TestAgent")

    registry.register(agent, enabled=True)

    assert "TestAgent" in registry
    assert len(registry) == 1
    assert agent in registry.list_agents(enabled_only=True)


def test_registry_unregister_agent():
    """Test unregistering an agent."""
    registry = AgentRegistry()
    agent = MockAgent("TestAgent")

    registry.register(agent)
    assert len(registry) == 1

    registry.unregister("TestAgent")
    assert len(registry) == 0


def test_registry_enable_disable():
    """Test enabling/disabling agents."""
    registry = AgentRegistry()
    agent = MockAgent("TestAgent")

    registry.register(agent, enabled=True)
    assert agent in registry.list_agents(enabled_only=True)

    registry.disable("TestAgent")
    assert agent not in registry.list_agents(enabled_only=True)

    registry.enable("TestAgent")
    assert agent in registry.list_agents(enabled_only=True)


def test_registry_find_best_agent():
    """Test finding the best agent for a request."""
    registry = AgentRegistry()
    agent1 = MockAgent("Agent1", ["task1"])
    agent2 = MockAgent("Agent2", ["task2"])

    registry.register(agent1, enabled=True)
    registry.register(agent2, enabled=True)

    # Request mentioning Agent1
    best = registry.find_best_agent("Can Agent1 help me?")
    assert best == agent1

    # Request mentioning Agent2
    best = registry.find_best_agent("I need Agent2")
    assert best == agent2


def test_registry_find_all_matching():
    """Test finding all matching agents."""
    registry = AgentRegistry()
    agent1 = MockAgent("Agent1")
    agent2 = MockAgent("Agent2")
    agent3 = MockAgent("Agent3")

    registry.register(agent1, enabled=True)
    registry.register(agent2, enabled=True)
    registry.register(agent3, enabled=False)  # Disabled

    # With low threshold, should find enabled agents
    matches = registry.find_all_matching("Hello", min_confidence=0.05)

    # Only enabled agents
    agent_list = [agent for agent, _ in matches]
    assert agent1 in agent_list
    assert agent2 in agent_list
    assert agent3 not in agent_list  # Disabled


# ============================================================================
# Message Tests
# ============================================================================


def test_message_creation():
    """Test creating a message."""
    msg = AgentMessage(
        sender="Agent1", recipient="Agent2", message_type=MessageType.REQUEST, payload={"action": "do_something"}
    )

    assert msg.sender == "Agent1"
    assert msg.recipient == "Agent2"
    assert msg.message_type == MessageType.REQUEST
    assert msg.payload["action"] == "do_something"


def test_message_create_response():
    """Test creating a response message."""
    request = AgentMessage(sender="Agent1", recipient="Agent2", message_type=MessageType.REQUEST, payload={})

    response = request.create_response({"result": "success"})

    assert response.sender == "Agent2"  # Swapped
    assert response.recipient == "Agent1"  # Swapped
    assert response.message_type == MessageType.RESPONSE
    assert response.reply_to == request.message_id
    assert response.conversation_id == request.conversation_id


def test_message_create_error():
    """Test creating an error message."""
    request = AgentMessage(sender="Agent1", recipient="Agent2", message_type=MessageType.REQUEST, payload={})

    error = request.create_error("Something went wrong", {"code": 500})

    assert error.message_type == MessageType.ERROR
    assert error.payload["error"] == "Something went wrong"
    assert error.payload["details"]["code"] == 500


def test_message_bus_send_receive():
    """Test sending and receiving messages."""
    bus = MessageBus()

    msg = AgentMessage(sender="Agent1", recipient="Agent2", message_type=MessageType.REQUEST, payload={})

    bus.send(msg)
    assert len(bus.messages) == 1

    received = bus.receive("Agent2")
    assert received == msg
    assert len(bus.messages) == 0  # Consumed


def test_message_bus_conversation_tracking():
    """Test conversation tracking."""
    bus = MessageBus()

    msg1 = AgentMessage(sender="Agent1", recipient="Agent2", message_type=MessageType.REQUEST, payload={})
    msg2 = msg1.create_response({"result": "ok"})

    bus.send(msg1)
    bus.send(msg2)

    conversation = bus.get_conversation(msg1.conversation_id)
    assert len(conversation) == 2
    assert conversation[0] == msg1
    assert conversation[1] == msg2


# ============================================================================
# Coordinator Tests
# ============================================================================


def test_coordinator_creation():
    """Test creating a coordinator."""
    registry = AgentRegistry()
    config = CoordinatorConfig(enabled=True)

    coordinator = MultiAgentCoordinator(registry=registry, config=config)

    assert coordinator.registry == registry
    assert coordinator.config.enabled


def test_coordinator_route_request():
    """Test routing a request to an agent."""
    registry = AgentRegistry()
    agent = MockAgent("TaskAgent", ["task"])
    registry.register(agent, enabled=True)

    config = CoordinatorConfig(enabled=True, min_confidence=0.3)
    coordinator = MultiAgentCoordinator(registry=registry, config=config)

    # Route request that mentions agent
    agents = coordinator.route_request("TaskAgent do something", deps=None)

    assert len(agents) == 1
    assert agents[0] == agent


def test_coordinator_disabled():
    """Test coordinator when disabled."""
    registry = AgentRegistry()
    config = CoordinatorConfig(enabled=False)
    coordinator = MultiAgentCoordinator(registry=registry, config=config)

    # Should return empty list when disabled
    agents = coordinator.route_request("Hello", deps=None)
    assert len(agents) == 0


def test_coordinator_get_stats():
    """Test getting coordinator statistics."""
    registry = AgentRegistry()
    agent = MockAgent("Agent1")
    registry.register(agent, enabled=True)

    config = CoordinatorConfig(enabled=True)
    coordinator = MultiAgentCoordinator(registry=registry, config=config)

    stats = coordinator.get_stats()

    assert stats["enabled"] is True
    assert stats["registered_agents"] == 1
    assert stats["enabled_agents"] == 1
    assert "Agent1" in stats["capabilities"]


# ============================================================================
# AgentResult Tests
# ============================================================================


def test_agent_result_success():
    """Test successful agent result."""
    result = AgentResult(
        success=True, data={"message": "Task completed"}, agent_name="TestAgent", execution_time_ms=100.0
    )

    assert result.success
    assert result.data["message"] == "Task completed"
    assert result.agent_name == "TestAgent"
    assert result.execution_time_ms == 100.0
    assert result.error is None


def test_agent_result_failure():
    """Test failed agent result."""
    result = AgentResult(success=False, data={}, error="Something went wrong", agent_name="TestAgent")

    assert not result.success
    assert result.error == "Something went wrong"


def test_agent_result_string_representation():
    """Test string representation of result."""
    result = AgentResult(
        success=True, data={}, agent_name="TestAgent", execution_time_ms=50.0
    )

    str_repr = str(result)
    assert "TestAgent" in str_repr
    assert "SUCCESS" in str_repr
    assert "50.0ms" in str_repr
