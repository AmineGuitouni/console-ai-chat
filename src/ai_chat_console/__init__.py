"""
AI Chat Console - Advanced AI console chat application

An advanced console-based AI chat application with multi-provider support,
tool calling, MCP integration, and extensible plugin system.
"""

__version__ = "0.1.0"
__author__ = "AI Chat Console Team"
__description__ = "Advanced AI console chat application"

from .config import AppConfig, ProviderConfig, ChatConfig
from .core.chat import ChatEngine
from .providers.base import BaseProvider

__all__ = [
    "AppConfig",
    "ProviderConfig",
    "ChatConfig",
    "ChatEngine",
    "BaseProvider",
]