"""
Base tool interface for AI Chat Console

Defines the abstract interface that all tools must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Parameter for a tool"""
    name: str = Field(description="Parameter name")
    type: str = Field(description="Parameter type (string, number, boolean, array, object)")
    description: str = Field(description="Parameter description")
    required: bool = Field(default=False, description="Whether this parameter is required")
    default: Any = Field(None, description="Default value for this parameter")
    enum: Optional[List[str]] = Field(None, description="List of allowed values (for enum type)")


class ToolSchema(BaseModel):
    """Schema for a tool definition"""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    parameters: Dict[str, Any] = Field(description="JSON schema for tool parameters")


class ToolResult(BaseModel):
    """Result of a tool execution"""
    success: bool = Field(description="Whether the tool execution was successful")
    result: Any = Field(description="The result of the tool execution")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class BaseTool(ABC):
    """Abstract base class for all tools"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Get the tool name"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get the tool description"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> ToolParameter:
        """Get tool parameters"""
        pass

    @property
    def schema(self) -> ToolSchema:
        """Get the tool schema"""
        # Handle both single parameter and list of parameters
        if isinstance(self.parameters, list):
            properties = {}
            required = []

            for param in self.parameters:
                properties[param.name] = {
                    "type": param.type,
                    "description": param.description,
                    "default": param.default,
                    "enum": param.enum,
                }
                if param.required:
                    required.append(param.name)
        else:
            # Single parameter
            param = self.parameters
            if param:
                properties = {
                    param.name: {
                        "type": param.type,
                        "description": param.description,
                        "default": param.default,
                        "enum": param.enum,
                    }
                }
                required = [param.name] if param.required else []
            else:
                properties = {}
                required = []

        return ToolSchema(
            name=self.name,
            description=self.description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            }
        )

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        """
        Execute the tool

        Args:
            **kwargs: Tool arguments

        Returns:
            ToolResult with the execution result
        """
        pass

    def validate_parameters(self, arguments: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate tool arguments against the schema

        Args:
            arguments: Tool arguments to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Get all required parameters
            required_params = []
            if isinstance(self.parameters, list):
                for param in self.parameters:
                    if param.required:
                        required_params.append(param.name)
            else:
                if self.parameters.required:
                    required_params.append(self.parameters.name)

            # Check required parameters
            for param in required_params:
                if param not in arguments:
                    return False, f"Missing required parameter: {param}"

            # Validate parameter types and values
            if isinstance(self.parameters, list):
                for param in self.parameters:
                    if param.name in arguments:
                        value = arguments[param.name]
                        if not self._validate_parameter_type(param, value):
                            return False, f"Invalid value for parameter {param.name}: {value}"

            return True, None

        except Exception as e:
            return False, f"Parameter validation error: {e}"

    def _validate_parameter_type(self, param: ToolParameter, value: Any) -> bool:
        """Validate a single parameter value"""
        if param.enum and value not in param.enum:
            return False

        try:
            if param.type == "string":
                return isinstance(value, str)
            elif param.type == "number":
                return isinstance(value, (int, float))
            elif param.type == "boolean":
                return isinstance(value, bool)
            elif param.type == "array":
                return isinstance(value, list)
            elif param.type == "object":
                return isinstance(value, dict)
            return True
        except:
            return False