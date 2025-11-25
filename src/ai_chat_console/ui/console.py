"""
Console UI for AI Chat Console

Provides the interactive chat interface with rich formatting and features.
"""

import asyncio
import os
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.table import Table

from ..core.chat import ChatEngine, ChatResponse
from ..config import AppConfig


class ConsoleUI:
    """Interactive console UI for chat"""

    def __init__(self, console: Console, chat_engine: ChatEngine, config: AppConfig):
        self.console = console
        self.chat_engine = chat_engine
        self.config = config

    async def start_interactive_chat(self) -> None:
        """Start the interactive chat session"""
        # Show welcome message
        self._show_welcome()

        # Validate provider connection
        try:
            if await self.chat_engine.validate_provider():
                self.console.print("[green]+ Connected to AI provider[/green]")
            else:
                self.console.print("[red]x Failed to connect to AI provider[/red]")
                return
        except Exception as e:
            self.console.print(f"[red]x Connection error: {e}[/red]")
            return

        # Main chat loop
        while True:
            try:
                # Get user input
                user_input = self._get_user_input()

                if not user_input:
                    continue

                # Handle special commands
                if user_input.lower() in ['quit', 'exit', 'q']:
                    self.console.print("[yellow]Goodbye![/yellow]")
                    break
                elif user_input.lower() in ['clear', 'cls']:
                    self.console.clear()
                    self._show_welcome()
                    continue
                elif user_input.lower() in ['help', 'h']:
                    self._show_help()
                    continue
                elif user_input.lower() in ['config', 'info']:
                    self._show_config_info()
                    continue
                elif user_input.lower() in ['clear-history', 'reset']:
                    self.chat_engine.clear_conversation()
                    self.console.print("[yellow]Conversation history cleared[/yellow]")
                    continue

                # Send message
                await self._send_message(user_input)

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Goodbye![/yellow]")
                break
            except EOFError:
                self.console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def _show_welcome(self) -> None:
        """Show welcome message"""
        welcome_text = f"""
[bold blue]AI Chat Console v0.1.0[/bold blue]

[dim]Provider:[/dim] {self.config.chat.provider.provider_type.value}
[dim]Model:[/dim] {self.config.chat.provider.model}
[dim]Streaming:[/dim] {'Enabled' if self.config.chat.enable_streaming else 'Disabled'}
[dim]Thinking Mode:[/dim] {'Enabled' if self.config.chat.enable_thinking else 'Disabled'}

[dim]Type 'help' for commands or start chatting![/dim]
"""
        self.console.print(Panel(welcome_text.strip(), border_style="blue"))

    def _show_help(self) -> None:
        """Show help information"""
        help_text = """
[bold]Available Commands:[/bold]

[yellow]help, h[/yellow]           - Show this help message
[yellow]quit, exit, q[/yellow]    - Exit the application
[yellow]clear, cls[/yellow]       - Clear the screen
[yellow]config, info[/yellow]     - Show current configuration
[yellow]clear-history, reset[/yellow] - Clear conversation history

[dim]Just type your message and press Enter to chat![/dim]
"""
        self.console.print(Panel(help_text.strip(), title="Help", border_style="yellow"))

    def _show_config_info(self) -> None:
        """Show current configuration"""
        config_table = Table(title="Configuration")
        config_table.add_column("Setting", style="bold")
        config_table.add_column("Value")

        config_table.add_row("Provider", self.config.chat.provider.provider_type.value)
        config_table.add_row("Model", self.config.chat.provider.model)
        config_table.add_row("Base URL", self.config.chat.provider.base_url)
        config_table.add_row("Streaming", str(self.config.chat.enable_streaming))
        config_table.add_row("Thinking Mode", str(self.config.chat.enable_thinking))
        config_table.add_row("Tools", str(self.config.chat.enable_tools))
        config_table.add_row("Max Tokens", str(self.config.chat.provider.max_tokens))
        config_table.add_row("Temperature", str(self.config.chat.provider.temperature))

        self.console.print(config_table)

    def _get_user_input(self) -> str:
        """Get user input with proper formatting"""
        return Prompt.ask("[bold blue]You[/bold blue]", default="", show_default=False)

    async def _send_message(self, user_input: str) -> None:
        """Send a message and display the response"""
        try:
            if self.config.chat.enable_streaming:
                await self._stream_response(user_input)
            else:
                await self._send_non_streaming(user_input)

        except Exception as e:
            self.console.print(f"[red]Error sending message: {e}[/red]")

    async def _stream_response(self, user_input: str) -> None:
        """Handle streaming response"""
        self.console.print("[bold green]Assistant:[/bold green] ", end="")

        full_response = ""
        thinking_displayed = False

        try:
            async for response_chunk in self.chat_engine.stream_message(user_input):
                if response_chunk.thinking and not thinking_displayed:
                    # Show thinking section
                    self.console.print()
                    self.console.print("[dim]<Thinking>:[/dim]")
                    self.console.print(f"[dim]{response_chunk.thinking}[/dim]")
                    self.console.print()
                    self.console.print("[bold green]Assistant:[/bold green] ", end="")
                    thinking_displayed = True

                if response_chunk.content:
                    self.console.print(response_chunk.content, end="")
                    full_response += response_chunk.content

            self.console.print()  # New line after response

        except Exception as e:
            self.console.print(f"\n[red]Streaming error: {e}[/red]")

    async def _send_non_streaming(self, user_input: str) -> None:
        """Handle non-streaming response"""
        try:
            response = await self.chat_engine.send_message(user_input)

            # Show thinking if present
            if response.thinking:
                self.console.print("[dim]<Thinking>:[/dim]")
                self.console.print(f"[dim]{response.thinking}[/dim]")
                self.console.print()

            # Show response
            self.console.print("[bold green]Assistant:[/bold green]")
            self.console.print(response.content)

        except Exception as e:
            self.console.print(f"[red]Error: {e}[/red]")

    def _format_content(self, content: str) -> None:
        """Format content with syntax highlighting for code blocks"""
        lines = content.split('\n')
        in_code_block = False
        code_language = ""
        code_content = []

        for line in lines:
            if line.strip().startswith('```'):
                if not in_code_block:
                    # Start of code block
                    in_code_block = True
                    code_language = line.strip()[3:].strip()
                    code_content = []
                else:
                    # End of code block
                    in_code_block = False
                    if code_content:
                        code_text = '\n'.join(code_content)
                        try:
                            syntax = Syntax(code_text, code_language or "text", theme="monokai", line_numbers=True)
                            self.console.print(syntax)
                        except Exception:
                            # Fallback to plain text if syntax highlighting fails
                            self.console.print(f"[dim]```{code_language}[/dim]")
                            for code_line in code_content:
                                self.console.print(f"[dim]{code_line}[/dim]")
                            self.console.print("[dim]```[/dim]")
                    else:
                        self.console.print(line)
            elif in_code_block:
                code_content.append(line)
            else:
                # Regular text - check for markdown formatting
                if line.strip().startswith('#'):
                    # Headers
                    self.console.print(f"[bold blue]{line}[/bold blue]")
                elif line.strip().startswith('-') or line.strip().startswith('*'):
                    # Lists
                    self.console.print(f"[green]{line}[/green]")
                else:
                    self.console.print(line)