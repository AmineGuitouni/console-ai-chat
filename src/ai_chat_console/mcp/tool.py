"""
MCP Tool Adapter

Wraps an MCP tool as a BaseTool for the chat console.
"""

from typing import Any, Dict, List, Optional
from mcp import ClientSession
from mcp.types import Tool as MCPToolType

from ..tools.base import BaseTool, ToolParameter, ToolResult


class MCPTool(BaseTool):
    """Adapter for MCP tools"""

    def __init__(self, session: ClientSession, tool_def: MCPToolType):
        self._session = session
        self._tool_def = tool_def
        self._parameters = self._parse_parameters()

    @property
    def name(self) -> str:
        return self._tool_def.name

    @property
    def description(self) -> str:
        return self._tool_def.description or ""

    @property
    def parameters(self) -> List[ToolParameter]:
        return self._parameters

    def _parse_parameters(self) -> List[ToolParameter]:
        """Parse JSON schema parameters into ToolParameter objects"""
        schema = self._tool_def.inputSchema
        if not schema or "properties" not in schema:
            return []

        params = []
        required_set = set(schema.get("required", []))
        
        for name, prop in schema["properties"].items():
            params.append(ToolParameter(
                name=name,
                type=prop.get("type", "string"),
                description=prop.get("description", ""),
                required=name in required_set,
                default=prop.get("default"),
                enum=prop.get("enum")
            ))
            
        return params

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the tool via MCP session"""
        result = await self._session.call_tool(self.name, arguments=kwargs)
        
        # Format result
        content = []
        is_error = result.isError if hasattr(result, "isError") else False
        
        if hasattr(result, "content"):
            for item in result.content:
                if hasattr(item, "text"):
                    content.append(item.text)
                elif hasattr(item, "type") and item.type == "text":
                    content.append(item.text)
                else:
                    content.append(str(item))
        
        output = "\n".join(content)
        
        return ToolResult(
            success=not is_error,
            result=output,
            error=output if is_error else None
        )
