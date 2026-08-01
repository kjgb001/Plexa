from __future__ import annotations

from dataclasses import dataclass
import asyncio
import hashlib
import json
from typing import AsyncIterator, List
from datetime import datetime, UTC
from uuid import uuid4

from plexa_server.models.session import Session
from plexa_server.models.session import SessionReflectionHook
from plexa_server.models.message import Message
from plexa_server.models.lesson import Lesson, LessonReflectionHook
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
from plexa_server.core.workspace import order_sessions_by_updated_at
from plexa_server.storage.storage_interface import (
    SessionRevisionConflictError,
    SessionStorage,
)
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


class SessionCompletionError(Exception):
    """Raised when completion or reflection actions are invalid for session state."""
    pass


class SessionMessageConflictError(Exception):
    """Raised when a message id is reused with conflicting content or state."""


class SessionConcurrencyLimitError(Exception):
    """Raised when a user already has two inference calls in flight."""


class SessionStreamingError(InferenceError):
    """Normalized streaming failure with an explicit client fallback policy."""

    def __init__(self, detail: str, fallback_allowed: bool):
        super().__init__(detail)
        self.fallback_allowed = fallback_allowed


@dataclass(frozen=True)
class SessionMessageDelta:
    """Ephemeral assistant text that has not yet been committed."""

    content_delta: str


@dataclass(frozen=True)
class SessionMessageComplete:
    """Canonical persisted result of a streamed user turn."""

    assistant_message: Message
    session: Session


SessionMessageStreamEvent = SessionMessageDelta | SessionMessageComplete


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
        self._ephemeral_transcripts: dict[str, list[Message]] = {}
        self._active_inferences: dict[str, int] = {}
        self._inference_count_lock = asyncio.Lock()

    async def create_session(
        self,
        lesson: Lesson,
        user_id: str,
        course_id: str,
        session_id: str | None = None,
        lesson_artifact_revision: int = 1,
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
            lesson_snapshot=lesson.model_copy(deep=True),
            frozen_inference_config=inference_config,
            lesson_artifact_revision=lesson_artifact_revision,
            lesson_content_sha256=hashlib.sha256(
                json.dumps(
                    lesson.model_dump(mode="json"),
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            ).hexdigest(),
            turn_count=0,
            max_turns=turn_limit,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            closed_at=None,
            is_active=True,
            logging_policy=lesson.reflection.logging_policy or "default",
            reflection_hooks=[
                SessionReflectionHook(
                    hook_id=hook.hook_id,
                    prompt=hook.prompt,
                    phase=hook.phase,
                    order_index=hook.order_index,
                    trigger_turn=self._resolve_reflection_trigger_turn(hook, turn_limit),
                    carry_to_post=hook.carry_to_post,
                )
                for hook in lesson.reflection.hooks
            ],
        )
        session.title = default_session_title(session)

        if session.logging_policy == "disabled":
            self._ephemeral_transcripts[session.session_id] = list(initial_messages)

        await self._storage.save_session(session)
        try:
            await self._persist_encrypted_log(session, inference_config, event_type="created")
        except Exception:
            await self._storage.delete_session(session.session_id)
            self._ephemeral_transcripts.pop(session.session_id, None)
            raise

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
        if self._hydrate_ephemeral_transcript(session):
            try:
                await self._storage.save_session(session)
            except SessionRevisionConflictError:
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
        stored_sessions = await self._storage.list_sessions()
        for index, stored_session in enumerate(stored_sessions):
            if self._hydrate_ephemeral_transcript(stored_session):
                try:
                    await self._storage.save_session(stored_session)
                except SessionRevisionConflictError:
                    current = await self._storage.get_session(stored_session.session_id)
                    if current is not None:
                        stored_sessions[index] = current
        sessions = [
            session
            for session in stored_sessions
            if session.user_id == user_id
            and session.course_id == course_id
            and session.lesson_id == lesson_id
            and session.lesson_version == lesson_version
        ]

        return order_sessions_by_updated_at(sessions)

    async def close_session(self, session_id: str) -> None:
        """Mark a session inactive and persist the closure timestamp.

        Args:
            session_id: Identifier of the session to close.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if not session.is_active:
                inference_config = await self._storage.get_inference_config(session_id)
                await self._persist_encrypted_log(session, inference_config, event_type="closed")
                return

            session.is_active = False
            session.closed_at = datetime.now(UTC)
            session.updated_at = datetime.now(UTC)
            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="closed")

    async def begin_completion(self, session_id: str) -> Session:
        """Enter soft-completion mode and trigger post reflections."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                raise SessionCompletionError("Session is already turned in.")

            session.is_completion_started = True
            if session.completed_at is None:
                session.completed_at = datetime.now(UTC)
            self._trigger_completion_reflections(session)
            session.updated_at = datetime.now(UTC)
            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="message_commit")
            return session

    async def resume_after_completion(self, session_id: str) -> Session:
        """Exit soft-completion mode while the session is still chat-editable."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                raise SessionCompletionError("Turned-in sessions cannot be reopened.")
            if not session.is_active:
                raise SessionCompletionError("Closed sessions cannot resume chat work.")

            session.is_completion_started = False
            session.completed_at = None
            self._clear_completion_reflections(session)
            session.updated_at = datetime.now(UTC)
            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="message_commit")
            return session

    async def save_reflection_response(
        self,
        session_id: str,
        hook_id: str,
        response_text: str,
    ) -> Session:
        """Create or update a reflection response for a triggered hook."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                raise SessionCompletionError("Turned-in sessions cannot edit reflections.")
            if session.transcript_unavailable_reason == "content_expired":
                raise SessionCompletionError(
                    "Session content expired under the retention policy."
                )

            hook = next((item for item in session.reflection_hooks if item.hook_id == hook_id), None)
            if hook is None:
                raise SessionCompletionError("Reflection hook not found.")
            if hook.triggered_at is None:
                raise SessionCompletionError("Reflection hook has not been triggered.")

            now = datetime.now(UTC)
            if hook.first_answered_at is None:
                hook.first_answered_at = now
            hook.last_updated_at = now
            hook.postponed_at = None
            hook.response_text = response_text
            session.updated_at = now

            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="message_commit")
            return session

    async def postpone_reflection(
        self,
        session_id: str,
        hook_id: str,
    ) -> Session:
        """Mark a triggered mid-session reflection as deferred."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                raise SessionCompletionError("Turned-in sessions cannot edit reflections.")

            hook = next((item for item in session.reflection_hooks if item.hook_id == hook_id), None)
            if hook is None:
                raise SessionCompletionError("Reflection hook not found.")
            if hook.phase != "mid":
                raise SessionCompletionError("Only mid-session reflections can be postponed.")
            if hook.triggered_at is None:
                raise SessionCompletionError("Reflection hook has not been triggered.")
            if hook.response_text is not None and hook.response_text.strip():
                raise SessionCompletionError("Answered reflections cannot be postponed.")

            now = datetime.now(UTC)
            hook.postponed_at = now
            session.updated_at = now

            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="message_commit")
            return session

    async def turn_in_session(self, session_id: str) -> Session:
        """Finalize and lock a session after required reflections are complete."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                inference_config = await self._storage.get_inference_config(session_id)
                await self._persist_encrypted_log(session, inference_config, event_type="closed")
                return session
            if not session.is_completion_started:
                raise SessionCompletionError("Completion must begin before turn-in.")
            if not self._required_reflections_answered(session):
                raise SessionCompletionError("All triggered reflections must be answered before turn-in.")

            now = datetime.now(UTC)
            session.is_finalized = True
            session.turned_in_at = now
            session.is_active = False
            if session.closed_at is None:
                session.closed_at = now
            session.updated_at = now

            await self._storage.save_session(session)
            inference_config = await self._storage.get_inference_config(session_id)
            await self._persist_encrypted_log(session, inference_config, event_type="closed")
            return session

    async def delete_session(self, session_id: str) -> None:
        """Delete a persisted session and its associated inference config.

        Args:
            session_id: Identifier of the session to delete.

        Raises:
            SessionNotFoundError: If no session exists for the given id.
        """
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            if session.is_finalized:
                raise SessionCompletionError("Turned-in sessions cannot be deleted.")
            await self._storage.delete_session(session_id)
            self._ephemeral_transcripts.pop(session_id, None)
            if self._encrypted_logs is not None:
                await self._encrypted_logs.delete_session_log(session.session_id)

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
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            existing = self._find_committed_assistant(session, message_id, content)
            if existing is not None:
                inference_config = await self._storage.get_inference_config(session_id)
                await self._persist_encrypted_log(
                    session,
                    inference_config,
                    event_type="message_commit",
                )
                return existing

            self._validate_new_user_turn(session)
            inference_config = await self._storage.get_inference_config(session_id)
            user_message = self._build_user_message(session_id, message_id, content)
            candidate_messages = self._build_inference_messages(session, user_message)

            await self._acquire_inference_slot(session.user_id)
            try:
                result = await self._inference.generate(
                    messages=candidate_messages,
                    config=inference_config,
                )
                return await self._commit_user_turn(
                    session=session,
                    user_message=user_message,
                    assistant_content=result.content,
                    inference_config=inference_config,
                )
            finally:
                await self._release_inference_slot(session.user_id)

    async def submit_user_message_stream(
        self,
        session_id: str,
        message_id: str,
        content: str,
    ) -> AsyncIterator[SessionMessageStreamEvent]:
        """Stream an assistant draft and atomically commit the completed turn."""
        async with self._lock_manager.lock(session_id):
            session = await self.get_session(session_id)
            existing = self._find_committed_assistant(session, message_id, content)
            if existing is not None:
                inference_config = await self._storage.get_inference_config(session_id)
                await self._persist_encrypted_log(
                    session,
                    inference_config,
                    event_type="message_commit",
                )
                yield SessionMessageComplete(
                    assistant_message=existing,
                    session=session,
                )
                return

            self._validate_new_user_turn(session)
            inference_config = await self._storage.get_inference_config(session_id)
            user_message = self._build_user_message(session_id, message_id, content)
            candidate_messages = self._build_inference_messages(session, user_message)
            content_parts: list[str] = []

            await self._acquire_inference_slot(session.user_id)
            try:
                async for chunk in self._inference.stream(
                    messages=candidate_messages,
                    config=inference_config,
                ):
                    if not chunk.content_delta:
                        continue
                    content_parts.append(chunk.content_delta)
                    yield SessionMessageDelta(content_delta=chunk.content_delta)
            except InferenceError as exc:
                if content_parts:
                    raise SessionStreamingError(
                        str(exc) or "Inference stream was interrupted.",
                        fallback_allowed=True,
                    ) from exc
                try:
                    result = await self._inference.generate(
                        messages=candidate_messages,
                        config=inference_config,
                    )
                except InferenceError as fallback_exc:
                    raise SessionStreamingError(
                        str(fallback_exc) or "Inference failed.",
                        fallback_allowed=False,
                    ) from fallback_exc
                content_parts.append(result.content)
                if result.content:
                    yield SessionMessageDelta(content_delta=result.content)

            finally:
                await self._release_inference_slot(session.user_id)

            if not content_parts:
                await self._acquire_inference_slot(session.user_id)
                try:
                    result = await self._inference.generate(
                        messages=candidate_messages,
                        config=inference_config,
                    )
                except InferenceError as fallback_exc:
                    raise SessionStreamingError(
                        str(fallback_exc) or "Inference failed.",
                        fallback_allowed=False,
                    ) from fallback_exc
                finally:
                    await self._release_inference_slot(session.user_id)
                content_parts.append(result.content)
                if result.content:
                    yield SessionMessageDelta(content_delta=result.content)

            assistant_message = await self._commit_user_turn(
                session=session,
                user_message=user_message,
                assistant_content="".join(content_parts),
                inference_config=inference_config,
            )
            yield SessionMessageComplete(
                assistant_message=assistant_message,
                session=session,
            )

    def _find_committed_assistant(
        self,
        session: Session,
        message_id: str,
        content: str,
    ) -> Message | None:
        """Return the committed assistant reply for an idempotent retry."""
        matching_indexes = [
            index
            for index, message in enumerate(session.messages)
            if message.message_id == message_id
        ]
        if not matching_indexes:
            return None
        if len(matching_indexes) != 1:
            raise SessionMessageConflictError("Message id is not unique in this session.")

        user_index = matching_indexes[0]
        user_message = session.messages[user_index]
        if user_message.role != "user" or user_message.content != content:
            raise SessionMessageConflictError(
                "Message id was already used with different content."
            )

        assistant_id = f"{message_id}-assistant"
        for message in session.messages[user_index + 1:]:
            if message.message_id == assistant_id and message.role == "assistant":
                return message
        raise SessionMessageConflictError(
            "Message id belongs to an incomplete or malformed committed turn."
        )

    def _validate_new_user_turn(
        self,
        session: Session,
    ) -> None:
        """Apply session state and reflection gates before inference begins."""
        if not session.is_active:
            raise SessionClosedError(session.session_id)
        if session.turn_count >= session.max_turns:
            raise TurnLimitExceededError(session.session_id)
        if self._has_pending_mid_reflection(session):
            raise SessionCompletionError(
                "Mid-session reflection must be answered before continuing."
            )

    def _build_user_message(
        self,
        session_id: str,
        message_id: str,
        content: str,
    ) -> Message:
        """Build an uncommitted user transcript entry."""
        return Message(
            message_id=message_id,
            session_id=session_id,
            role="user",
            content=content,
            created_at=datetime.now(UTC),
        )

    async def _commit_user_turn(
        self,
        session: Session,
        user_message: Message,
        assistant_content: str,
        inference_config,
    ) -> Message:
        """Persist one completed user/assistant turn and derived session state."""
        assistant_message = Message(
            message_id=f"{user_message.message_id}-assistant",
            session_id=session.session_id,
            role="assistant",
            content=assistant_content,
            created_at=datetime.now(UTC),
        )

        session.messages.append(user_message)
        session.messages.append(assistant_message)
        session.turn_count += 1
        session.updated_at = datetime.now(UTC)
        if session.turn_count == 1:
            generated_title = await self._title_generator.generate_title(
                session,
                user_message,
            )
            if generated_title is not None and generated_title.strip():
                session.title = generated_title.strip()

        self._trigger_mid_reflections(session)

        if session.turn_count >= session.max_turns:
            session.is_completion_started = True
            if session.completed_at is None:
                session.completed_at = datetime.now(UTC)
            session.is_active = False
            session.closed_at = datetime.now(UTC)
            self._trigger_completion_reflections(session)

        await self._storage.save_session(session)
        if session.logging_policy == "disabled":
            self._ephemeral_transcripts[session.session_id] = list(session.messages)
        await self._persist_encrypted_log(
            session,
            inference_config,
            event_type="message_commit",
        )
        return assistant_message

    def _trigger_mid_reflections(self, session: Session) -> None:
        """Trigger any mid-session reflections due at the current turn count."""
        now = datetime.now(UTC)
        for hook in session.reflection_hooks:
            if hook.phase != "mid":
                continue
            if hook.triggered_at is not None:
                continue
            if hook.trigger_turn is None:
                continue
            if hook.carry_to_post and session.max_turns is not None and session.turn_count >= session.max_turns:
                continue
            if session.turn_count >= hook.trigger_turn:
                hook.triggered_at = now
                hook.trigger_source = "mid_turn"

    def _resolve_reflection_trigger_turn(self, hook: LessonReflectionHook, turn_limit: int) -> int | None:
        """Return the concrete turn for mid-session hooks."""
        if hook.phase != "mid":
            return None
        if hook.trigger_turn is not None:
            return hook.trigger_turn
        return max(1, (turn_limit + 1) // 2)

    def _trigger_completion_reflections(self, session: Session) -> None:
        """Trigger post reflections and any carry-forward mid reflections."""
        now = datetime.now(UTC)
        for hook in session.reflection_hooks:
            if hook.triggered_at is not None:
                if (
                    hook.phase == "mid"
                    and hook.postponed_at is not None
                    and (hook.response_text is None or not hook.response_text.strip())
                ):
                    hook.postponed_at = None
                continue
            if hook.phase == "post":
                hook.triggered_at = now
                hook.trigger_source = "soft_complete"
                continue
            if hook.phase == "mid" and hook.carry_to_post:
                hook.triggered_at = now
                hook.trigger_source = "carry_to_post"
                hook.carried_to_post = True

    def _clear_completion_reflections(self, session: Session) -> None:
        """Hide completion-triggered reflections when a student returns to work."""
        for hook in session.reflection_hooks:
            if hook.trigger_source not in {"soft_complete", "carry_to_post"}:
                continue
            hook.triggered_at = None
            hook.trigger_source = None
            hook.postponed_at = None
            hook.response_text = None
            hook.first_answered_at = None
            hook.last_updated_at = None
            if hook.carried_to_post:
                hook.carried_to_post = False

    def _has_pending_mid_reflection(self, session: Session) -> bool:
        """Return whether a triggered mid-session reflection still needs a response."""
        return any(
            hook.phase == "mid"
            and hook.triggered_at is not None
            and hook.postponed_at is None
            and (hook.response_text is None or not hook.response_text.strip())
            for hook in session.reflection_hooks
        )

    def _required_reflections_answered(self, session: Session) -> bool:
        """Return whether all triggered hooks have responses."""
        return all(
            hook.response_text is not None and hook.response_text.strip()
            for hook in session.reflection_hooks
            if hook.triggered_at is not None
        )

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

    def _hydrate_ephemeral_transcript(self, session: Session) -> bool:
        """Attach process-local messages and report whether restart closure must persist."""
        if session.logging_policy != "disabled":
            return False
        cached = self._ephemeral_transcripts.get(session.session_id)
        if cached is not None:
            session.messages = list(cached)
            session.transcript_available = True
            session.transcript_unavailable_reason = None
            return False
        if session.turn_count == 0 and session.lesson_snapshot is not None:
            session.messages = build_initial_messages(session.lesson_snapshot, session.session_id)
            self._ephemeral_transcripts[session.session_id] = list(session.messages)
            session.transcript_available = True
            session.transcript_unavailable_reason = None
            return False
        session.messages = []
        session.transcript_available = False
        interrupted = session.is_active
        if interrupted:
            now = datetime.now(UTC)
            session.transcript_unavailable_reason = "server_restart"
            session.is_active = False
            session.closed_at = now
            session.updated_at = now
        elif session.transcript_unavailable_reason is None:
            session.transcript_unavailable_reason = "not_persisted"
        return interrupted

    def _build_inference_messages(self, session: Session, user_message: Message) -> list[Message]:
        """Build model context with the private snapshot prompt prepended server-side."""
        if session.lesson_snapshot is None:
            raise SessionCompletionError("Session lesson snapshot is unavailable.")
        system_message = Message(
            message_id="system-runtime",
            session_id=session.session_id,
            role="system",
            content=session.lesson_snapshot.execution.system_prompt,
            created_at=session.created_at,
        )
        return [system_message, *session.messages, user_message]

    async def _acquire_inference_slot(self, user_id: str) -> None:
        async with self._inference_count_lock:
            active = self._active_inferences.get(user_id, 0)
            if active >= 2:
                raise SessionConcurrencyLimitError(
                    "At most two inference requests may run concurrently."
                )
            self._active_inferences[user_id] = active + 1

    async def _release_inference_slot(self, user_id: str) -> None:
        async with self._inference_count_lock:
            active = self._active_inferences.get(user_id, 0)
            if active <= 1:
                self._active_inferences.pop(user_id, None)
            else:
                self._active_inferences[user_id] = active - 1
