"""
Anthropic provider implementation for AI Chat Console

Implements the BaseProvider interface for Anthropic's Claude API.
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, List, Any, Optional

import anthropic
from httpx import AsyncClient

from .base import BaseProvider, Message, MessageRole, ModelInfo, ProviderError, AuthenticationError


class AnthropicProvider(BaseProvider):
    """Anthropic Claude API provider"""

    def __init__(self, api_key: str, base_url: str, model: str, **kwargs):
        super().__init__(api_key, base_url, model, **kwargs)

        # Initialize Anthropic client
        self.anthropic_client = anthropic.AsyncAnthropic(
            api_key=self.api_key,
            base_url=self.base_url if self.base_url != "https://api.anthropic.com" else None,
        )

    def _get_headers(self) -> Dict[str, str]:
        """Get Anthropic-specific headers"""
        headers = super()._get_headers()
        headers["x-api-key"] = self.api_key
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def _convert_messages_to_anthropic_format(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert messages to Anthropic format"""
        anthropic_messages = []

        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                # System messages are handled separately in Anthropic
                continue
            elif msg.role == MessageRole.USER:
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                anthropic_messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == MessageRole.TOOL:
                # Convert tool messages to user messages for now
                # Anthropic handles tool calling differently
                anthropic_messages.append({
                    "role": "user",
                    "content": f"Tool result: {msg.content}"
                })

        return anthropic_messages

    def _extract_system_message(self, messages: List[Message]) -> Optional[str]:
        """Extract system message from messages"""
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                return msg.content
        return None

    async def create_message(
        self,
        messages: List[Message],
        **kwargs
    ) -> str:
        """Create a message (non-streaming)"""
        try:
            # Convert messages
            anthropic_messages = self._convert_messages_to_anthropic_format(messages)
            system_message = self._extract_system_message(messages)

            # Create message
            response = await self.anthropic_client.messages.create(
                model=self.model,
                messages=anthropic_messages,
                system=system_message,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            )

            # Extract content
            return response.content[0].text

        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {e}")
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}")
        except anthropic.APIError as e:
            raise ProviderError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def stream_message(
        self,
        messages: List[Message],
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """Stream a message response"""
        try:
            # Convert messages
            anthropic_messages = self._convert_messages_to_anthropic_format(messages)
            system_message = self._extract_system_message(messages)

            # Create streaming message
            async with self.anthropic_client.messages.stream(
                model=self.model,
                messages=anthropic_messages,
                system=system_message,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            ) as stream:
                async for text in stream.text_stream:
                    yield text

        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {e}")
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}")
        except anthropic.APIError as e:
            raise ProviderError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def create_message_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> Dict[str, Any]:
        """Create a message with tool calling support"""
        try:
            # Convert messages
            anthropic_messages = self._convert_messages_to_anthropic_format(messages)
            system_message = self._extract_system_message(messages)

            # Convert tools to Anthropic format
            anthropic_tools = []
            for tool in tools:
                anthropic_tool = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool.get("parameters", {}),
                }
                anthropic_tools.append(anthropic_tool)

            # Create message with tools
            response = await self.anthropic_client.messages.create(
                model=self.model,
                messages=anthropic_messages,
                system=system_message,
                tools=anthropic_tools if anthropic_tools else None,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            )

            # Extract content and tool calls
            content = ""
            tool_calls = []

            for content_block in response.content:
                if content_block.type == "text":
                    content += content_block.text
                elif content_block.type == "tool_use":
                    tool_call = {
                        "id": content_block.id,
                        "name": content_block.name,
                        "arguments": content_block.input,
                    }
                    tool_calls.append(tool_call)

            return {
                "content": content,
                "tool_calls": tool_calls,
                "model": response.model,
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            }

        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {e}")
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}")
        except anthropic.APIError as e:
            raise ProviderError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def stream_message_with_tools(
        self,
        messages: List[Message],
        tools: List[Dict[str, Any]],
        **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a message with tool calling support"""
        try:
            # Convert messages
            anthropic_messages = self._convert_messages_to_anthropic_format(messages)
            system_message = self._extract_system_message(messages)

            # Convert tools to Anthropic format
            anthropic_tools = []
            for tool in tools:
                anthropic_tool = {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool.get("parameters", {}),
                }
                anthropic_tools.append(anthropic_tool)

            # Stream message with tools
            async with self.anthropic_client.messages.stream(
                model=self.model,
                messages=anthropic_messages,
                system=system_message,
                tools=anthropic_tools if anthropic_tools else None,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            ) as stream:
                async for chunk in stream:
                    if chunk.type == "content_block_start":
                        if chunk.content_block.type == "text":
                            yield {"content": ""}
                        elif chunk.content_block.type == "tool_use":
                            yield {
                                "tool_call_start": {
                                    "id": chunk.content_block.id,
                                    "name": chunk.content_block.name,
                                }
                            }
                    elif chunk.type == "content_block_delta":
                        if chunk.delta.type == "text_delta":
                            yield {"content": chunk.delta.text}
                        elif chunk.delta.type == "input_json_delta":
                            yield {
                                "tool_call_delta": {
                                    "partial_json": chunk.delta.partial_json,
                                }
                            }
                    elif chunk.type == "message_stop":
                        yield {"stop": True}

        except anthropic.AuthenticationError as e:
            raise AuthenticationError(f"Anthropic authentication failed: {e}")
        except anthropic.RateLimitError as e:
            raise ProviderError(f"Anthropic rate limit exceeded: {e}")
        except anthropic.APIError as e:
            raise ProviderError(f"Anthropic API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def get_model_info(self, model: str) -> ModelInfo:
        """Get information about a specific model"""
        # Model information for Claude models
        model_info_map = {
            "claude-3-5-sonnet-20241022": ModelInfo(
                name="claude-3-5-sonnet-20241022",
                max_tokens=8192,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=True,
                context_window=200000,
                input_cost_per_1k=0.003,
                output_cost_per_1k=0.015,
            ),
            "claude-3-5-haiku-20241022": ModelInfo(
                name="claude-3-5-haiku-20241022",
                max_tokens=8192,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=200000,
                input_cost_per_1k=0.001,
                output_cost_per_1k=0.005,
            ),
            "claude-3-opus-20240229": ModelInfo(
                name="claude-3-opus-20240229",
                max_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=True,
                context_window=200000,
                input_cost_per_1k=0.015,
                output_cost_per_1k=0.075,
            ),
            "GLM-4.6": ModelInfo(
                name="GLM-4.6",
                max_tokens=8000,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=True,
                context_window=200000,
                input_cost_per_1k=0.005,
                output_cost_per_1k=0.015,
            ),
        }

        # Return model info or a default
        return model_info_map.get(model, ModelInfo(
            name=model,
            max_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
            supports_thinking=False,
            context_window=200000,
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.05,
        ))

    async def list_models(self) -> List[ModelInfo]:
        """List all available models"""
        # Return list of Claude models
        models = [
            await self.get_model_info("claude-3-5-sonnet-20241022"),
            await self.get_model_info("claude-3-5-haiku-20241022"),
            await self.get_model_info("claude-3-opus-20240229"),
        ]
        return models