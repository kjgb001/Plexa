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
from plexa_server.utils.lock_manager import LockManager

class SessionClosedError(Exception):
    pass


class TurnLimitExceededError(Exception):
    pass


class SessionNotFoundError(Exception):
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

    def __init__(self, storage, inference_backend: InferenceBackend):
        self._storage = storage
        self._inference = inference_backend
        self._lock_manager = LockManager()

    def create_session(
        self,
        lesson: Lesson,
        user_id: str,
        course_id: Course,
        session_id: str = str(uuid4()),
    ) -> Session:

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
        session = self._storage.get_session(session_id)
        if session is None:
            raise SessionNotFoundError(session_id)
        return session

    def close_session(self, session_id: str) -> None:
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
