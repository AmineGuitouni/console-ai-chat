"""
Chat session management for AI Chat Console

Handles conversation persistence, session management, and conversation history.
"""

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field

from .conversation import Conversation
from ..providers.base import Message, MessageRole


@dataclass
class SessionInfo:
    """Session metadata"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    provider: str
    model: str
    message_count: int
    tags: List[str] = field(default_factory=list)


@dataclass
class ChatSession:
    """Complete chat session with metadata"""
    info: SessionInfo
    conversation: Conversation

    def to_dict(self) -> Dict[str, Any]:
        """Convert session to dictionary for serialization"""
        return {
            "info": asdict(self.info),
            "conversation": {
                "messages": [msg.to_dict() for msg in self.conversation.messages],
                "max_history": self.conversation.max_history,
                "system_prompt": self.conversation.system_prompt,
            }
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChatSession":
        """Create session from dictionary"""
        info_data = data["info"]
        info = SessionInfo(**info_data)

        conv_data = data["conversation"]
        messages = [Message.from_dict(msg) for msg in conv_data["messages"]]
        conversation = Conversation(
            messages=messages,
            max_history=conv_data.get("max_history", 50),
            system_prompt=conv_data.get("system_prompt"),
        )

        return cls(info=info, conversation=conversation)


class SessionManager:
    """Manager for chat sessions"""

    def __init__(self, sessions_dir: Path = None):
        if sessions_dir is None:
            sessions_dir = Path.home() / ".ai-chat-console" / "sessions"

        self.sessions_dir = sessions_dir
        self.sessions_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_cache: Dict[str, ChatSession] = {}
        self._active_session: Optional[str] = None

    async def create_session(
        self,
        provider: str,
        model: str,
        system_prompt: Optional[str] = None,
        title: Optional[str] = None,
        max_history: int = 50
    ) -> ChatSession:
        """Create a new chat session"""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()

        if title is None:
            title = f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        info = SessionInfo(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            provider=provider,
            model=model,
            message_count=0
        )

        conversation = Conversation(
            max_history=max_history,
            system_prompt=system_prompt
        )

        session = ChatSession(info=info, conversation=conversation)

        # Store in cache
        self._sessions_cache[session_id] = session

        # Set as active session
        self._active_session = session_id

        # Save to disk
        await self.save_session(session)

        return session

    async def load_session(self, session_id: str) -> Optional[ChatSession]:
        """Load a session from disk"""
        if session_id in self._sessions_cache:
            return self._sessions_cache[session_id]

        session_file = self.sessions_dir / f"{session_id}.json"
        if not session_file.exists():
            return None

        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            session = ChatSession.from_dict(data)
            self._sessions_cache[session_id] = session
            return session

        except Exception as e:
            print(f"Error loading session {session_id}: {e}")
            return None

    async def save_session(self, session: ChatSession) -> None:
        """Save a session to disk"""
        session_file = self.sessions_dir / f"{session.info.session_id}.json"

        # Update metadata
        session.info.updated_at = datetime.now().isoformat()
        session.info.message_count = len(session.conversation.messages)

        try:
            with open(session_file, 'w', encoding='utf-8') as f:
                json.dump(session.to_dict(), f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving session {session.info.session_id}: {e}")

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        session_file = self.sessions_dir / f"{session_id}.json"

        try:
            if session_file.exists():
                session_file.unlink()

            if session_id in self._sessions_cache:
                del self._sessions_cache[session_id]

            if self._active_session == session_id:
                self._active_session = None

            return True

        except Exception as e:
            print(f"Error deleting session {session_id}: {e}")
            return False

    async def list_sessions(self) -> List[SessionInfo]:
        """List all available sessions"""
        sessions = []

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                with open(session_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                info = SessionInfo(**data["info"])
                sessions.append(info)

            except Exception as e:
                print(f"Error reading session {session_file.name}: {e}")
                continue

        # Sort by updated_at (most recent first)
        sessions.sort(key=lambda x: x.updated_at, reverse=True)
        return sessions

    def get_active_session(self) -> Optional[ChatSession]:
        """Get the currently active session"""
        if self._active_session and self._active_session in self._sessions_cache:
            return self._sessions_cache[self._active_session]
        return None

    async def set_active_session(self, session_id: str) -> bool:
        """Set the active session"""
        session = await self.load_session(session_id)
        if session:
            self._active_session = session_id
            return True
        return False

    async def update_session_title(self, session_id: str, title: str) -> bool:
        """Update session title"""
        session = await self.load_session(session_id)
        if not session:
            return False

        session.info.title = title
        session.info.updated_at = datetime.now().isoformat()
        await self.save_session(session)
        return True

    async def add_tag(self, session_id: str, tag: str) -> bool:
        """Add a tag to a session"""
        session = await self.load_session(session_id)
        if not session:
            return False

        if tag not in session.info.tags:
            session.info.tags.append(tag)
            session.info.updated_at = datetime.now().isoformat()
            await self.save_session(session)
        return True

    async def remove_tag(self, session_id: str, tag: str) -> bool:
        """Remove a tag from a session"""
        session = await self.load_session(session_id)
        if not session:
            return False

        if tag in session.info.tags:
            session.info.tags.remove(tag)
            session.info.updated_at = datetime.now().isoformat()
            await self.save_session(session)
        return True

    async def cleanup_old_sessions(self, max_age_days: int = 30) -> int:
        """Clean up old sessions"""
        cutoff_time = datetime.now().timestamp() - (max_age_days * 24 * 3600)
        deleted_count = 0

        for session_file in self.sessions_dir.glob("*.json"):
            try:
                file_age = session_file.stat().st_mtime
                if file_age < cutoff_time:
                    session_file.unlink()
                    deleted_count += 1

                    # Remove from cache if present
                    session_id = session_file.stem
                    if session_id in self._sessions_cache:
                        del self._sessions_cache[session_id]
                    if self._active_session == session_id:
                        self._active_session = None

            except Exception as e:
                print(f"Error cleaning up session {session_file.name}: {e}")
                continue

        return deleted_count

    async def export_session(self, session_id: str, format: str = "json") -> str:
        """Export session in various formats"""
        session = await self.load_session(session_id)
        if not session:
            return ""

        if format.lower() == "json":
            return json.dumps(session.to_dict(), indent=2, ensure_ascii=False)

        elif format.lower() == "text":
            lines = []
            lines.append(f"Session: {session.info.title}")
            lines.append(f"Created: {session.info.created_at}")
            lines.append(f"Provider: {session.info.provider} ({session.info.model})")
            lines.append(f"Messages: {session.info.message_count}")
            lines.append("")

            for message in session.conversation.messages:
                role_prefix = {
                    MessageRole.SYSTEM: "System",
                    MessageRole.USER: "You",
                    MessageRole.ASSISTANT: "Assistant",
                    MessageRole.TOOL: "Tool"
                }.get(message.role, message.role.value)

                lines.append(f"{role_prefix}: {message.content}")
                lines.append("")

            return "\n".join(lines)

        elif format.lower() == "markdown":
            lines = []
            lines.append(f"# {session.info.title}")
            lines.append("")
            lines.append(f"**Created:** {session.info.created_at}")
            lines.append(f"**Provider:** {session.info.provider} ({session.info.model})")
            lines.append(f"**Messages:** {session.info.message_count}")
            lines.append("")

            if session.info.tags:
                lines.append(f"**Tags:** {', '.join(session.info.tags)}")
                lines.append("")

            for message in session.conversation.messages:
                if message.role == MessageRole.USER:
                    lines.append(f"## You")
                    lines.append("")
                    lines.append(message.content)
                    lines.append("")
                elif message.role == MessageRole.ASSISTANT:
                    lines.append(f"## Assistant")
                    lines.append("")
                    lines.append(message.content)
                    lines.append("")

            return "\n".join(lines)

        return ""