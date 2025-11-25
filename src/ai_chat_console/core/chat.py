"""
Core chat engine for AI Chat Console

Handles conversation management, provider integration, and message processing.
"""

import asyncio
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass

from ..providers.base import BaseProvider, Message, MessageRole, ToolCall
from ..config import ChatConfig, MCPConfig
from .conversation import Conversation
from .session import SessionManager
from ..tools import ToolRegistry, ToolExecutor
from ..tools.builtin import BUILTIN_TOOLS
from ..mcp.manager import MCPManager


@dataclass
class ChatResponse:
    """Represents a response from the AI"""
    content: str
    tool_calls: Optional[List[ToolCall]] = None
    thinking: Optional[str] = None
    model: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None


class ChatEngine:
    """Main chat engine that coordinates providers and conversation"""

    def __init__(self, provider: BaseProvider, config: ChatConfig, mcp_config: Optional[MCPConfig] = None):
        self.provider = provider
        self.config = config
        self.mcp_config = mcp_config
        self.session_manager = SessionManager()

        # Initialize tool system
        self.tool_registry = ToolRegistry()
        self.tool_executor = ToolExecutor()
        
        # Initialize MCP manager
        self.mcp_manager = MCPManager(mcp_config) if mcp_config else None

        # Register built-in tools
        for tool_class in BUILTIN_TOOLS:
            self.tool_registry.register_class(tool_class)

        # Start with a temporary conversation (will be replaced when session is set)
        self.conversation = Conversation(
            max_history=config.conversation_history_limit,
            system_prompt=config.system_prompt,
        )

        # Add system prompt if provided
        if config.system_prompt:
            system_msg = Message(role=MessageRole.SYSTEM, content=config.system_prompt)
            self.conversation.add_message(system_msg)

    async def initialize(self):
        """Initialize the chat engine and external resources"""
        if self.mcp_manager:
            await self.mcp_manager.initialize()
            
            # Register MCP tools
            for tool in self.mcp_manager.get_tools():
                self.tool_registry.register(tool)
                
            # Update system prompt with MCP status
            self._update_system_prompt_with_mcp_status()

    def _update_system_prompt_with_mcp_status(self):
        """Inject MCP connection status into the system prompt"""
        if not self.mcp_manager or not self.mcp_manager.connection_status:
            return
            
        status_lines = ["\nMCP Server Status:"]
        for name, status in self.mcp_manager.connection_status.items():
            status_lines.append(f"- {name}: {status}")
            
        status_text = "\n".join(status_lines)
        
        # Check if we already have a system message
        if self.conversation.messages and self.conversation.messages[0].role == MessageRole.SYSTEM:
            # Append to existing system message
            self.conversation.messages[0].content += f"\n\n{status_text}"
        else:
            # Create new system message
            base_prompt = self.config.system_prompt or "You are a helpful AI assistant."
            new_content = f"{base_prompt}\n\n{status_text}"
            system_msg = Message(role=MessageRole.SYSTEM, content=new_content)
            self.conversation.messages.insert(0, system_msg)

    async def cleanup(self):
        """Cleanup resources"""
        if self.mcp_manager:
            await self.mcp_manager.cleanup()

    async def create_new_session(self, title: Optional[str] = None) -> str:
        """Create a new chat session"""
        session = await self.session_manager.create_session(
            provider=self.config.provider.provider_type.value,
            model=self.config.provider.model,
            system_prompt=self.config.system_prompt,
            title=title,
            max_history=self.config.conversation_history_limit
        )

        # Use the session's conversation
        self.conversation = session.conversation

        return session.info.session_id

    async def load_session(self, session_id: str) -> bool:
        """Load an existing session"""
        session = await self.session_manager.load_session(session_id)
        if session:
            self.conversation = session.conversation
            return True
        return False

    async def save_current_session(self) -> bool:
        """Save the current session"""
        active_session = self.session_manager.get_active_session()
        if active_session:
            await self.session_manager.save_session(active_session)
            return True
        return False

    async def list_sessions(self) -> List[Dict[str, Any]]:
        """List all available sessions"""
        sessions = await self.session_manager.list_sessions()
        return [
            {
                "id": session.session_id,
                "title": session.title,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "provider": session.provider,
                "model": session.model,
                "message_count": session.message_count,
                "tags": session.tags
            }
            for session in sessions
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        return await self.session_manager.delete_session(session_id)

    async def export_session(self, session_id: str, format: str = "json") -> str:
        """Export a session"""
        return await self.session_manager.export_session(session_id, format)

    async def send_message(
        self,
        content: str,
        thinking_mode: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_tools: Optional[bool] = None,
    ) -> ChatResponse:
        """
        Send a message and get a response

        Args:
            content: Message content
            thinking_mode: Override default thinking mode setting
            tools: List of available tools (if None, uses built-in tools)
            enable_tools: Override default tool setting

        Returns:
            ChatResponse with content and any tool calls
        """
        # Determine thinking mode
        enable_thinking = thinking_mode if thinking_mode is not None else self.config.enable_thinking

        # Determine if tools should be enabled
        if enable_tools is not None:
            should_enable_tools = enable_tools
        else:
            # Use config setting if no explicit override
            should_enable_tools = (
                self.config.enable_tools and
                self.provider.supports_tool_calling() and
                (tools is not None or len(self.tool_registry.list_tools()) > 0)
            )

        # Prepare tools
        available_tools = tools
        if should_enable_tools and available_tools is None:
            # Use built-in tools
            available_tools = self.tool_registry.get_tool_schemas()
            # Convert to dict format for providers
            available_tools = [
                {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters
                }
                for schema in available_tools
            ]

        
        # Prepare message
        if enable_thinking:
            # Modify content to encourage thinking process
            modified_content = self._create_thinking_prompt(content)
        else:
            modified_content = content

        # Add user message to conversation
        user_msg = Message(role=MessageRole.USER, content=modified_content)
        self.conversation.add_message(user_msg)

        # Get messages for provider
        messages = self.conversation.get_messages_for_provider()

        try:
            # Send to provider
            if should_enable_tools and available_tools and self.provider.supports_tool_calling():
                response_data = await self.provider.create_message_with_tools(
                    messages=messages,
                    tools=available_tools,
                    max_tokens=self.config.provider.max_tokens,
                    temperature=self.config.provider.temperature,
                )
            else:
                response_content = await self.provider.create_message(
                    messages=messages,
                    max_tokens=self.config.provider.max_tokens,
                    temperature=self.config.provider.temperature,
                )
                response_data = {"content": response_content}

            # Process tool calls if any
            if response_data.get("tool_calls"):
                response_data = await self._handle_tool_calls(response_data)

            # Process response
            chat_response = self._process_response(response_data, enable_thinking)

            # Add assistant message to conversation
            assistant_msg = Message(
                role=MessageRole.ASSISTANT,
                content=chat_response.content,
                tool_calls=[tc.to_dict() for tc in chat_response.tool_calls] if chat_response.tool_calls else None,
            )
            self.conversation.add_message(assistant_msg)

            # Auto-save session if we have an active one
            await self.save_current_session()

            return chat_response

        except Exception as e:
            # Remove the user message if the request failed
            self.conversation.messages.pop()
            raise e

    async def stream_message(
        self,
        content: str,
        thinking_mode: Optional[bool] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        enable_tools: Optional[bool] = None,
    ) -> AsyncGenerator[ChatResponse, None]:
        """
        Send a message and stream the response

        Args:
            content: Message content
            thinking_mode: Override default thinking mode setting
            tools: List of available tools
            enable_tools: Override default tool setting

        Yields:
            ChatResponse chunks as they're generated
        """
        # Determine thinking mode
        enable_thinking = thinking_mode if thinking_mode is not None else self.config.enable_thinking

        # Determine if tools should be enabled
        if enable_tools is not None:
            should_enable_tools = enable_tools
        else:
            # Use config setting if no explicit override
            should_enable_tools = (
                self.config.enable_tools and
                self.provider.supports_tool_calling() and
                (tools is not None or len(self.tool_registry.list_tools()) > 0)
            )

        # Prepare tools
        available_tools = tools
        if should_enable_tools and available_tools is None:
            # Use built-in tools
            available_tools = self.tool_registry.get_tool_schemas()
            # Convert to dict format for providers
            available_tools = [
                {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters
                }
                for schema in available_tools
            ]

        
        # Prepare message
        if enable_thinking:
            modified_content = self._create_thinking_prompt(content)
        else:
            modified_content = content

        # Add user message to conversation
        user_msg = Message(role=MessageRole.USER, content=modified_content)
        self.conversation.add_message(user_msg)

        # Get messages for provider
        messages = self.conversation.get_messages_for_provider()

        accumulated_content = ""
        accumulated_tool_calls = {}
        current_tool_call = None

        try:
            if should_enable_tools and available_tools and self.provider.supports_tool_calling():
                # Stream with tools
                async for chunk_data in self.provider.stream_message_with_tools(
                    messages=messages,
                    tools=available_tools,
                    max_tokens=self.config.provider.max_tokens,
                    temperature=self.config.provider.temperature,
                ):

                    # Handle streaming tool calls
                    if "tool_call_start" in chunk_data:
                        current_tool_call = {
                            "id": chunk_data["tool_call_start"]["id"],
                            "name": chunk_data["tool_call_start"]["name"],
                            "arguments": "",
                            "arguments_json": ""
                        }
                        accumulated_tool_calls[current_tool_call["id"]] = current_tool_call

                    elif "tool_call_delta" in chunk_data and current_tool_call:
                        # Accumulate JSON arguments
                        current_tool_call["arguments_json"] += chunk_data["tool_call_delta"].get("partial_json", "")

                    elif "content" in chunk_data:
                        # Regular content chunk
                        response_chunk = ChatResponse(content=chunk_data["content"])
                        yield response_chunk
                        accumulated_content += chunk_data["content"]

                    # Handle stop signal - execute tool calls
                    elif chunk_data.get("stop", False):
                        # Execute all accumulated tool calls
                        for tool_id, tool_call in accumulated_tool_calls.items():
                            try:
                                # Parse the JSON arguments
                                import json
                                if tool_call["arguments_json"]:
                                    tool_call["arguments"] = json.loads(tool_call["arguments_json"])
                                else:
                                    tool_call["arguments"] = {}

                                # Execute the tool
                                result = await self.tool_executor.execute_by_name(
                                    self.tool_registry,
                                    tool_call["name"],
                                    tool_call["arguments"]
                                )

                                # Add tool result message to conversation
                                tool_result_msg = Message(
                                    role=MessageRole.TOOL,
                                    content=str(result.result) if result.success else f"Error: {result.error}",
                                    tool_call_id=tool_id,
                                )
                                self.conversation.add_message(tool_result_msg)

                                # Stream the tool result
                                result_text = str(result.result) if result.success else f"Error: {result.error}"
                                result_chunk = ChatResponse(content=result_text)
                                yield result_chunk
                                accumulated_content += result_text

                            except Exception as e:
                                error_text = f"Error executing {tool_call['name']}: {e}"
                                error_chunk = ChatResponse(content=error_text)
                                yield error_chunk
                                accumulated_content += error_text
                    else:
                        # Other chunk types
                        response_chunk = self._process_response(chunk_data, enable_thinking)
                        if response_chunk.content:
                            yield response_chunk
                            accumulated_content += response_chunk.content
            else:
                # Stream without tools
                async for content_chunk in self.provider.stream_message(
                    messages=messages,
                    max_tokens=self.config.provider.max_tokens,
                    temperature=self.config.provider.temperature,
                ):
                    accumulated_content += content_chunk
                    response_chunk = ChatResponse(content=content_chunk)
                    yield response_chunk

            # Add final assistant message to conversation
            # Convert tool calls to proper format
            tool_calls_list = []
            for tool_id, tool_call in accumulated_tool_calls.items():
                tool_calls_list.append({
                    "id": tool_id,
                    "name": tool_call["name"],
                    "arguments": tool_call["arguments"]
                })

            final_msg = Message(
                role=MessageRole.ASSISTANT,
                content=accumulated_content,
                tool_calls=tool_calls_list if tool_calls_list else None,
            )
            self.conversation.add_message(final_msg)

            # Auto-save session if we have an active one
            await self.save_current_session()

        except Exception as e:
            # Remove the user message if the request failed
            self.conversation.messages.pop()
            raise e

    def _create_thinking_prompt(self, content: str) -> str:
        """Create a prompt that encourages thinking mode"""
        return f"""Please think through this question step by step and provide your response in two distinct sections:

**THINKING PROCESS:**
First, show your step-by-step thinking process. Analyze the question carefully, consider different angles, break down the problem, and work through your reasoning. Be thorough in showing how you arrive at your conclusion.

**FINAL ANSWER:**
After your thinking process, provide your clear, direct answer to the user's question.

User's question: {content}

Please format your response exactly like this:

THINKING:
[Your detailed thinking process here]

RESPONSE:
[Your final answer here]"""

    def _process_response(self, response_data: Dict[str, Any], enable_thinking: bool) -> ChatResponse:
        """Process provider response into ChatResponse"""
        content = response_data.get("content", "")

        # Handle different tool call formats (streaming vs non-streaming)
        tool_calls_data = []

        # Non-streaming format
        if "tool_calls" in response_data:
            tool_calls_data = response_data.get("tool_calls", [])

        # Streaming format
        elif "tool_call_start" in response_data:
            # This is a streaming tool call start
            tool_calls_data.append({
                "id": response_data["tool_call_start"].get("id", ""),
                "name": response_data["tool_call_start"].get("name", ""),
                "arguments": {},  # Will be populated in subsequent chunks
            })
        elif "tool_call_delta" in response_data:
            # This is a streaming tool call argument delta
            # For now, we'll handle this in the streaming logic
            pass

        # Extract thinking if enabled
        thinking = None
        final_content = content

        if enable_thinking and content:
            thinking, final_content = self._parse_thinking_response(content)

        # Process tool calls
        tool_calls = []
        for tc_data in tool_calls_data:
            tool_call = ToolCall(
                id=tc_data.get("id", ""),
                name=tc_data.get("name", ""),
                arguments=tc_data.get("arguments", {}),
            )
            tool_calls.append(tool_call)

        return ChatResponse(
            content=final_content,
            tool_calls=tool_calls if tool_calls else None,
            thinking=thinking,
            model=response_data.get("model"),
            usage=response_data.get("usage"),
        )

    async def _handle_tool_calls(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle tool calls from AI response

        Args:
            response_data: Response data containing tool calls

        Returns:
            Updated response data with tool results
        """
        tool_calls = response_data.get("tool_calls", [])
        if not tool_calls:
            return response_data

        tool_results = []

        for tool_call in tool_calls:
            tool_name = tool_call.get("name")
            tool_args = tool_call.get("arguments", {})
            tool_id = tool_call.get("id", "")

            # Execute the tool
            result = await self.tool_executor.execute_by_name(
                self.tool_registry,
                tool_name,
                tool_args
            )

            # Add tool result message to conversation
            tool_result_msg = Message(
                role=MessageRole.TOOL,
                content=str(result.result) if result.success else f"Error: {result.error}",
                tool_call_id=tool_id,
            )
            self.conversation.add_message(tool_result_msg)

            tool_results.append({
                "tool_call_id": tool_id,
                "result": result.result if result.success else f"Error: {result.error}",
                "success": result.success
            })

        # Get updated messages for provider
        messages = self.conversation.get_messages_for_provider()

        # Send back to provider for final response
        final_response = await self.provider.create_message(
            messages=messages,
            max_tokens=self.config.provider.max_tokens,
            temperature=self.config.provider.temperature,
        )

        return {
            "content": final_response,
            "tool_calls": tool_calls,
            "tool_results": tool_results
        }

    def _parse_thinking_response(self, content: str) -> tuple[str, str]:
        """Parse thinking response into thinking and final answer"""
        thinking = ""
        response = ""

        # Try different separators
        separators = [
            "RESPONSE:",
            "FINAL ANSWER:",
            "ANSWER:",
            "\n\n",  # Double newline as fallback
        ]

        for sep in separators:
            if sep in content:
                parts = content.split(sep, 1)
                thinking = parts[0]
                response = parts[1] if len(parts) > 1 else ""
                # Clean up thinking section
                thinking = thinking.replace("THINKING:", "").replace("THINKING PROCESS:", "").strip()
                break

        # If no clear separation found, use the whole response as the answer
        if not thinking and not response:
            response = content
            thinking = ""

        return thinking, response

    def get_conversation_history(self) -> List[Message]:
        """Get the current conversation history"""
        return self.conversation.messages.copy()

    def clear_conversation(self) -> None:
        """Clear the conversation history"""
        self.conversation.clear()

        # Re-add system prompt if it exists
        if self.config.system_prompt:
            system_msg = Message(role=MessageRole.SYSTEM, content=self.config.system_prompt)
            self.conversation.add_message(system_msg)

    async def validate_provider(self) -> bool:
        """Validate that the provider connection works"""
        return await self.provider.validate_connection()

    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about the current model"""
        model_info = await self.provider.get_model_info(self.config.provider.model)
        return {
            "name": model_info.name,
            "max_tokens": model_info.max_tokens,
            "supports_streaming": model_info.supports_streaming,
            "supports_tools": model_info.supports_tools,
            "supports_thinking": model_info.supports_thinking,
            "context_window": model_info.context_window,
        }

    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools"""
        schemas = self.tool_registry.get_tool_schemas()
        # Remove duplicates by using a dictionary with tool names as keys
        unique_tools = {}
        for schema in schemas:
            if schema.name not in unique_tools:
                unique_tools[schema.name] = {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters
                }
        return list(unique_tools.values())

    def get_tool_execution_stats(self) -> Dict[str, Any]:
        """Get tool execution statistics"""
        return self.tool_executor.get_execution_stats()

    def register_custom_tool(self, tool) -> None:
        """Register a custom tool"""
        self.tool_registry.register(tool)

    def enable_tools(self, enable: bool = True) -> None:
        """Enable or disable tools for this chat engine"""
        self._tools_enabled = enable and self.provider.supports_tool_calling()

    def are_tools_enabled(self) -> bool:
        """Check if tools are enabled"""
        return getattr(self, '_tools_enabled', False) and self.provider.supports_tool_calling()