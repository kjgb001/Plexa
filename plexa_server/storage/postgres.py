from __future__ import annotations

from typing import Any, Iterable, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from plexa_server.db.models import (
    CourseEnrollmentRecord,
    CourseLessonRecord,
    CoursePendingRequestRecord,
    CourseRecord,
    EncryptedLogRecord,
    LessonRecord,
    MessageRecord,
    SessionRecord,
    UserRecord,
)
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.models.session import Session
from plexa_server.storage.storage_interface import ArtifactStorage, CourseStorage, SessionStorage


def _lesson_to_record_payload(lesson: Lesson) -> dict[str, Any]:
    """Serialize a lesson for JSONB persistence.

    Args:
        lesson: Lesson document to serialize.

    Returns:
        dict[str, Any]: JSON-serializable lesson payload.
    """
    return lesson.model_dump(mode="json")


def _message_from_record(record: MessageRecord, session_id: str) -> Message:
    """Hydrate a domain message from a database row.

    Args:
        record: Database message row.
        session_id: Public session identifier for the owning session.

    Returns:
        Message: Hydrated domain model.
    """
    return Message(
        message_id=record.message_id,
        session_id=session_id,
        role=record.role,
        content=record.content,
        created_at=record.created_at,
        metadata=record.message_metadata,
    )


def _session_from_record(record: SessionRecord) -> Session:
    """Hydrate a domain session from a database row.

    Args:
        record: Database session row with messages loaded.

    Returns:
        Session: Hydrated domain session model.
    """
    return Session(
        session_id=record.session_id,
        user_id=record.user.external_user_id,
        lesson_id=record.lesson.lesson_id,
        lesson_version=record.lesson.version,
        course_id=record.course.course_id,
        messages=[_message_from_record(message, record.session_id) for message in record.messages],
        created_at=record.created_at,
        closed_at=record.closed_at,
        turn_count=record.turn_count,
        max_turns=record.max_turns,
        is_active=record.is_active,
    )


def _course_from_record(record: CourseRecord) -> Course:
    """Hydrate a domain course from a database row.

    Args:
        record: Database course row with related rows loaded.

    Returns:
        Course: Hydrated domain course model.
    """
    lessons = {
        binding.lesson.lesson_id: binding.lesson.version
        for binding in record.lesson_bindings
    }
    return Course(
        course_id=record.course_id,
        title=record.title,
        description=record.description,
        instructor=record.instructor,
        term=record.term,
        owner_id=record.owner.external_user_id,
        discoverable=record.discoverable,
        enrolled_users=[enrollment.user.external_user_id for enrollment in record.enrollments],
        pending_requests=[request.user.external_user_id for request in record.pending_requests],
        created_at=record.created_at,
        lessons=lessons,
    )


class PostgresStorageMixin:
    """Shared helpers for Postgres-backed storage classes."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        """Store the async SQLAlchemy session factory.

        Args:
            session_factory: Factory used to create database sessions.
        """
        self._session_factory = session_factory

    async def _get_or_create_user(
        self,
        session: AsyncSession,
        external_user_id: str,
    ) -> UserRecord:
        """Load or create a user row by external identifier.

        Args:
            session: Database session used for the lookup.
            external_user_id: Public user identifier.

        Returns:
            UserRecord: Existing or newly created user row.
        """
        result = await session.execute(
            select(UserRecord).where(UserRecord.external_user_id == external_user_id)
        )
        user = result.scalar_one_or_none()
        if user is None:
            user = UserRecord(external_user_id=external_user_id)
            session.add(user)
            await session.flush()
        return user

    async def _get_or_create_course(
        self,
        session: AsyncSession,
        course_id: str,
        owner: UserRecord,
    ) -> CourseRecord:
        """Load or create a minimal course row by public identifier.

        This preserves the existing storage abstraction semantics, where
        sessions may reference an opaque `course_id` without requiring that
        course metadata has already been created through `CourseStorage`.

        Args:
            session: Database session used for the lookup.
            course_id: Public course identifier.
            owner: User row to assign as placeholder owner when creation is needed.

        Returns:
            CourseRecord: Existing or newly created course row.
        """
        result = await session.execute(
            select(CourseRecord).where(CourseRecord.course_id == course_id)
        )
        course = result.scalar_one_or_none()
        if course is None:
            course = CourseRecord(
                course_id=course_id,
                title=course_id,
                description=None,
                instructor=None,
                term=None,
                owner=owner,
                discoverable=False,
            )
            session.add(course)
            await session.flush()
        return course

    async def _ping(self) -> bool:
        """Probe the backing database with a trivial query.

        Returns:
            bool: `True` when the database responds successfully.
        """
        try:
            async with self._session_factory() as session:
                await session.execute(text("SELECT 1"))
            return True
        except Exception:
            return False


class PostgresArtifactStorage(PostgresStorageMixin, ArtifactStorage):
    """Postgres-backed storage for lessons and encrypted logs."""

    async def save_lesson(self, lesson: Lesson) -> None:
        """Persist a lesson artifact.

        Args:
            lesson: Lesson document to store.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.lesson_id == lesson.identity.lesson_id,
                    LessonRecord.version == lesson.identity.version,
                )
            )
            record = result.scalar_one_or_none()
            payload = _lesson_to_record_payload(lesson)

            if record is None:
                record = LessonRecord(
                    lesson_id=lesson.identity.lesson_id,
                    version=lesson.identity.version,
                )
                session.add(record)

            record.title = lesson.identity.title
            record.author = lesson.identity.author
            record.course = lesson.identity.course
            record.unit = lesson.identity.unit
            record.license = lesson.identity.license
            record.lesson_created_at = lesson.identity.created_at
            record.learning_objective = lesson.intent.learning_objective
            record.behavioral_focus = lesson.intent.behavioral_focus
            record.difficulty = lesson.intent.difficulty
            record.approximate_time = lesson.intent.approximate_time
            record.schema_version = lesson.schema_version
            record.payload = payload

            await session.commit()

    async def load_lesson(self, lesson_id: str, version: str) -> Optional[Lesson]:
        """Load a lesson artifact by identifier and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.

        Returns:
            Optional[Lesson]: Stored lesson document, or `None` if absent.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.lesson_id == lesson_id,
                    LessonRecord.version == version,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return Lesson.model_validate(record.payload)

    async def save_encrypted_log(self, instance_id: str, encrypted_blob: bytes) -> None:
        """Persist an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.
            encrypted_blob: Opaque encrypted bytes to store.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EncryptedLogRecord).where(EncryptedLogRecord.instance_id == instance_id)
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = EncryptedLogRecord(instance_id=instance_id, encrypted_blob=encrypted_blob)
                session.add(record)
            else:
                record.encrypted_blob = encrypted_blob
            await session.commit()

    async def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
        """Load an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.

        Returns:
            Optional[bytes]: Stored encrypted bytes, or `None` if absent.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EncryptedLogRecord).where(EncryptedLogRecord.instance_id == instance_id)
            )
            record = result.scalar_one_or_none()
            return None if record is None else record.encrypted_blob

    async def health_check(self) -> bool:
        """Report whether artifact storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """
        return await self._ping()


class PostgresCourseStorage(PostgresStorageMixin, CourseStorage):
    """Postgres-backed storage for courses and lesson bindings."""

    async def _get_course_record(
        self,
        session: AsyncSession,
        course_id: str,
    ) -> CourseRecord | None:
        """Load a course row with related data.

        Args:
            session: Database session used for the lookup.
            course_id: Public course identifier.

        Returns:
            CourseRecord | None: Loaded course row, or `None` if absent.
        """
        result = await session.execute(
            select(CourseRecord)
            .options(
                selectinload(CourseRecord.owner),
                selectinload(CourseRecord.enrollments).selectinload(CourseEnrollmentRecord.user),
                selectinload(CourseRecord.pending_requests).selectinload(CoursePendingRequestRecord.user),
                selectinload(CourseRecord.lesson_bindings).selectinload(CourseLessonRecord.lesson),
            )
            .where(CourseRecord.course_id == course_id)
        )
        return result.scalar_one_or_none()

    async def save_course(self, course: Course) -> None:
        """Persist a course document.

        Args:
            course: Course document to store.
        """
        async with self._session_factory() as session:
            owner = await self._get_or_create_user(session, course.owner_id)
            record = await self._get_course_record(session, course.course_id)
            is_new = record is None

            if is_new:
                record = CourseRecord(
                    course_id=course.course_id,
                    owner=owner,
                    enrollments=[],
                    pending_requests=[],
                    lesson_bindings=[],
                )
                session.add(record)

            record.title = course.title
            record.description = course.description
            record.instructor = course.instructor
            record.term = course.term
            record.owner = owner
            record.discoverable = course.discoverable
            record.created_at = course.created_at

            await session.flush()

            if not is_new:
                await session.execute(
                    delete(CourseEnrollmentRecord).where(
                        CourseEnrollmentRecord.course_id == record.id
                    )
                )
                await session.execute(
                    delete(CoursePendingRequestRecord).where(
                        CoursePendingRequestRecord.course_id == record.id
                    )
                )
                await session.execute(
                    delete(CourseLessonRecord).where(
                        CourseLessonRecord.course_id == record.id
                    )
                )
                await session.flush()
                record.enrollments = []
                record.pending_requests = []
                record.lesson_bindings = []

            for user_id in course.enrolled_users:
                user = await self._get_or_create_user(session, user_id)
                record.enrollments.append(CourseEnrollmentRecord(user=user))

            for user_id in course.pending_requests:
                user = await self._get_or_create_user(session, user_id)
                record.pending_requests.append(CoursePendingRequestRecord(user=user))

            for lesson_id, version in course.lessons.items():
                lesson_result = await session.execute(
                    select(LessonRecord).where(
                        LessonRecord.lesson_id == lesson_id,
                        LessonRecord.version == version,
                    )
                )
                lesson = lesson_result.scalar_one_or_none()
                if lesson is not None:
                    record.lesson_bindings.append(CourseLessonRecord(lesson=lesson))

            await session.commit()

    async def get_course(self, course_id: str) -> Optional[Course]:
        """Load a course by id.

        Args:
            course_id: Identifier of the course to load.

        Returns:
            Optional[Course]: Persisted course, or `None` if absent.
        """
        async with self._session_factory() as session:
            record = await self._get_course_record(session, course_id)
            return None if record is None else _course_from_record(record)

    async def delete_course(self, course_id: str) -> None:
        """Delete a persisted course document.

        Args:
            course_id: Identifier of the course to delete.
        """
        async with self._session_factory() as session:
            await session.execute(delete(CourseRecord).where(CourseRecord.course_id == course_id))
            await session.commit()

    async def list_courses(self) -> list[Course]:
        """Load every persisted course document.

        Returns:
            list[Course]: All persisted courses.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(CourseRecord).options(
                    selectinload(CourseRecord.owner),
                    selectinload(CourseRecord.enrollments).selectinload(CourseEnrollmentRecord.user),
                    selectinload(CourseRecord.pending_requests).selectinload(CoursePendingRequestRecord.user),
                    selectinload(CourseRecord.lesson_bindings).selectinload(CourseLessonRecord.lesson),
                )
            )
            records = result.scalars().all()
            return [_course_from_record(record) for record in records]

    async def bind_lesson_to_course(self, course_id: str, lesson_id: str, version: str) -> None:
        """Bind a lesson version into a course document.

        Args:
            course_id: Identifier of the course to update.
            lesson_id: Lesson identifier to bind.
            version: Lesson version to store.
        """
        async with self._session_factory() as session:
            course = await self._get_course_record(session, course_id)
            if course is None:
                return

            lesson_result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.lesson_id == lesson_id,
                    LessonRecord.version == version,
                )
            )
            lesson = lesson_result.scalar_one_or_none()
            if lesson is None:
                return

            existing = next(
                (binding for binding in course.lesson_bindings if binding.lesson.lesson_id == lesson_id),
                None,
            )
            if existing is not None:
                existing.lesson = lesson
            else:
                course.lesson_bindings.append(CourseLessonRecord(lesson=lesson))

            await session.commit()

    async def health_check(self) -> bool:
        """Report whether course storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """
        return await self._ping()


class PostgresSessionStorage(PostgresStorageMixin, SessionStorage):
    """Postgres-backed storage for sessions and frozen inference configs."""

    async def _get_session_record(
        self,
        session: AsyncSession,
        session_id: str,
    ) -> SessionRecord | None:
        """Load a session row with related data.

        Args:
            session: Database session used for the lookup.
            session_id: Public session identifier.

        Returns:
            SessionRecord | None: Loaded session row, or `None` if absent.
        """
        result = await session.execute(
            select(SessionRecord)
            .options(
                selectinload(SessionRecord.user),
                selectinload(SessionRecord.course),
                selectinload(SessionRecord.lesson),
                selectinload(SessionRecord.messages),
            )
            .where(SessionRecord.session_id == session_id)
        )
        return result.scalar_one_or_none()

    async def save_session(self, session_model: Session) -> None:
        """Persist the current session state.

        Args:
            session_model: Session object to store.
        """
        async with self._session_factory() as session:
            user = await self._get_or_create_user(session, session_model.user_id)
            course = await self._get_or_create_course(session, session_model.course_id, user)

            lesson_result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.lesson_id == session_model.lesson_id,
                    LessonRecord.version == session_model.lesson_version,
                )
            )
            lesson = lesson_result.scalar_one_or_none()
            if lesson is None:
                raise ValueError(
                    f"Lesson {session_model.lesson_id}@{session_model.lesson_version} does not exist."
                )

            record = await self._get_session_record(session, session_model.session_id)
            is_new = record is None
            if is_new:
                record = SessionRecord(
                    session_id=session_model.session_id,
                    messages=[],
                )
                session.add(record)

            record.user = user
            record.course = course
            record.lesson = lesson
            record.created_at = session_model.created_at
            record.closed_at = session_model.closed_at
            record.turn_count = session_model.turn_count
            record.max_turns = session_model.max_turns
            record.is_active = session_model.is_active

            await session.flush()

            if not is_new:
                await session.execute(
                    delete(MessageRecord).where(
                        MessageRecord.session_id == record.id
                    )
                )
                await session.flush()
                record.messages = []
            for index, message in enumerate(session_model.messages):
                record.messages.append(
                    MessageRecord(
                        message_id=message.message_id,
                        role=message.role,
                        content=message.content,
                        message_metadata=message.metadata,
                        sequence_index=index,
                        created_at=message.created_at,
                    )
                )

            await session.commit()

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Persisted session, or `None` if absent.
        """
        async with self._session_factory() as session:
            record = await self._get_session_record(session, session_id)
            return None if record is None else _session_from_record(record)

    async def delete_session(self, session_id: str) -> None:
        """Delete any persisted state associated with a session id.

        Args:
            session_id: Identifier of the session to delete.
        """
        async with self._session_factory() as session:
            await session.execute(delete(SessionRecord).where(SessionRecord.session_id == session_id))
            await session.commit()

    async def save_inference_config(self, session_id: str, config: InferenceConfig) -> None:
        """Persist the frozen inference config for a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to store.
        """
        async with self._session_factory() as session:
            record = await self._get_session_record(session, session_id)
            if record is None:
                raise ValueError(f"Session {session_id} does not exist.")
            record.frozen_inference_config = config.model_dump(mode="json")
            await session.commit()

    async def get_inference_config(self, session_id: str) -> Optional[InferenceConfig]:
        """Load a session's inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Persisted config, or `None` if absent.
        """
        async with self._session_factory() as session:
            record = await self._get_session_record(session, session_id)
            if record is None or record.frozen_inference_config is None:
                return None
            return InferenceConfig.model_validate(record.frozen_inference_config)

    async def list_sessions(self) -> list[Session]:
        """Load every persisted session document.

        Returns:
            list[Session]: All persisted sessions.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(SessionRecord).options(
                    selectinload(SessionRecord.user),
                    selectinload(SessionRecord.course),
                    selectinload(SessionRecord.lesson),
                    selectinload(SessionRecord.messages),
                )
            )
            records = result.scalars().all()
            return [_session_from_record(record) for record in records]

    async def health_check(self) -> bool:
        """Report whether session storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """
        return await self._ping()
