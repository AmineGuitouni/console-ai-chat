"""
Tool registry for AI Chat Console

Manages tool registration, discovery, and execution.
"""

from typing import Dict, List, Optional, Type, Any
import asyncio
import importlib
import os
from pathlib import Path

from .base import BaseTool, ToolResult, ToolSchema


class ToolRegistry:
    """Registry for managing tools"""

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}
        self._tool_classes: Dict[str, Type[BaseTool]] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool instance

        Args:
            tool: Tool instance to register
        """
        tool_name = tool.name
        if tool_name in self._tools:
            print(f"Warning: Tool '{tool_name}' already registered, overwriting")

        self._tools[tool_name] = tool
        self._tool_classes[tool_name] = tool.__class__

    def register_class(self, tool_class: Type[BaseTool]) -> None:
        """
        Register a tool class (creates instance on demand)

        Args:
            tool_class: Tool class to register
        """
        # Create a temporary instance to get the name
        temp_instance = tool_class()
        tool_name = temp_instance.name
        self._tool_classes[tool_name] = tool_class

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """
        Get a tool instance by name

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        if name not in self._tools:
            # Try to create instance from registered class
            if name in self._tool_classes:
                self._tools[name] = self._tool_classes[name]()
            else:
                return None

        return self._tools[name]

    def get_tool_schemas(self) -> List[ToolSchema]:
        """
        Get all tool schemas

        Returns:
            List of all tool schemas
        """
        schemas = []
        processed_tools = set()

        # Add schemas from instantiated tools
        for name, tool in self._tools.items():
            schemas.append(tool.schema)
            processed_tools.add(name)

        # Add schemas from registered classes (instantiate temporarily)
        # Only if not already processed
        for name, tool_class in self._tool_classes.items():
            if name not in processed_tools:
                try:
                    temp_instance = tool_class()
                    schemas.append(temp_instance.schema)
                except Exception as e:
                    print(f"Warning: Failed to instantiate tool class {name} for schema: {e}")

        return schemas

    def list_tools(self) -> List[str]:
        """
        List all registered tool names

        Returns:
            List of tool names
        """
        # Return both instantiated tools and registered classes
        tool_names = set(self._tools.keys())
        tool_names.update(self._tool_classes.keys())
        return list(tool_names)

    def unregister(self, name: str) -> bool:
        """
        Unregister a tool

        Args:
            name: Tool name

        Returns:
            True if tool was unregistered, False if not found
        """
        if name in self._tools:
            del self._tools[name]
            if name in self._tool_classes:
                del self._tool_classes[name]
            return True
        return False

    async def load_tools_from_directory(self, directory: Path) -> int:
        """
        Load tools from a directory

        Args:
            directory: Directory containing tool modules

        Returns:
            Number of tools loaded
        """
        loaded_count = 0

        if not directory.exists():
            return 0

        for file_path in directory.glob("*.py"):
            if file_path.name.startswith("_"):
                continue  # Skip private modules

            try:
                # Load module dynamically
                module_name = file_path.stem
                spec = importlib.util.spec_from_file_location(module_name, str(file_path))
                module = importlib.util.module_from_spec(spec)

                # Look for tool classes in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        issubclass(attr, BaseTool) and
                        attr is not BaseTool):
                        self.register_class(attr)
                        loaded_count += 1

            except Exception as e:
                print(f"Warning: Failed to load tools from {file_path}: {e}")

        return loaded_count

    async def discover_and_load_builtin_tools(self) -> int:
        """
        Discover and load built-in tools

        Returns:
            Number of tools loaded
        """
        builtin_dir = Path(__file__).parent / "builtin"
        return await self.load_tools_from_directory(builtin_dir)

    async def discover_and_load_custom_tools(self, custom_directories: List[Path]) -> int:
        """
        Discover and load custom tools from directories

        Args:
            custom_directories: List of directories to search for tools

        Returns:
            Number of tools loaded
        """
        loaded_count = 0

        for directory in custom_directories:
            if directory.exists():
                loaded_count += await self.load_tools_from_directory(directory)

        return loaded_count

    async def execute_tool(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute a tool

        Args:
            name: Tool name
            arguments: Tool arguments

        Returns:
            ToolResult with execution result
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                result=None,
                error=f"Tool '{name}' not found"
            )

        # Validate parameters
        is_valid, error_message = tool.validate_parameters(arguments)
        if not is_valid:
            return ToolResult(
                success=False,
                result=None,
                error=error_message
            )

        # Execute the tool
        from .executor import ToolExecutor
        executor = ToolExecutor()
        return await executor.execute(tool, arguments)