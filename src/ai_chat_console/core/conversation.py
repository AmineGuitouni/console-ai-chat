"""
Conversation management for AI Chat Console

Handles conversation history, message management, and context tracking.
"""

from typing import List, Optional
from dataclasses import dataclass, field

from ..providers.base import Message, MessageRole


@dataclass
class Conversation:
    """Represents a conversation with the AI"""
    messages: List[Message] = field(default_factory=list)
    max_history: int = 50
    system_prompt: Optional[str] = None

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation"""
        self.messages.append(message)
        self._trim_history()

    def _trim_history(self) -> None:
        """Trim conversation history to max_history"""
        if len(self.messages) > self.max_history:
            # Keep system messages and recent messages
            system_msgs = [msg for msg in self.messages if msg.role == MessageRole.SYSTEM]
            other_msgs = [msg for msg in self.messages if msg.role != MessageRole.SYSTEM]

            # Keep the most recent messages (excluding system messages)
            recent_msgs = other_msgs[-(self.max_history - len(system_msgs)):]

            self.messages = system_msgs + recent_msgs

    def get_messages_for_provider(self) -> List[Message]:
        """Get messages formatted for provider"""
        return self.messages.copy()

    def clear(self) -> None:
        """Clear the conversation"""
        self.messages.clear()

    def get_last_message(self) -> Optional[Message]:
        """Get the last message in the conversation"""
        return self.messages[-1] if self.messages else None

    def get_message_count(self) -> int:
        """Get the total number of messages"""
        return len(self.messages)

    def get_token_count_estimate(self) -> int:
        """Get a rough estimate of token count"""
        total_chars = sum(len(message.content) for message in self.messages)
        # Rough estimate: 1 token ≈ 4 characters
        return total_chars // 4

    def export_to_dict(self) -> List[dict]:
        """Export conversation to list of dictionaries"""
        return [message.to_dict() for message in self.messages]

    @classmethod
    def import_from_dict(cls, data: List[dict]) -> "Conversation":
        """Import conversation from list of dictionaries"""
        messages = [Message.from_dict(item) for item in data]
        return cls(messages=messages)