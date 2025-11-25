"""
OpenAI provider implementation for AI Chat Console

Implements the BaseProvider interface for OpenAI's API.
"""

import json
import asyncio
from typing import AsyncGenerator, Dict, List, Any

from .base import BaseProvider, Message, MessageRole, ModelInfo, ProviderError, AuthenticationError, RateLimitError, ModelNotFoundError
import openai
from openai import AsyncOpenAI


class OpenAIProvider(BaseProvider):
    """OpenAI API provider"""

    def __init__(self, api_key: str, base_url: str, model: str, **kwargs):
        super().__init__(api_key, base_url, model, **kwargs)

        # Initialize OpenAI client
        client_config = {
            "api_key": self.api_key,
        }

        # Use custom base URL if provided and not the default
        if base_url and base_url != "https://api.openai.com/v1":
            client_config["base_url"] = base_url

        self.openai_client = AsyncOpenAI(**client_config)

        # Additional configuration
        self.max_tokens = kwargs.get('max_tokens', 4096)
        self.temperature = kwargs.get('temperature', 0.7)
        self.supports_streaming = kwargs.get('supports_streaming', True)
        self.supports_tools = kwargs.get('supports_tools', True)
        self.supports_thinking = kwargs.get('supports_thinking', False)

    def _get_headers(self) -> Dict[str, str]:
        """Get OpenAI-specific headers"""
        headers = super()._get_headers()
        headers["Authorization"] = f"Bearer {self.api_key}"
        headers["Content-Type"] = "application/json"
        return headers

    def _convert_messages_to_openai_format(self, messages: List[Message]) -> List[Dict[str, str]]:
        """Convert messages to OpenAI format"""
        openai_messages = []

        for msg in messages:
            role_mapping = {
                MessageRole.USER: "user",
                MessageRole.ASSISTANT: "assistant",
                MessageRole.SYSTEM: "system",
                MessageRole.TOOL: "tool",
            }

            role = role_mapping.get(msg.role, "user")
            openai_messages.append({
                "role": role,
                "content": msg.content
            })

        return openai_messages

    def _convert_tools_to_openai_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert tools to OpenAI format"""
        openai_tools = []

        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool.get("parameters", {})
                }
            }
            openai_tools.append(openai_tool)

        return openai_tools

    async def create_message(self, messages: List[Message], **kwargs) -> str:
        """Create a message (non-streaming)"""
        try:
            openai_messages = self._convert_messages_to_openai_format(messages)

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            )

            return response.choices[0].message.content

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}")
        except openai.RateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit exceeded: {e}")
        except openai.NotFoundError as e:
            raise ModelNotFoundError(f"OpenAI model not found: {e}")
        except openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def stream_message(self, messages: List[Message], **kwargs) -> AsyncGenerator[str, None]:
        """Stream a message response"""
        try:
            openai_messages = self._convert_messages_to_openai_format(messages)

            stream = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    yield chunk.choices[0].delta.content

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}")
        except openai.RateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit exceeded: {e}")
        except openai.NotFoundError as e:
            raise ModelNotFoundError(f"OpenAI model not found: {e}")
        except openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def create_message_with_tools(
        self, messages: List[Message], tools: List[Dict[str, Any]], **kwargs
    ) -> Dict[str, Any]:
        """Create a message with tool calling support"""
        try:
            openai_messages = self._convert_messages_to_openai_format(messages)
            openai_tools = self._convert_tools_to_openai_format(tools) if tools else None

            response = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools if openai_tools else None,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
            )

            content = response.choices[0].message.content or ""
            tool_calls = []

            if response.choices[0].message.tool_calls:
                for tool_call in response.choices[0].message.tool_calls:
                    tool_calls.append({
                        "id": tool_call.id,
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                    })

            return {
                "content": content,
                "tool_calls": tool_calls,
                "model": response.model,
                "usage": {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                } if response.usage else None,
            }

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}")
        except openai.RateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit exceeded: {e}")
        except openai.NotFoundError as e:
            raise ModelNotFoundError(f"OpenAI model not found: {e}")
        except openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def stream_message_with_tools(
        self, messages: List[Message], tools: List[Dict[str, Any]], **kwargs
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream a message with tool calling support"""
        try:
            openai_messages = self._convert_messages_to_openai_format(messages)
            openai_tools = self._convert_tools_to_openai_format(tools) if tools else None

            stream = await self.openai_client.chat.completions.create(
                model=self.model,
                messages=openai_messages,
                tools=openai_tools if openai_tools else None,
                max_tokens=kwargs.get('max_tokens', self.max_tokens),
                temperature=kwargs.get('temperature', self.temperature),
                stream=True,
            )

            accumulated_content = ""
            accumulated_tool_calls = []

            async for chunk in stream:
                delta = chunk.choices[0].delta

                if delta.content is not None:
                    accumulated_content += delta.content
                    yield {"content": delta.content}

                if delta.tool_calls:
                    for tool_call_delta in delta.tool_calls:
                        tool_call_id = tool_call_delta.id
                        if tool_call_id not in [tc["id"] for tc in accumulated_tool_calls]:
                            accumulated_tool_calls.append({
                                "id": tool_call_id,
                                "name": "",
                                "arguments": ""
                            })

                        # Find the corresponding tool call in accumulated list
                        for tool_call in accumulated_tool_calls:
                            if tool_call["id"] == tool_call_id:
                                if tool_call_delta.function.name:
                                    tool_call["name"] = tool_call_delta.function.name
                                if tool_call_delta.function.arguments:
                                    tool_call["arguments"] += tool_call_delta.function.arguments
                                break

            # Final yield with complete tool calls
            if accumulated_tool_calls:
                for tool_call in accumulated_tool_calls:
                    try:
                        tool_call["arguments"] = json.loads(tool_call["arguments"])
                    except json.JSONDecodeError:
                        # If JSON is incomplete or invalid, skip this tool call
                        pass

                yield {"tool_calls": accumulated_tool_calls}

        except openai.AuthenticationError as e:
            raise AuthenticationError(f"OpenAI authentication failed: {e}")
        except openai.RateLimitError as e:
            raise RateLimitError(f"OpenAI rate limit exceeded: {e}")
        except openai.NotFoundError as e:
            raise ModelNotFoundError(f"OpenAI model not found: {e}")
        except openai.APIError as e:
            raise ProviderError(f"OpenAI API error: {e}")
        except Exception as e:
            raise ProviderError(f"Unexpected error: {e}")

    async def get_model_info(self, model: str) -> ModelInfo:
        """Get information about a specific model"""
        # Model information for OpenAI models
        model_info_map = {
            "gpt-4": ModelInfo(
                name="gpt-4",
                max_tokens=8192,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=128000,
                input_cost_per_1k=0.03,
                output_cost_per_1k=0.06,
            ),
            "gpt-4-turbo": ModelInfo(
                name="gpt-4-turbo",
                max_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=128000,
                input_cost_per_1k=0.01,
                output_cost_per_1k=0.03,
            ),
            "gpt-3.5-turbo": ModelInfo(
                name="gpt-3.5-turbo",
                max_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=16385,
                input_cost_per_1k=0.0015,
                output_cost_per_1k=0.002,
            ),
            "gpt-4o": ModelInfo(
                name="gpt-4o",
                max_tokens=4096,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=128000,
                input_cost_per_1k=0.005,
                output_cost_per_1k=0.015,
            ),
            "gpt-4o-mini": ModelInfo(
                name="gpt-4o-mini",
                max_tokens=16384,
                supports_streaming=True,
                supports_tools=True,
                supports_thinking=False,
                context_window=128000,
                input_cost_per_1k=0.00015,
                output_cost_per_1k=0.0006,
            ),
        }

        # Return model info or a default
        return model_info_map.get(model, ModelInfo(
            name=model,
            max_tokens=4096,
            supports_streaming=True,
            supports_tools=True,
            supports_thinking=False,
            context_window=128000,
            input_cost_per_1k=0.01,
            output_cost_per_1k=0.03,
        ))

    async def list_models(self) -> List[ModelInfo]:
        """List all available models"""
        models = [
            await self.get_model_info("gpt-4"),
            await self.get_model_info("gpt-4-turbo"),
            await self.get_model_info("gpt-3.5-turbo"),
            await self.get_model_info("gpt-4o"),
            await self.get_model_info("gpt-4o-mini"),
        ]
        return models