"""Message types for inter-agent communication."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4


class MessageType(Enum):
    """Types of messages that can be passed between agents."""

    REQUEST = "request"  # Agent requests another agent's help
    RESPONSE = "response"  # Agent responds to a request
    NOTIFICATION = "notification"  # Agent broadcasts information
    ERROR = "error"  # Agent reports a failure
    QUERY = "query"  # Agent queries coordinator for information
    RESULT = "result"  # Agent returns final result


@dataclass
class AgentMessage:
    """Message passed between agents or to/from coordinator.

    Attributes:
        sender: Name of sending agent
        recipient: Name of target agent or "coordinator"
        message_type: Type of message
        payload: Message data (structure depends on message_type)
        conversation_id: UUID for threading related messages
        reply_to: ID of message this is replying to (for REQUEST/RESPONSE)
        timestamp: When message was created
        priority: Message priority (higher = more urgent)
        timeout_ms: Maximum time to wait for response (for REQUESTs)
    """

    sender: str
    recipient: str
    message_type: MessageType
    payload: dict[str, Any]
    conversation_id: UUID = field(default_factory=uuid4)
    message_id: UUID = field(default_factory=uuid4)
    reply_to: UUID | None = None
    timestamp: datetime = field(default_factory=datetime.now)
    priority: int = 0
    timeout_ms: int = 30000  # 30 seconds default

    def create_response(self, payload: dict[str, Any], message_type: MessageType = MessageType.RESPONSE) -> "AgentMessage":
        """Create a response message to this message.

        Args:
            payload: Response data
            message_type: Type of response (default: RESPONSE)

        Returns:
            New AgentMessage configured as a response
        """
        return AgentMessage(
            sender=self.recipient,  # Response sender is original recipient
            recipient=self.sender,  # Response goes back to original sender
            message_type=message_type,
            payload=payload,
            conversation_id=self.conversation_id,
            reply_to=self.message_id,
        )

    def create_error(self, error_message: str, details: dict[str, Any] | None = None) -> "AgentMessage":
        """Create an error response to this message.

        Args:
            error_message: Error description
            details: Additional error details

        Returns:
            New AgentMessage configured as an error
        """
        payload = {"error": error_message}
        if details:
            payload["details"] = details

        return AgentMessage(
            sender=self.recipient,
            recipient=self.sender,
            message_type=MessageType.ERROR,
            payload=payload,
            conversation_id=self.conversation_id,
            reply_to=self.message_id,
        )

    def __str__(self) -> str:
        """String representation of message."""
        return f"[{self.message_type.value.upper()}] {self.sender} → {self.recipient}"


@dataclass
class MessageBus:
    """Simple message bus for routing messages between agents.

    Attributes:
        messages: Queue of messages to be processed
        conversations: Map of conversation_id to list of messages
    """

    messages: list[AgentMessage] = field(default_factory=list)
    conversations: dict[UUID, list[AgentMessage]] = field(default_factory=dict)

    def send(self, message: AgentMessage) -> None:
        """Send a message through the bus.

        Args:
            message: Message to send
        """
        self.messages.append(message)

        # Track in conversation
        if message.conversation_id not in self.conversations:
            self.conversations[message.conversation_id] = []
        self.conversations[message.conversation_id].append(message)

    def receive(self, recipient: str, timeout_ms: int = 1000) -> AgentMessage | None:
        """Receive the next message for a recipient.

        Args:
            recipient: Name of receiving agent
            timeout_ms: Maximum time to wait (not implemented, for future use)

        Returns:
            Next message for recipient, or None if queue empty
        """
        for i, msg in enumerate(self.messages):
            if msg.recipient == recipient:
                return self.messages.pop(i)
        return None

    def get_conversation(self, conversation_id: UUID) -> list[AgentMessage]:
        """Get all messages in a conversation.

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of messages in conversation (chronological order)
        """
        return self.conversations.get(conversation_id, [])

    def clear(self) -> None:
        """Clear all messages and conversations."""
        self.messages.clear()
        self.conversations.clear()
