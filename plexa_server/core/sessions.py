from __future__ import annotations

from typing import List
from datetime import datetime, UTC
from uuid import uuid4

from plexa_server.models.session import Session
from plexa_server.models.message import Message
from plexa_server.models.lesson import Lesson
from plexa_server.inference.base import (
    InferenceBackend,
    InferenceError,
)
from plexa_server.inference.routing import InferenceRouter, create_single_backend_router
from plexa_server.core.lessons import (
    validate_lesson_runtime,
    build_initial_messages,
    freeze_inference_config,
)
from plexa_server.core.encrypted_logs import EncryptedLogService
from plexa_server.core.session_titles import (
    DeterministicSessionTitleGenerator,
    SessionTitleGenerator,
    default_session_title,
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

    def __init__(
        self,
        storage: SessionStorage,
        inference_router: InferenceRouter | None = None,
        inference_backend: InferenceBackend | None = None,
        encrypted_log_service: EncryptedLogService | None = None,
        title_generator: SessionTitleGenerator | None = None,
    ):
        """Initialize the session manager.

        Args:
            storage: Storage backend used to persist sessions and inference
                configs.
            inference_router: Router used to resolve lesson profiles into
                concrete backend calls.
            inference_backend: Legacy single backend used to generate assistant
                responses when no router is supplied.
            encrypted_log_service: Optional service used to persist encrypted
                session log snapshots.
            title_generator: Strategy used to derive persisted session titles.
        """
        self._storage = storage
        if inference_router is not None:
            self._inference = inference_router
        elif inference_backend is not None:
            self._inference = create_single_backend_router(inference_backend)
        else:
            raise ValueError("SessionManager requires an inference router or backend.")
        self._encrypted_logs = encrypted_log_service
        self._title_generator = title_generator or DeterministicSessionTitleGenerator()
        self._lock_manager = LockManager()

    async def create_session(
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
            title="",
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
        session.title = default_session_title(session)

        await self._storage.save_session(session)
        await self._storage.save_inference_config(session_id, inference_config)
        await self._persist_encrypted_log(session, inference_config, event_type="created")

        return session

    async def get_session(self, session_id: str) -> Session:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Session: Persisted session matching the requested id.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        session = await self._storage.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    async def list_sessions(
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
            for session in await self._storage.list_sessions()
            if session.user_id == user_id
            and session.course_id == course_id
            and session.lesson_id == lesson_id
            and session.lesson_version == lesson_version
        ]

        return sorted(sessions, key=lambda session: session.created_at, reverse=True)

    async def close_session(self, session_id: str) -> None:
        """Mark a session inactive and persist the closure timestamp.

        Args:
            session_id: Identifier of the session to close.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        lock = self._lock_manager.get_lock(session_id)

        with lock:
            session = await self.get_session(session_id)
            if not session.is_active:
                return

            session.is_active = False
            session.closed_at = datetime.now(UTC)
            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="closed")
            self._lock_manager.release_lock(session_id)

    async def delete_session(self, session_id: str) -> None:
        """Delete a persisted session and its associated inference config.

        Args:
            session_id: Identifier of the session to delete.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        lock = self._lock_manager.get_lock(session_id)

        with lock:
            session = await self.get_session(session_id)
            await self._storage.delete_session(session_id)
            if self._encrypted_logs is not None:
                await self._encrypted_logs.delete_session_log(session.session_id)
            self._lock_manager.release_lock(session_id)

    async def submit_user_message(
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
            session = await self.get_session(session_id)

            if not session.is_active:
                raise SessionClosedError(session_id)

            if session.turn_count >= session.max_turns:
                raise TurnLimitExceededError(session_id)

            inference_config = await self._storage.get_inference_config(session_id)

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
                result = await self._inference.generate(
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
            if session.turn_count == 1:
                generated_title = await self._title_generator.generate_title(session, user_message)
                if generated_title is not None and generated_title.strip():
                    session.title = generated_title.strip()

            if session.turn_count >= session.max_turns:
                session.is_active = False
                session.closed_at = datetime.now(UTC)

            await self._storage.save_session(session)
            await self._persist_encrypted_log(session, inference_config, event_type="message_commit")

            return assistant_message

    async def _persist_encrypted_log(
        self,
        session: Session,
        inference_config,
        event_type,
    ) -> None:
        """Persist the encrypted log snapshot when logging is configured.

        Args:
            session: Session state snapshot to log.
            inference_config: Frozen inference config associated with the session.
            event_type: Lifecycle event that produced the current snapshot.
        """
        if self._encrypted_logs is None:
            return
        await self._encrypted_logs.persist_session_log(session, inference_config, event_type=event_type)
