"""
Tool executor for AI Chat Console

Handles tool execution with timeout, error handling, and security measures.
"""

import asyncio
import traceback
from typing import Any, Dict, Optional
from datetime import datetime

from .base import BaseTool, ToolResult
from .registry import ToolRegistry


class ToolExecutor:
    """Executes tools with proper error handling and security"""

    def __init__(self, default_timeout: int = 30):
        """
        Initialize tool executor

        Args:
            default_timeout: Default timeout in seconds for tool execution
        """
        self.default_timeout = default_timeout
        self.execution_history = []

    async def execute(
        self,
        tool: BaseTool,
        arguments: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ToolResult:
        """
        Execute a tool with timeout and error handling

        Args:
            tool: Tool instance to execute
            arguments: Tool arguments
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with execution result
        """
        execution_start = datetime.now()
        timeout = timeout or self.default_timeout

        try:
            # Execute tool with timeout
            result = await asyncio.wait_for(
                tool.execute(**arguments),
                timeout=timeout
            )

            execution_time = (datetime.now() - execution_start).total_seconds()

            # Record execution
            self._record_execution(tool.name, arguments, result, execution_time, None)

            return result

        except asyncio.TimeoutError:
            error_msg = f"Tool execution timed out after {timeout} seconds"
            execution_time = (datetime.now() - execution_start).total_seconds()

            # Record failed execution
            failed_result = ToolResult(
                success=False,
                result=None,
                error=error_msg
            )
            self._record_execution(tool.name, arguments, failed_result, execution_time, "timeout")

            return failed_result

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            execution_time = (datetime.now() - execution_start).total_seconds()

            # Record failed execution
            failed_result = ToolResult(
                success=False,
                result=None,
                error=error_msg
            )
            self._record_execution(tool.name, arguments, failed_result, execution_time, type(e).__name__)

            return failed_result

    async def execute_by_name(
        self,
        registry: ToolRegistry,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[int] = None
    ) -> ToolResult:
        """
        Execute a tool by name using registry

        Args:
            registry: Tool registry to get tool from
            tool_name: Name of tool to execute
            arguments: Tool arguments
            timeout: Execution timeout in seconds

        Returns:
            ToolResult with execution result
        """
        tool = registry.get_tool(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                result=None,
                error=f"Tool '{tool_name}' not found in registry"
            )

        return await self.execute(tool, arguments, timeout)

    def _record_execution(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: ToolResult,
        execution_time: float,
        error_type: Optional[str]
    ) -> None:
        """
        Record tool execution for analytics and debugging

        Args:
            tool_name: Name of executed tool
            arguments: Arguments passed to tool
            result: Execution result
            execution_time: Time taken to execute
            error_type: Type of error if execution failed
        """
        execution_record = {
            "tool_name": tool_name,
            "arguments": arguments,
            "success": result.success,
            "execution_time": execution_time,
            "error_type": error_type,
            "timestamp": datetime.now().isoformat(),
            "error_message": result.error if not result.success else None
        }

        self.execution_history.append(execution_record)

        # Keep only last 100 executions to prevent memory bloat
        if len(self.execution_history) > 100:
            self.execution_history = self.execution_history[-100:]

    def get_execution_history(self) -> list:
        """Get the execution history"""
        return self.execution_history.copy()

    def clear_execution_history(self) -> None:
        """Clear the execution history"""
        self.execution_history.clear()

    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        if not self.execution_history:
            return {
                "total_executions": 0,
                "successful_executions": 0,
                "failed_executions": 0,
                "average_execution_time": 0,
                "most_used_tools": {}
            }

        total_executions = len(self.execution_history)
        successful_executions = sum(1 for record in self.execution_history if record["success"])
        failed_executions = total_executions - successful_executions

        execution_times = [record["execution_time"] for record in self.execution_history]
        average_execution_time = sum(execution_times) / len(execution_times)

        # Calculate most used tools
        tool_counts = {}
        for record in self.execution_history:
            tool_name = record["tool_name"]
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        return {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": successful_executions / total_executions * 100,
            "average_execution_time": average_execution_time,
            "most_used_tools": dict(sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5])
        }