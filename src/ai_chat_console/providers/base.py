"""
Base provider interface for AI Chat Console

Defines the abstract interface that all AI providers must implement.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

import httpx


class MessageRole(Enum):
    """Message role types"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """Represents a chat message"""
    role: MessageRole
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary format"""
        result = {
            "role": self.role.value,
            "content": self.content,
        }

        if self.tool_calls:
            result["tool_calls"] = self.tool_calls

        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """Create message from dictionary"""
        return cls(
            role=MessageRole(data["role"]),
            content=data["content"],
            tool_calls=data.get("tool_calls"),
            tool_call_id=data.get("tool_call_id"),
        )


@dataclass
class ToolCall:
    """Represents a tool call"""
    id: str
    name: str
    arguments: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert tool call to dictionary format"""
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class ModelInfo:
    """Information about an AI model"""
    name: str
    max_tokens: int
    supports_streaming: bool
    supports_tools: bool
    supports_thinking: bool
    context_window: int
    input_cost_per_1k: float
    output_cost_per_1k: float


class ProviderError(Exception):
    """Base exception for provider errors"""
    pass


class AuthenticationError(ProviderError):
    """Raised when authentication fails"""
    pass


class RateLimitError(ProviderError):
    """Raised when rate limit is exceeded"""
    pass


class ModelNotFoundError(ProviderError):
    """Raised when requested model is not found"""
    pass


class BaseProvider(ABC):
    """Abstract base class for all AI providers"""

    def __init__(self, api_key: str, base_url: str, model: str, **kwargs):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._get_headers(),
            timeout=60.0,
        )

        # Additional configuration
        self.max_tokens = kwargs.get('max_tokens', 1000)
        self.temperature = kwargs.get('temperature', 0.7)
        self.supports_streaming = kwargs.get('supports_streaming', True)
        self.supports_tools = kwargs.get('supports_tools', False)
        self.supports_thinking = kwargs.get('supports_thinking', False)

    def _get_headers(self) -> Dict[str, str]:
        """Get default headers for API requests"""
        return {
            "Content-Type": "application/json",
            "User-Agent": "ai-chat-console/0.1.0",
        }

    @abstractmethod
    async def create_message(
        self,
        messages: List[Message],
        **kwargs
    ) -> str:
        """
        Create a message (non-streaming)

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            The complete response text
        """
        pass

    @abstractmethod
    async def stream_message(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        Stream a message response

        Args:
            messages: List of conversation messages
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Yields:
            Response text chunks as they're generated
        """
        pass

    @abstractmethod
    async def create_message_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Create a message with tool calling support

        Args:
            messages: List of conversation messages
            tools: List of available tools
            **kwargs: Additional parameters

        Returns:
            Response with content and tool calls
        """
        pass

    @abstractmethod
    async def stream_message_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Stream a message with tool calling support

        Args:
            messages: List of conversation messages
            tools: List of available tools
            **kwargs: Additional parameters

        Yields:
            Response chunks with content and tool calls
        """
        pass

    def supports_tool_calling(self) -> bool:
        """Check if provider supports tool calling"""
        return self.supports_tools

    def supports_thinking_mode(self) -> bool:
        """Check if provider supports thinking mode"""
        return self.supports_thinking

    def supports_streaming_mode(self) -> bool:
        """Check if provider supports streaming"""
        return self.supports_streaming

    @abstractmethod
    async def get_model_info(self, model: str) -> ModelInfo:
        """
        Get information about a specific model

        Args:
            model: Model name

        Returns:
            Model information
        """
        pass

    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """
        List all available models

        Returns:
            List of model information
        """
        pass

    async def validate_connection(self) -> bool:
        """
        Validate that the provider connection works

        Returns:
            True if connection is valid
        """
        try:
            # Try to get model list as a simple connection test
            await self.list_models()
            return True
        except Exception:
            return False

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    async def close(self):
        """Close the provider and cleanup resources"""
        await self.client.aclose()

    def _prepare_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        """Prepare messages for API request"""
        return [msg.to_dict() for msg in messages]

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API error responses"""
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed")
        elif response.status_code == 429:
            raise RateLimitError("Rate limit exceeded")
        elif response.status_code == 404:
            raise ModelNotFoundError("Model not found")
        elif response.status_code >= 400:
            error_data = response.json() if response.content else {}
            raise ProviderError(f"API error: {response.status_code} - {error_data}")

    def _extract_content_from_response(self, response_data: Dict[str, Any]) -> str:
        """Extract content from provider response"""
        # Default implementation - should be overridden by providers
        if isinstance(response_data, str):
            return response_data

        # Try common response formats
        if "content" in response_data:
            content = response_data["content"]
            if isinstance(content, list) and content:
                return content[0].get("text", "")
            elif isinstance(content, str):
                return content

        if "choices" in response_data:
            choices = response_data["choices"]
            if choices and "message" in choices[0]:
                return choices[0]["message"].get("content", "")

        # Fallback
        return str(response_data)