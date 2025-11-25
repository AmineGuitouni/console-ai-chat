"""
Calculator tool for AI Chat Console

Provides basic mathematical operations.
"""

import math
from typing import Union

from ..base import BaseTool, ToolParameter, ToolResult


class CalculatorTool(BaseTool):
    """Basic calculator tool for mathematical operations"""

    @property
    def name(self) -> str:
        return "calculator"

    @property
    def description(self) -> str:
        return "Perform basic mathematical operations (add, subtract, multiply, divide, power, sqrt, sin, cos, tan)"

    @property
    def parameters(self) -> list:
        return [
            ToolParameter(
                name="operation",
                type="string",
                description="Mathematical operation to perform",
                required=True,
                enum=["add", "subtract", "multiply", "divide", "power", "sqrt", "sin", "cos", "tan", "log", "abs"]
            ),
            ToolParameter(
                name="a",
                type="number",
                description="First number",
                required=True
            ),
            ToolParameter(
                name="b",
                type="number",
                description="Second number (not required for sqrt, sin, cos, tan, log, abs)",
                required=False
            )
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the calculator operation"""
        try:
            operation = kwargs.get("operation")
            a = kwargs.get("a")
            b = kwargs.get("b")

            if operation is None or a is None:
                return ToolResult(
                    success=False,
                    result=None,
                    error="Missing required parameters: operation and a"
                )

            # Convert to float for calculations
            a = float(a)
            if b is not None:
                b = float(b)

            result = None

            if operation == "add":
                if b is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Add operation requires two numbers"
                    )
                result = a + b

            elif operation == "subtract":
                if b is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Subtract operation requires two numbers"
                    )
                result = a - b

            elif operation == "multiply":
                if b is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Multiply operation requires two numbers"
                    )
                result = a * b

            elif operation == "divide":
                if b is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Divide operation requires two numbers"
                    )
                if b == 0:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Division by zero is not allowed"
                    )
                result = a / b

            elif operation == "power":
                if b is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Power operation requires two numbers"
                    )
                result = a ** b

            elif operation == "sqrt":
                if a < 0:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Cannot calculate square root of negative number"
                    )
                result = math.sqrt(a)

            elif operation == "sin":
                result = math.sin(math.radians(a))

            elif operation == "cos":
                result = math.cos(math.radians(a))

            elif operation == "tan":
                result = math.tan(math.radians(a))

            elif operation == "log":
                if a <= 0:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Cannot calculate logarithm of non-positive number"
                    )
                if b is None:
                    # Natural logarithm
                    result = math.log(a)
                else:
                    if b <= 0 or b == 1:
                        return ToolResult(
                            success=False,
                            result=None,
                            error="Logarithm base must be positive and not equal to 1"
                        )
                    result = math.log(a, b)

            elif operation == "abs":
                result = abs(a)

            else:
                return ToolResult(
                    success=False,
                    result=None,
                    error=f"Unknown operation: {operation}"
                )

            # Format result nicely
            if isinstance(result, float) and result.is_integer():
                result = int(result)

            return ToolResult(
                success=True,
                result=result,
                metadata={"operation": operation, "input_a": a, "input_b": b}
            )

        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=f"Calculation error: {str(e)}"
            )