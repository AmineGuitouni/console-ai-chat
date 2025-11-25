"""
Command-line interface for AI Chat Console

Provides the main entry point and interactive chat interface.
"""

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from .config import AppConfig
from .providers.factory import ProviderFactory
from .core.chat import ChatEngine
from .ui.console import ConsoleUI


@click.group()
@click.version_option(version="0.1.0")
@click.option(
    "--config",
    "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file",
)
@click.option(
    "--log-level",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Set logging level",
)
@click.pass_context
def cli(ctx, config: Optional[Path], log_level: str):
    """AI Chat Console - Advanced AI console chat application"""
    # Ensure context object exists
    ctx.ensure_object(dict)

    # Load configuration
    # If no config file specified, look for default config.yaml
    if config is None:
        config_path = Path("config.yaml")
        if not config_path.exists():
            config_path = None
    else:
        config_path = config

    app_config = AppConfig.load(config_path)
    app_config.log_level = log_level

    # Store config in context
    ctx.obj["config"] = app_config
    ctx.obj["console"] = Console()


@cli.command()
@click.option(
    "--provider",
    type=click.Choice(["anthropic", "openai", "openrouter"]),
    help="Override provider type",
)
@click.option(
    "--model",
    help="Override model name",
)
@click.option(
    "--streaming/--no-streaming",
    default=None,
    help="Enable/disable streaming",
)
@click.option(
    "--thinking/--no-thinking",
    default=None,
    help="Enable/disable thinking mode",
)
@click.pass_context
def chat(ctx, provider: Optional[str], model: Optional[str], streaming: Optional[bool], thinking: Optional[bool]):
    """Start an interactive chat session"""
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    # Override config with command-line options
    if provider:
        from .config import ProviderType
        config.chat.provider.provider_type = ProviderType(provider)
    if model:
        config.chat.provider.model = model
    if streaming is not None:
        config.chat.enable_streaming = streaming
    if thinking is not None:
        config.chat.enable_thinking = thinking

    # Create chat session
    async def run_chat():
        chat_engine = None
        try:
            # Create provider
            provider = ProviderFactory.create_provider(config.chat.provider)

            # Create chat engine
            chat_engine = ChatEngine(provider, config.chat, config.mcp)
            
            # Initialize chat engine (connects to MCP servers)
            await chat_engine.initialize()

            # Create UI
            ui = ConsoleUI(console, chat_engine, config)

            # Start chat
            await ui.start_interactive_chat()

        except Exception as e:
            console.print(f"[red]Error starting chat: {e}[/red]")
            sys.exit(1)
        finally:
            if chat_engine:
                await chat_engine.cleanup()

    # Run the chat session
    asyncio.run(run_chat())


@cli.command()
@click.pass_context
def config_info(ctx):
    """Display current configuration"""
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    # Display configuration
    console.print(Panel.fit("Current Configuration", style="bold blue"))

    # Provider info
    console.print(f"[bold]Provider:[/bold] {config.chat.provider.provider_type.value}")
    console.print(f"[bold]Model:[/bold] {config.chat.provider.model}")
    console.print(f"[bold]Base URL:[/bold] {config.chat.provider.base_url}")
    console.print(f"[bold]Max Tokens:[/bold] {config.chat.provider.max_tokens}")
    console.print(f"[bold]Temperature:[/bold] {config.chat.provider.temperature}")

    console.print()

    # Chat settings
    console.print(f"[bold]Streaming:[/bold] {'Enabled' if config.chat.enable_streaming else 'Disabled'}")
    console.print(f"[bold]Thinking Mode:[/bold] {'Enabled' if config.chat.enable_thinking else 'Disabled'}")
    console.print(f"[bold]Tools:[/bold] {'Enabled' if config.chat.enable_tools else 'Disabled'}")
    console.print(f"[bold]History Limit:[/bold] {config.chat.conversation_history_limit}")

    if config.chat.system_prompt:
        console.print(f"[bold]System Prompt:[/bold] {config.chat.system_prompt}")

    console.print()

    # App settings
    console.print(f"[bold]Log Level:[/bold] {config.log_level}")
    console.print(f"[bold]Theme:[/bold] {config.theme}")


@cli.command()
@click.pass_context
def validate(ctx):
    """Validate provider connection and configuration"""
    config = ctx.obj["config"]
    console = ctx.obj["console"]

    async def run_validation():
        console.print("[bold]Validating configuration...[/bold]")

        try:
            # Create provider
            provider = ProviderFactory.create_provider(config.chat.provider)

            # Test connection
            console.print(f"[dim]Testing connection to {config.chat.provider.provider_type.value}...[/dim]")

            if await provider.validate_connection():
                console.print("[green]+ Connection successful[/green]")
            else:
                console.print("[red]x Connection failed[/red]")
                return

            # Get model info
            console.print(f"[dim]Getting model info for {config.chat.provider.model}...[/dim]")
            model_info = await provider.get_model_info(config.chat.provider.model)

            console.print(f"[green]+ Model: {model_info.name}[/green]")
            console.print(f"[dim]  Max tokens: {model_info.max_tokens}[/dim]")
            console.print(f"[dim]  Context window: {model_info.context_window}[/dim]")

            # Show model capabilities vs configuration
            console.print(f"[dim]  Streaming: {'Yes' if model_info.supports_streaming else 'No'} (model) / {'Enabled' if config.chat.enable_streaming else 'Disabled'} (config)[/dim]")
            console.print(f"[dim]  Tools: {'Yes' if model_info.supports_tools else 'No'} (model) / {'Enabled' if config.chat.enable_tools else 'Disabled'} (config)[/dim]")
            console.print(f"[dim]  Thinking: {'Yes' if model_info.supports_thinking else 'No'} (model) / {'Enabled' if config.chat.enable_thinking else 'Disabled'} (config)[/dim]")

            console.print("[green]+ Configuration is valid[/green]")

        except Exception as e:
            console.print(f"[red]x Validation failed: {e}[/red]")

    # Run the async validation
    import asyncio
    asyncio.run(run_validation())


@cli.command()
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file for config (default: config.yaml)",
)
def init_config(output: Optional[Path]):
    """Initialize a default configuration file"""
    console = Console()

    if output is None:
        output = Path("config.yaml")

    if output.exists():
        if not click.confirm(f"Config file {output} already exists. Overwrite?"):
            return

    # Create default config
    config = AppConfig()

    # Save to file
    config.save(output)

    console.print(f"[green]✓ Configuration saved to {output}[/green]")
    console.print("[dim]Edit the file to configure your API keys and preferences[/dim]")


def main():
    """Main entry point"""
    cli()


if __name__ == "__main__":
    main()