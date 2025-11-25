"""
MCP Manager

Manages connections to MCP servers and exposes their tools.
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from contextlib import AsyncExitStack, asynccontextmanager

import httpx
import anyio
import mcp.types as types
from mcp import ClientSession
from mcp.shared.message import SessionMessage
from mcp.client.sse import sse_client
from mcp.client.stdio import stdio_client, StdioServerParameters

from ..config import MCPConfig
from ..tools.base import BaseTool
from .tool import MCPTool

logger = logging.getLogger(__name__)

@asynccontextmanager
async def stateless_http_client(
    url: str,
    headers: Dict[str, Any] = None,
    timeout: float = 30.0
):
    """
    Custom transport for stateless HTTP MCP servers (like Context7).
    Sends requests via POST and expects responses in the HTTP response body.
    """
    read_stream_writer, read_stream = anyio.create_memory_object_stream(0)
    write_stream, write_stream_reader = anyio.create_memory_object_stream(0)
    
    headers = headers or {}
    # Ensure we accept both JSON and SSE (as required by Context7)
    if "Accept" not in headers:
        headers["Accept"] = "application/json, text/event-stream"
    if "Content-Type" not in headers:
        headers["Content-Type"] = "application/json"

    async with httpx.AsyncClient(timeout=timeout) as client:
        async def writer_loop():
            async with write_stream_reader:
                async for session_message in write_stream_reader:
                    try:
                        # Convert message to JSON
                        json_data = session_message.message.model_dump(
                            by_alias=True,
                            mode="json",
                            exclude_none=True,
                        )
                        
                        # Send POST request
                        response = await client.post(
                            url, 
                            json=json_data, 
                            headers=headers
                        )
                        response.raise_for_status()
                        
                        # Parse response
                        response_data = response.json()
                        message = types.JSONRPCMessage.model_validate(response_data)
                        
                        # Send back to read stream
                        await read_stream_writer.send(SessionMessage(message))
                        
                    except Exception as e:
                        logger.error(f"Error in stateless HTTP transport: {e}")
                        # We might want to propagate error or reconnect?
                        # For now, just log it.
                        pass
        
        async with anyio.create_task_group() as tg:
            tg.start_soon(writer_loop)
            
            try:
                yield read_stream, write_stream
            finally:
                tg.cancel_scope.cancel()
                await read_stream_writer.aclose()
                await write_stream.aclose()

class MCPManager:
    """Manages MCP server connections and tools"""

    def __init__(self, config: MCPConfig):
        self.config = config
        self.sessions: Dict[str, ClientSession] = {}
        self.exit_stack = AsyncExitStack()
        self._tools: Dict[str, BaseTool] = {}
        self._initialized = False
        self.connection_status: Dict[str, str] = {}

    async def initialize(self):
        """Initialize connections to all configured MCP servers"""
        if self._initialized:
            return

        for server_config in self.config.servers:
            name = server_config.get("name", "unknown")
            url = server_config.get("url")
            command = server_config.get("command")
            
            if not url and not command:
                continue
                
            try:
                self.connection_status[name] = "connecting"
                
                async def connect_to_server():
                    if command:
                        print(f"Starting MCP server: {name} ({command})...")
                        args = server_config.get("args", [])
                        env = server_config.get("env")
                        
                        server_params = StdioServerParameters(
                            command=command,
                            args=args,
                            env=env
                        )
                        
                        read, write = await self.exit_stack.enter_async_context(
                            stdio_client(server_params)
                        )
                    else:
                        print(f"Connecting to MCP server: {name} ({url})...")
                        headers = server_config.get("headers", {})
                        
                        # Check if this is Context7 or similar stateless HTTP server
                        # We can detect it by name or try to probe, but for now let's assume
                        # if it's context7, we use the stateless transport.
                        if "context7" in name.lower() or "context7" in url.lower():
                            print(f"Using stateless HTTP transport for {name}")
                            read, write = await self.exit_stack.enter_async_context(
                                stateless_http_client(url=url, headers=headers)
                            )
                        else:
                            # Start SSE client
                            # We use timeout=None to prevent read timeouts on the SSE stream
                            # as it can be idle for long periods.
                            read, write = await self.exit_stack.enter_async_context(
                                sse_client(url=url, headers=headers, timeout=None)
                            )
                    
                    # Start session
                    session = await self.exit_stack.enter_async_context(
                        ClientSession(read, write)
                    )
                    
                    await session.initialize()
                    return session

                try:
                    # We still keep a connection timeout for the initial handshake
                    # but increase it significantly to 30s
                    session = await asyncio.wait_for(connect_to_server(), timeout=30.0)
                    self.sessions[name] = session
                    self.connection_status[name] = "connected"
                    
                    # List tools
                    result = await session.list_tools()
                    for tool_def in result.tools:
                        # Wrap as BaseTool
                        tool = MCPTool(session, tool_def)
                        self._tools[tool.name] = tool
                        print(f"  - Registered MCP tool: {tool.name}")
                        
                except asyncio.TimeoutError:
                    print(f"Timeout connecting to MCP server {name} (exceeded 30s)")
                    self.connection_status[name] = "timeout"
                except TypeError:
                    # Fallback if sse_client doesn't accept timeout arg
                    # We retry without timeout arg
                    if command:
                        raise # stdio_client doesn't have this issue
                        
                    async def connect_fallback():
                        headers = server_config.get("headers", {})
                        read, write = await self.exit_stack.enter_async_context(
                            sse_client(url=url, headers=headers)
                        )
                        session = await self.exit_stack.enter_async_context(
                            ClientSession(read, write)
                        )
                        await session.initialize()
                        return session
                        
                    session = await asyncio.wait_for(connect_fallback(), timeout=30.0)
                    self.sessions[name] = session
                    self.connection_status[name] = "connected"
                    
                    # List tools
                    result = await session.list_tools()
                    for tool_def in result.tools:
                        tool = MCPTool(session, tool_def)
                        self._tools[tool.name] = tool
                        print(f"  - Registered MCP tool: {tool.name}")

            except Exception as e:
                print(f"Failed to connect to MCP server {name}: {e}")
                self.connection_status[name] = f"failed: {str(e)}"
                # Don't fail the whole app if one server fails
                
        self._initialized = True
                
        self._initialized = True

    async def cleanup(self):
        """Close all connections"""
        await self.exit_stack.aclose()
        self.sessions.clear()
        self._tools.clear()
        self._initialized = False
        
    def get_tools(self) -> List[BaseTool]:
        """Get all registered MCP tools"""
        return list(self._tools.values())
