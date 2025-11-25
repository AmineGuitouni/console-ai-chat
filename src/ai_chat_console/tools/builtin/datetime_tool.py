"""
Datetime tool for AI Chat Console

Provides date and time operations.
"""

import datetime
from typing import Optional

from ..base import BaseTool, ToolParameter, ToolResult


class DatetimeTool(BaseTool):
    """Datetime tool for date and time operations"""

    @property
    def name(self) -> str:
        return "datetime"

    @property
    def description(self) -> str:
        return "Get current date and time, perform date calculations, and format dates"

    @property
    def parameters(self) -> list:
        return [
            ToolParameter(
                name="operation",
                type="string",
                description="Date operation to perform",
                required=True,
                enum=["now", "today", "format", "add_days", "subtract_days", "date_diff", "parse"]
            ),
            ToolParameter(
                name="date",
                type="string",
                description="Date string (for format, add_days, subtract_days, parse operations)",
                required=False
            ),
            ToolParameter(
                name="days",
                type="number",
                description="Number of days to add/subtract",
                required=False
            ),
            ToolParameter(
                name="format",
                type="string",
                description="Date format string (e.g., '%Y-%m-%d', '%d/%m/%Y')",
                required=False,
                default="%Y-%m-%d"
            ),
            ToolParameter(
                name="date2",
                type="string",
                description="Second date for date_diff operation",
                required=False
            )
        ]

    async def execute(self, **kwargs) -> ToolResult:
        """Execute the datetime operation"""
        try:
            operation = kwargs.get("operation")

            if operation == "now":
                now = datetime.datetime.now()
                return ToolResult(
                    success=True,
                    result={
                        "datetime": now.isoformat(),
                        "timestamp": now.timestamp(),
                        "formatted": {
                            "iso": now.isoformat(),
                            "readable": now.strftime("%A, %B %d, %Y %I:%M:%S %p"),
                            "date": now.strftime("%Y-%m-%d"),
                            "time": now.strftime("%H:%M:%S")
                        }
                    }
                )

            elif operation == "today":
                today = datetime.date.today()
                return ToolResult(
                    success=True,
                    result={
                        "date": today.isoformat(),
                        "year": today.year,
                        "month": today.month,
                        "day": today.day,
                        "weekday": today.strftime("%A"),
                        "formatted": today.strftime("%A, %B %d, %Y")
                    }
                )

            elif operation == "format":
                date_str = kwargs.get("date")
                format_str = kwargs.get("format", "%Y-%m-%d")

                if not date_str:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Date string is required for format operation"
                    )

                # Try to parse the date string first
                try:
                    # Try common date formats
                    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S"]:
                        try:
                            date_obj = datetime.datetime.strptime(date_str, fmt)
                            break
                        except ValueError:
                            continue
                    else:
                        # If no format matches, try ISO format
                        date_obj = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    return ToolResult(
                        success=False,
                        result=None,
                        error=f"Could not parse date string: {date_str}"
                    )

                formatted = date_obj.strftime(format_str)
                return ToolResult(
                    success=True,
                    result={
                        "original": date_str,
                        "formatted": formatted,
                        "format_used": format_str,
                        "iso_format": date_obj.isoformat()
                    }
                )

            elif operation == "add_days":
                date_str = kwargs.get("date")
                days = kwargs.get("days")

                if not date_str or days is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Date string and days are required for add_days operation"
                    )

                # Parse date
                try:
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    try:
                        date_obj = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        return ToolResult(
                            success=False,
                            result=None,
                            error=f"Could not parse date string: {date_str}"
                        )

                result_date = date_obj + datetime.timedelta(days=int(days))
                return ToolResult(
                    success=True,
                    result={
                        "original_date": date_str,
                        "days_added": int(days),
                        "result_date": result_date.strftime("%Y-%m-%d"),
                        "result_datetime": result_date.isoformat()
                    }
                )

            elif operation == "subtract_days":
                date_str = kwargs.get("date")
                days = kwargs.get("days")

                if not date_str or days is None:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Date string and days are required for subtract_days operation"
                    )

                # Parse date
                try:
                    date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d")
                except:
                    try:
                        date_obj = datetime.datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                    except:
                        return ToolResult(
                            success=False,
                            result=None,
                            error=f"Could not parse date string: {date_str}"
                        )

                result_date = date_obj - datetime.timedelta(days=int(days))
                return ToolResult(
                    success=True,
                    result={
                        "original_date": date_str,
                        "days_subtracted": int(days),
                        "result_date": result_date.strftime("%Y-%m-%d"),
                        "result_datetime": result_date.isoformat()
                    }
                )

            elif operation == "date_diff":
                date1_str = kwargs.get("date")
                date2_str = kwargs.get("date2")

                if not date1_str or not date2_str:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Two date strings are required for date_diff operation"
                    )

                # Parse dates
                try:
                    date1 = datetime.datetime.strptime(date1_str, "%Y-%m-%d")
                except:
                    try:
                        date1 = datetime.datetime.fromisoformat(date1_str.replace('Z', '+00:00'))
                    except:
                        return ToolResult(
                            success=False,
                            result=None,
                            error=f"Could not parse first date string: {date1_str}"
                        )

                try:
                    date2 = datetime.datetime.strptime(date2_str, "%Y-%m-%d")
                except:
                    try:
                        date2 = datetime.datetime.fromisoformat(date2_str.replace('Z', '+00:00'))
                    except:
                        return ToolResult(
                            success=False,
                            result=None,
                            error=f"Could not parse second date string: {date2_str}"
                        )

                diff = abs((date2 - date1).days)
                return ToolResult(
                    success=True,
                    result={
                        "date1": date1_str,
                        "date2": date2_str,
                        "days_difference": diff,
                        "weeks_difference": diff / 7,
                        "months_difference": diff / 30.44,  # Average month length
                        "years_difference": diff / 365.25
                    }
                )

            elif operation == "parse":
                date_str = kwargs.get("date")

                if not date_str:
                    return ToolResult(
                        success=False,
                        result=None,
                        error="Date string is required for parse operation"
                    )

                # Try to parse the date string
                parsed_formats = []
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"]:
                    try:
                        date_obj = datetime.datetime.strptime(date_str, fmt)
                        parsed_formats.append({
                            "format": fmt,
                            "datetime": date_obj.isoformat(),
                            "success": True
                        })
                    except ValueError:
                        continue

                if not parsed_formats:
                    return ToolResult(
                        success=False,
                        result=None,
                        error=f"Could not parse date string with any known format: {date_str}"
                    )

                return ToolResult(
                    success=True,
                    result={
                        "original": date_str,
                        "parsed_formats": parsed_formats,
                        "best_match": parsed_formats[0] if parsed_formats else None
                    }
                )

            else:
                return ToolResult(
                    success=False,
                    result=None,
                    error=f"Unknown operation: {operation}"
                )

        except Exception as e:
            return ToolResult(
                success=False,
                result=None,
                error=f"Datetime operation error: {str(e)}"
            )