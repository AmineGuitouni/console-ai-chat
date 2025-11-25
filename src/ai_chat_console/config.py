"""
Configuration management for AI Chat Console

Handles loading and managing configuration from environment variables,
config files, and command-line arguments.
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field


class ProviderType(Enum):
    """Supported AI provider types"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    OPENROUTER = "openrouter"


@dataclass
class ProviderConfig:
    """Configuration for a specific AI provider"""
    provider_type: ProviderType
    api_key: str
    base_url: Optional[str] = None
    model: str = "default"
    max_tokens: int = 1000
    supports_streaming: bool = True
    supports_tools: bool = False
    supports_thinking: bool = False
    temperature: float = 0.7

    @classmethod
    def from_env(cls, prefix: str) -> "ProviderConfig":
        """Create provider config from environment variables"""
        load_dotenv()

        provider_type = ProviderType(os.getenv(f"{prefix}_PROVIDER", "anthropic"))
        api_key = os.getenv(f"{prefix}_API_KEY", "")
        base_url = os.getenv(f"{prefix}_BASE_URL")
        model = os.getenv(f"{prefix}_MODEL", "default")
        max_tokens = int(os.getenv(f"{prefix}_MAX_TOKENS", "1000"))
        temperature = float(os.getenv(f"{prefix}_TEMPERATURE", "0.7"))

        # Set provider-specific defaults
        if provider_type == ProviderType.ANTHROPIC:
            if not base_url:
                base_url = "https://api.anthropic.com"
            if model == "default":
                model = "claude-3-5-sonnet-20241022"
            supports_tools = True
            supports_thinking = True
        elif provider_type == ProviderType.OPENAI:
            if not base_url:
                base_url = "https://api.openai.com/v1"
            if model == "default":
                model = "gpt-4"
            supports_tools = True
            supports_thinking = False
        elif provider_type == ProviderType.OPENROUTER:
            if not base_url:
                base_url = "https://openrouter.ai/api/v1"
            if model == "default":
                model = "anthicropic/claude-3.5-sonnet"
            supports_tools = True
            supports_thinking = False

        return cls(
            provider_type=provider_type,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            supports_streaming=True,
            supports_tools=supports_tools,
            supports_thinking=supports_thinking,
            temperature=temperature,
        )


@dataclass
class ChatConfig:
    """Configuration for the chat engine"""
    provider: ProviderConfig
    enable_streaming: bool = True
    enable_thinking: bool = False
    enable_tools: bool = True
    system_prompt: Optional[str] = None
    conversation_history_limit: int = 50

    @classmethod
    def from_env(cls) -> "ChatConfig":
        """Create chat config from environment variables"""
        load_dotenv()

        provider = ProviderConfig.from_env("AI")
        enable_streaming = os.getenv("ENABLE_STREAMING", "true").lower() in ["true", "1", "yes"]
        enable_thinking = os.getenv("ENABLE_THINKING", "false").lower() in ["true", "1", "yes"]
        enable_tools = os.getenv("ENABLE_TOOLS", "true").lower() in ["true", "1", "yes"]
        system_prompt = os.getenv("SYSTEM_PROMPT")
        conversation_history_limit = int(os.getenv("CONVERSATION_HISTORY_LIMIT", "50"))

        return cls(
            provider=provider,
            enable_streaming=enable_streaming,
            enable_thinking=enable_thinking,
            enable_tools=enable_tools,
            system_prompt=system_prompt,
            conversation_history_limit=conversation_history_limit,
        )


@dataclass
class MCPConfig:
    """Configuration for MCP (Model Context Protocol) servers"""
    servers: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_env(cls) -> "MCPConfig":
        """Create MCP config from environment variables"""
        load_dotenv()

        # For now, return empty config - will be expanded later
        return cls(servers=[])


@dataclass
class ToolConfig:
    """Configuration for tool system"""
    directories: List[str] = field(default_factory=list)
    enable_builtin: bool = True

    @classmethod
    def from_env(cls) -> "ToolConfig":
        """Create tool config from environment variables"""
        load_dotenv()

        directories_str = os.getenv("TOOL_DIRECTORIES", "")
        directories = [d.strip() for d in directories_str.split(",") if d.strip()]
        enable_builtin = os.getenv("ENABLE_BUILTIN_TOOLS", "true").lower() in ["true", "1", "yes"]

        return cls(
            directories=directories,
            enable_builtin=enable_builtin,
        )


@dataclass
class AppConfig:
    """Main application configuration"""
    chat: ChatConfig = field(default_factory=ChatConfig.from_env)
    mcp: MCPConfig = field(default_factory=MCPConfig.from_env)
    tools: ToolConfig = field(default_factory=ToolConfig.from_env)
    log_level: str = "INFO"
    theme: str = "default"
    config_file: Optional[Path] = None

    @classmethod
    def load(cls, config_file: Optional[Path] = None) -> "AppConfig":
        """Load configuration from file and environment variables"""
        load_dotenv()

        # If config file exists, load from it first
        if config_file and config_file.exists():
            config = cls._load_from_file(config_file)
        else:
            # Start with environment-based config as fallback
            config = cls()
            config.chat = ChatConfig.from_env()
            config.mcp = MCPConfig.from_env()
            config.tools = ToolConfig.from_env()

        config.config_file = config_file

        # Override specific settings with environment variables (but not the entire config)
        if os.getenv("LOG_LEVEL"):
            config.log_level = os.getenv("LOG_LEVEL")
        if os.getenv("THEME"):
            config.theme = os.getenv("THEME")

        return config

    @classmethod
    def _load_from_file(cls, config_file: Path) -> "AppConfig":
        """Load configuration from YAML file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            # Convert dict to config objects
            chat_data = data.get('chat', {})
            provider_data = chat_data.get('provider', {})

            provider = ProviderConfig(
                provider_type=ProviderType(provider_data.get('type', 'anthropic')),
                api_key=provider_data.get('api_key', ''),
                base_url=provider_data.get('base_url'),
                model=provider_data.get('model', 'default'),
                max_tokens=provider_data.get('max_tokens', 1000),
                temperature=provider_data.get('temperature', 0.7),
                supports_streaming=provider_data.get('supports_streaming', True),
                supports_tools=provider_data.get('supports_tools', False),
                supports_thinking=provider_data.get('supports_thinking', False),
            )

            chat = ChatConfig(
                provider=provider,
                enable_streaming=chat_data.get('enable_streaming', True),
                enable_thinking=chat_data.get('enable_thinking', False),
                enable_tools=chat_data.get('enable_tools', True),
                system_prompt=chat_data.get('system_prompt'),
                conversation_history_limit=chat_data.get('conversation_history_limit', 50),
            )

            mcp = MCPConfig(
                servers=data.get('mcp', {}).get('servers', [])
            )

            tools = ToolConfig(
                directories=data.get('tools', {}).get('directories', []),
                enable_builtin=data.get('tools', {}).get('enable_builtin', True),
            )

            return cls(
                chat=chat,
                mcp=mcp,
                tools=tools,
                log_level=data.get('log_level', 'INFO'),
                theme=data.get('theme', 'default'),
                config_file=config_file,
            )

        except Exception as e:
            print(f"Warning: Failed to load config file {config_file}: {e}")
            return cls()

    def save(self, config_file: Optional[Path] = None) -> None:
        """Save configuration to YAML file"""
        file_path = config_file or self.config_file
        if not file_path:
            raise ValueError("No config file specified")

        # Convert config objects to dict
        data = {
            'chat': {
                'enable_streaming': self.chat.enable_streaming,
                'enable_thinking': self.chat.enable_thinking,
                'enable_tools': self.chat.enable_tools,
                'system_prompt': self.chat.system_prompt,
                'conversation_history_limit': self.chat.conversation_history_limit,
                'provider': {
                    'type': self.chat.provider.provider_type.value,
                    'api_key': self.chat.provider.api_key,
                    'base_url': self.chat.provider.base_url,
                    'model': self.chat.provider.model,
                    'max_tokens': self.chat.provider.max_tokens,
                    'temperature': self.chat.provider.temperature,
                    'supports_streaming': self.chat.provider.supports_streaming,
                    'supports_tools': self.chat.provider.supports_tools,
                    'supports_thinking': self.chat.provider.supports_thinking,
                }
            },
            'mcp': {
                'servers': self.mcp.servers
            },
            'tools': {
                'directories': self.tools.directories,
                'enable_builtin': self.tools.enable_builtin,
            },
            'log_level': self.log_level,
            'theme': self.theme,
        }

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, indent=2)