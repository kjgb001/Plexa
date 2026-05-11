from __future__ import annotations

import re
from abc import ABC, abstractmethod

from plexa_server.models.message import Message
from plexa_server.models.session import Session


_WHITESPACE_RE = re.compile(r"\s+")


class SessionTitleGenerator(ABC):
    """Generate a persisted human-readable session title."""

    @abstractmethod
    async def generate_title(self, session: Session, first_user_message: Message) -> str | None:
        """Return a title for the supplied session, or `None` to defer."""


class DeterministicSessionTitleGenerator(SessionTitleGenerator):
    """Derive a stable session title directly from the first user message."""

    def __init__(self, max_words: int = 8, max_chars: int = 56):
        self._max_words = max_words
        self._max_chars = max_chars

    async def generate_title(self, session: Session, first_user_message: Message) -> str:
        content = _WHITESPACE_RE.sub(" ", first_user_message.content).strip()
        if not content:
            return default_session_title(session)

        first_line = content.splitlines()[0].strip()
        if not first_line:
            return default_session_title(session)

        words = first_line.split(" ")
        trimmed = " ".join(words[: self._max_words]).strip(" -:;,.!?")
        if not trimmed:
            return default_session_title(session)

        if len(trimmed) > self._max_chars:
            trimmed = trimmed[: self._max_chars].rstrip(" -:;,.!?")

        if len(words) > self._max_words or len(first_line) > len(trimmed):
            return f"{trimmed}..."
        return trimmed


def default_session_title(session: Session) -> str:
    """Return the initial placeholder title for a newly created session."""
    return f"New session {session.created_at.strftime('%b %d %I:%M %p')}"
