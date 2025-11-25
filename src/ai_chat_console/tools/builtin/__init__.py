"""
Built-in tools for AI Chat Console

This package contains the default tools that are available
out-of-the-box for AI models to use.
"""

from .calculator import CalculatorTool
from .datetime_tool import DatetimeTool

# Register all built-in tools
BUILTIN_TOOLS = [
    CalculatorTool,
    DatetimeTool,
]

__all__ = [
    "CalculatorTool",
    "DatetimeTool",
    "BUILTIN_TOOLS",
]