from __future__ import annotations

import threading
from typing import Dict, List
from datetime import datetime, UTC
from uuid import uuid4

from plexa_server.models.session import Session
from plexa_server.models.message import Message
from plexa_server.models.lesson import Lesson
from plexa_server.models.course import Course
from plexa_server.inference.base import (
    InferenceBackend, 
    InferenceConfig, 
    InferenceError
)
from plexa_server.core.lessons import (
    validate_lesson_runtime,
    build_initial_messages,
    freeze_inference_config,
)
from plexa_server.storage.storage_interface import SessionStorage
from plexa_server.utils.lock_manager import LockManager


class SessionClosedError(Exception):
    """Raised when a caller tries to mutate an inactive session."""
    pass


class TurnLimitExceededError(Exception):
    """Raised when a session has already consumed its maximum turns."""
    pass


class SessionNotFoundError(Exception):
    """Raised when session storage has no record for the requested session."""
    pass


class SessionManager:
    """
    Authoritative session lifecycle manager.

    Enforces:
    - Single-writer per session
    - Atomic user→assistant mutation
    - Turn limit invariants
    - Deterministic ordering
    """

    def __init__(self, storage: SessionStorage, inference_backend: InferenceBackend):
        """Initialize the session manager.

        Args:
            storage: Storage backend used to persist sessions and inference
                configs.
            inference_backend: Backend used to generate assistant responses.
        """
        self._storage = storage
        self._inference = inference_backend
        self._lock_manager = LockManager()

    def create_session(
        self,
        lesson: Lesson,
        user_id: str,
        course_id: str,
        session_id: str | None = None,
    ) -> Session:
        """Create and persist a new session seeded from a lesson definition.

        Args:
            lesson: Lesson document that defines the runtime configuration.
            user_id: Identifier of the user who owns the session.
            course_id: Course identifier associated with the session.
            session_id: Identifier to assign to the new session, randomly generated if None.

        Returns:
            Session: Newly created session with its initial transcript.

        Raises:
            LessonRuntimeError: If the lesson is not runnable at runtime.
            ValueError: If the lesson does not define a turn limit.
        """
        if session_id == None:
            session_id = str(uuid4())

        validate_lesson_runtime(lesson)

        inference_config = freeze_inference_config(lesson)

        turn_limit = lesson.constraints.turn_limit
        if turn_limit is None:
            raise ValueError("Lesson must define a turn_limit.")

        initial_messages = build_initial_messages(
            lesson=lesson,
            session_id=session_id,
        )

        session = Session(
            session_id=session_id,
            lesson_id=lesson.identity.lesson_id,
            lesson_version=lesson.identity.version,
            user_id=user_id,
            course_id=course_id,
            messages=initial_messages,
            turn_count=0,
            max_turns=turn_limit,
            created_at=datetime.now(UTC),
            closed_at=None,
            is_active=True,
        )

        self._storage.save_session(session)
        self._storage.save_inference_config(session_id, inference_config)

        return session

    def get_session(self, session_id: str) -> Session:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Session: Persisted session matching the requested id.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        session = self._storage.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def list_sessions(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> List[Session]:
        """Return the caller's sessions for a specific course lesson version.

        Args:
            user_id: Identifier of the user who owns the sessions.
            course_id: Course identifier to match.
            lesson_id: Lesson identifier to match.
            lesson_version: Lesson version to match.

        Returns:
            List[Session]: Matching sessions ordered from newest to oldest.
        """
        sessions = [
            session
            for session in self._storage.list_sessions()
            if session.user_id == user_id
            and session.course_id == course_id
            and session.lesson_id == lesson_id
            and session.lesson_version == lesson_version
        ]

        return sorted(sessions, key=lambda session: session.created_at, reverse=True)

    def close_session(self, session_id: str) -> None:
        """Mark a session inactive and persist the closure timestamp.

        Args:
            session_id: Identifier of the session to close.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        lock = self._lock_manager.get_lock(session_id)

        with lock:
            session = self.get_session(session_id)
            if not session.is_active:
                return

            session.is_active = False
            session.closed_at = datetime.now(UTC)
            self._storage.save_session(session)
            self._lock_manager.release_lock(session_id)

    def submit_user_message(
        self,
        session_id: str,
        message_id: str,
        content: str,
    ) -> Message:
        """Append a user turn, run inference, and atomically persist the reply.

        Args:
            session_id: Identifier of the session to mutate.
            message_id: Identifier to assign to the new user message.
            content: User message content to submit for inference.

        Returns:
            Message: Persisted assistant reply generated for the submitted turn.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
            SessionClosedError: If the session is already inactive.
            TurnLimitExceededError: If the session has reached its turn limit.
            InferenceError: If the inference backend fails before the turn is
                committed.
        """
        lock = self._lock_manager.get_lock(session_id)

        with lock:
            session = self.get_session(session_id)

            if not session.is_active:
                raise SessionClosedError(session_id)

            if session.turn_count >= session.max_turns:
                raise TurnLimitExceededError(session_id)

            inference_config = self._storage.get_inference_config(session_id)

            user_message = Message(
                message_id=message_id,
                session_id=session_id,
                role="user",
                content=content,
                created_at=datetime.now(UTC),
            )

            # Build candidate message list (not yet committed)
            candidate_messages: List[Message] = session.messages + [user_message]

            try:
                result = self._inference.generate(
                    messages=candidate_messages,
                    config=inference_config,
                )
            except InferenceError:
                # Do not mutate session on failure
                raise

            assistant_message = Message(
                message_id=f"{message_id}-assistant",
                session_id=session_id,
                role="assistant",
                content=result.content,
                created_at=datetime.now(UTC),
            )

            # Atomic commit begins here
            session.messages.append(user_message)
            session.messages.append(assistant_message)
            session.turn_count += 1

            if session.turn_count >= session.max_turns:
                session.is_active = False
                session.closed_at = datetime.now(UTC)

            self._storage.save_session(session)

            return assistant_message
