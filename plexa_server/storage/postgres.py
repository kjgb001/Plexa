from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Iterable, Optional

from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from sqlalchemy.dialects.postgresql import insert as pg_insert

from plexa_server.db.models import (
    CourseEnrollmentRecord,
    CourseInstructorRecord,
    CourseLessonRecord,
    CoursePendingRequestRecord,
    CourseRecord,
    EncryptedLogAccessAuditRecord,
    EncryptedLogRecord,
    LessonRecord,
    MessageRecord,
    SessionRecord,
    UserCourseStateRecord,
    UserLessonStateRecord,
    UserRecord,
)
from plexa_server.inference.base import InferenceConfig
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditAction, EncryptedLogAccessAuditEntry
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.message import Message
from plexa_server.models.session import Session
from plexa_server.models.workspace_state import UserCourseState, UserLessonState
from plexa_server.storage.storage_interface import (
    ArtifactStorage,
    CourseRevisionConflictError,
    CourseStorage,
    LessonRevisionConflictError,
    SessionRevisionConflictError,
    SessionStorage,
    WorkspaceStateStorage,
)


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
        title=record.title,
        user_id=record.user.external_user_id,
        lesson_id=record.lesson.lesson_id,
        lesson_version=record.lesson.version,
        course_id=record.course.course_id,
        messages=[_message_from_record(message, record.session_id) for message in record.messages],
        created_at=record.created_at,
        updated_at=record.updated_at,
        closed_at=record.closed_at,
        turn_count=record.turn_count,
        max_turns=record.max_turns,
        is_active=record.is_active,
        is_completion_started=record.is_completion_started,
        completed_at=record.completed_at,
        is_finalized=record.is_finalized,
        turned_in_at=record.turned_in_at,
        logging_policy=record.logging_policy,
        lesson_snapshot=(
            None if record.lesson_snapshot is None else Lesson.model_validate(record.lesson_snapshot)
        ),
        lesson_artifact_revision=record.lesson_artifact_revision,
        lesson_content_sha256=record.lesson_content_sha256,
        frozen_inference_config=(
            None
            if record.frozen_inference_config is None
            else InferenceConfig.model_validate(record.frozen_inference_config)
        ),
        transcript_available=record.transcript_available,
        transcript_unavailable_reason=record.transcript_unavailable_reason,
        persistence_revision=record.persistence_revision,
        reflection_hooks=record.reflection_hooks,
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
        instructor_ids=[instructor.user.external_user_id for instructor in record.instructors],
        discoverable=record.discoverable,
        revision=record.revision,
        archived_at=record.archived_at,
        enrolled_users=[enrollment.user.external_user_id for enrollment in record.enrollments],
        pending_requests=[request.user.external_user_id for request in record.pending_requests],
        created_at=record.created_at,
        lessons=lessons,
        lesson_timeline=record.lesson_timeline,
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
        await session.execute(
            pg_insert(UserRecord)
            .values(external_user_id=external_user_id, created_at=datetime.now(UTC))
            .on_conflict_do_nothing(index_elements=[UserRecord.external_user_id])
        )
        result = await session.execute(
            select(UserRecord).where(UserRecord.external_user_id == external_user_id)
        )
        return result.scalar_one()

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

    async def restore_encrypted_log(
        self,
        metadata: EncryptedLogMetadata,
        encrypted_blob: bytes | None,
    ) -> None:
        """Restore a validated legacy log without changing its metadata."""
        async with self._session_factory() as session:
            session.add(
                EncryptedLogRecord(
                    instance_id=metadata.instance_id,
                    user_id=metadata.user_id,
                    course_id=metadata.course_id,
                    lesson_id=metadata.lesson_id,
                    lesson_version=metadata.lesson_version,
                    course_owner_id=metadata.course_owner_id,
                    authorized_instructor_ids=metadata.authorized_instructor_ids,
                    updated_at=metadata.updated_at,
                    closed_at=metadata.closed_at,
                    turned_in_at=metadata.turned_in_at,
                    turn_count=metadata.turn_count,
                    is_active=metadata.is_active,
                    log_version=metadata.log_version,
                    artifact_sha256=metadata.artifact_sha256,
                    last_event_type=metadata.last_event_type,
                    last_event_at=metadata.last_event_at,
                    key_id=metadata.key_id,
                    content_available=metadata.content_available,
                    encrypted_blob=encrypted_blob,
                    created_at=metadata.created_at,
                )
            )
            await session.commit()

    async def save_lesson(
        self,
        lesson: Lesson,
        course_id: str,
        expected_revision: int | None = None,
    ) -> int:
        """Persist a lesson artifact.

        Args:
            lesson: Lesson document to store.
            course_id: Course that owns the mutable artifact.
        """
        async with self._session_factory() as session:
            owner_result = await session.execute(
                select(CourseRecord).where(CourseRecord.course_id == course_id)
            )
            owner_record = owner_result.scalar_one_or_none()
            if owner_record is None:
                raise ValueError(f"Course {course_id} does not exist.")
            statement = select(LessonRecord).where(
                LessonRecord.lesson_id == lesson.identity.lesson_id,
                LessonRecord.version == lesson.identity.version,
            )
            statement = statement.where(LessonRecord.owning_course_id == owner_record.id)
            result = await session.execute(statement.with_for_update())
            record = result.scalar_one_or_none()
            payload = _lesson_to_record_payload(lesson)

            if record is None:
                if expected_revision is not None:
                    raise LessonRevisionConflictError(
                        "Lesson no longer exists; reload before saving."
                    )
                record = LessonRecord(
                    lesson_id=lesson.identity.lesson_id,
                    version=lesson.identity.version,
                    owning_course_id=owner_record.id,
                )
                session.add(record)
            else:
                if (
                    expected_revision is not None
                    and record.artifact_revision != expected_revision
                ):
                    raise LessonRevisionConflictError(
                        f"Lesson changed since revision {expected_revision}; reload and retry."
                    )
                record.artifact_revision += 1

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
            record.updated_at = datetime.now(UTC)

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise LessonRevisionConflictError(
                    "Lesson was created concurrently; reload before saving."
                ) from exc
            return record.artifact_revision

    async def load_lesson(
        self,
        lesson_id: str,
        version: str,
        course_id: str,
    ) -> Optional[Lesson]:
        """Load a lesson artifact by identifier and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.

        Returns:
            Optional[Lesson]: Stored lesson document, or `None` if absent.
        """
        async with self._session_factory() as session:
            statement = select(LessonRecord).where(
                LessonRecord.lesson_id == lesson_id,
                LessonRecord.version == version,
            )
            statement = statement.join(
                CourseRecord, CourseRecord.id == LessonRecord.owning_course_id
            ).where(CourseRecord.course_id == course_id)
            result = await session.execute(statement.order_by(LessonRecord.id).limit(1))
            record = result.scalar_one_or_none()
            if record is None:
                return None
            return Lesson.model_validate(record.payload)

    async def get_lesson_revision(
        self,
        lesson_id: str,
        version: str,
        course_id: str,
    ) -> int | None:
        async with self._session_factory() as session:
            statement = select(LessonRecord.artifact_revision).where(
                LessonRecord.lesson_id == lesson_id,
                LessonRecord.version == version,
            )
            statement = statement.join(
                CourseRecord, CourseRecord.id == LessonRecord.owning_course_id
            ).where(CourseRecord.course_id == course_id)
            result = await session.execute(statement.order_by(LessonRecord.id).limit(1))
            return result.scalar_one_or_none()

    async def save_encrypted_log(
        self,
        instance_id: str,
        encrypted_blob: bytes,
        metadata: EncryptedLogMetadata | None = None,
    ) -> None:
        """Persist an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.
            encrypted_blob: Opaque encrypted bytes to store.
            metadata: Optional plaintext metadata describing the artifact.
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
                if not record.content_available:
                    return
                record.encrypted_blob = encrypted_blob
            record.content_available = True
            if metadata is not None:
                record.user_id = metadata.user_id
                record.course_id = metadata.course_id
                record.lesson_id = metadata.lesson_id
                record.lesson_version = metadata.lesson_version
                record.course_owner_id = metadata.course_owner_id
                record.authorized_instructor_ids = metadata.authorized_instructor_ids
                record.updated_at = metadata.updated_at
                record.closed_at = metadata.closed_at
                record.turned_in_at = metadata.turned_in_at
                record.turn_count = metadata.turn_count
                record.is_active = metadata.is_active
                record.log_version = metadata.log_version
                record.artifact_sha256 = metadata.artifact_sha256
                record.last_event_type = metadata.last_event_type
                record.last_event_at = metadata.last_event_at
                record.key_id = metadata.key_id
                record.created_at = metadata.created_at
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

    async def load_encrypted_log_metadata(self, instance_id: str) -> Optional[EncryptedLogMetadata]:
        """Load plaintext metadata describing an encrypted log blob.

        Args:
            instance_id: Identifier for the encrypted log.

        Returns:
            Optional[EncryptedLogMetadata]: Stored metadata, or `None` if absent.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                select(EncryptedLogRecord).where(EncryptedLogRecord.instance_id == instance_id)
            )
            record = result.scalar_one_or_none()
            if record is None or record.user_id is None or record.course_id is None or record.lesson_id is None or record.lesson_version is None or record.course_owner_id is None or record.authorized_instructor_ids is None or record.updated_at is None or record.turn_count is None or record.is_active is None or record.log_version is None or record.artifact_sha256 is None or record.last_event_type is None or record.last_event_at is None or record.key_id is None:
                return None
            return EncryptedLogMetadata(
                instance_id=record.instance_id,
                user_id=record.user_id,
                course_id=record.course_id,
                lesson_id=record.lesson_id,
                lesson_version=record.lesson_version,
                course_owner_id=record.course_owner_id,
                authorized_instructor_ids=record.authorized_instructor_ids,
                created_at=record.created_at,
                updated_at=record.updated_at,
                closed_at=record.closed_at,
                turned_in_at=record.turned_in_at,
                turn_count=record.turn_count,
                is_active=record.is_active,
                log_version=record.log_version,
                artifact_sha256=record.artifact_sha256,
                last_event_type=record.last_event_type,
                last_event_at=record.last_event_at,
                key_id=record.key_id,
                content_available=record.content_available,
            )

    async def list_encrypted_log_metadata(
        self,
        course_id: str | None = None,
        lesson_id: str | None = None,
        lesson_version: str | None = None,
        owner_id: str | None = None,
        instructor_id: str | None = None,
        user_id: str | None = None,
    ) -> list[EncryptedLogMetadata]:
        """List plaintext metadata for encrypted session logs.

        Args:
            course_id: Optional course filter.
            lesson_id: Optional lesson filter.
            lesson_version: Optional lesson version filter.
            owner_id: Optional course owner filter.
            instructor_id: Optional authorized instructor filter.
            user_id: Optional student/user filter.

        Returns:
            list[EncryptedLogMetadata]: Matching metadata records.
        """
        async with self._session_factory() as session:
            stmt = select(EncryptedLogRecord)
            if course_id is not None:
                stmt = stmt.where(EncryptedLogRecord.course_id == course_id)
            if lesson_id is not None:
                stmt = stmt.where(EncryptedLogRecord.lesson_id == lesson_id)
            if lesson_version is not None:
                stmt = stmt.where(EncryptedLogRecord.lesson_version == lesson_version)
            if owner_id is not None:
                stmt = stmt.where(EncryptedLogRecord.course_owner_id == owner_id)
            if instructor_id is not None:
                stmt = stmt.where(EncryptedLogRecord.authorized_instructor_ids.contains([instructor_id]))
            if user_id is not None:
                stmt = stmt.where(EncryptedLogRecord.user_id == user_id)

            result = await session.execute(stmt)
            records = result.scalars().all()
            metadata: list[EncryptedLogMetadata] = []
            for record in records:
                if record.user_id is None or record.course_id is None or record.lesson_id is None or record.lesson_version is None or record.course_owner_id is None or record.authorized_instructor_ids is None or record.updated_at is None or record.turn_count is None or record.is_active is None or record.log_version is None or record.artifact_sha256 is None or record.last_event_type is None or record.last_event_at is None or record.key_id is None:
                    continue
                metadata.append(
                    EncryptedLogMetadata(
                        instance_id=record.instance_id,
                        user_id=record.user_id,
                        course_id=record.course_id,
                        lesson_id=record.lesson_id,
                        lesson_version=record.lesson_version,
                        course_owner_id=record.course_owner_id,
                        authorized_instructor_ids=record.authorized_instructor_ids,
                        created_at=record.created_at,
                        updated_at=record.updated_at,
                        closed_at=record.closed_at,
                        turned_in_at=record.turned_in_at,
                        turn_count=record.turn_count,
                        is_active=record.is_active,
                        log_version=record.log_version,
                        artifact_sha256=record.artifact_sha256,
                        last_event_type=record.last_event_type,
                        last_event_at=record.last_event_at,
                        key_id=record.key_id,
                        content_available=record.content_available,
                    )
                )
            return metadata

    async def delete_encrypted_log(self, instance_id: str) -> None:
        """Delete an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.
        """
        async with self._session_factory() as session:
            await session.execute(
                delete(EncryptedLogRecord).where(EncryptedLogRecord.instance_id == instance_id)
            )
            await session.commit()

    async def expire_encrypted_log_content(self, instance_id: str) -> None:
        """Delete encrypted content while retaining its lookup metadata."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(EncryptedLogRecord).where(EncryptedLogRecord.instance_id == instance_id)
            )
            record = result.scalar_one_or_none()
            if record is not None:
                record.encrypted_blob = None
                record.content_available = False
                await session.commit()

    async def save_encrypted_log_access_audit(
        self,
        entry: EncryptedLogAccessAuditEntry,
    ) -> None:
        """Persist an audit record for encrypted log access."""
        async with self._session_factory() as session:
            session.add(
                EncryptedLogAccessAuditRecord(
                    audit_id=entry.audit_id,
                    requester_user_id=entry.requester_user_id,
                    course_id=entry.course_id,
                    session_id=entry.session_id,
                    lesson_id=entry.lesson_id,
                    lesson_version=entry.lesson_version,
                    target_user_id=entry.target_user_id,
                    action=entry.action,
                    details=entry.details,
                    created_at=entry.created_at,
                )
            )
            await session.commit()

    async def list_encrypted_log_access_audits(
        self,
        course_id: str | None = None,
        session_id: str | None = None,
        requester_user_id: str | None = None,
        action: EncryptedLogAccessAuditAction | None = None,
    ) -> list[EncryptedLogAccessAuditEntry]:
        """List persisted audit records for encrypted log access."""
        async with self._session_factory() as session:
            stmt = select(EncryptedLogAccessAuditRecord)
            if course_id is not None:
                stmt = stmt.where(EncryptedLogAccessAuditRecord.course_id == course_id)
            if session_id is not None:
                stmt = stmt.where(EncryptedLogAccessAuditRecord.session_id == session_id)
            if requester_user_id is not None:
                stmt = stmt.where(EncryptedLogAccessAuditRecord.requester_user_id == requester_user_id)
            if action is not None:
                stmt = stmt.where(EncryptedLogAccessAuditRecord.action == action)
            stmt = stmt.order_by(EncryptedLogAccessAuditRecord.created_at.asc())
            result = await session.execute(stmt)
            return [
                EncryptedLogAccessAuditEntry(
                    audit_id=record.audit_id,
                    requester_user_id=record.requester_user_id,
                    course_id=record.course_id,
                    session_id=record.session_id,
                    lesson_id=record.lesson_id,
                    lesson_version=record.lesson_version,
                    target_user_id=record.target_user_id,
                    action=record.action,  # type: ignore[arg-type]
                    details=record.details,
                    created_at=record.created_at,
                )
                for record in result.scalars().all()
            ]

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
                selectinload(CourseRecord.instructors).selectinload(CourseInstructorRecord.user),
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
                    instructors=[],
                    pending_requests=[],
                    lesson_bindings=[],
                )
                session.add(record)
                record.revision = 0
            else:
                locked_revision = await session.scalar(
                    select(CourseRecord.revision)
                    .where(CourseRecord.id == record.id)
                    .with_for_update()
                )
                if locked_revision != course.revision:
                    raise CourseRevisionConflictError(
                        f"Course changed since revision {course.revision}; reload and retry."
                    )
                record.revision = course.revision + 1

            record.title = course.title
            record.description = course.description
            record.instructor = course.instructor
            record.term = course.term
            record.owner = owner
            record.discoverable = course.discoverable
            record.archived_at = course.archived_at
            record.lesson_timeline = [window.model_dump(mode="json") for window in course.lesson_timeline]
            record.created_at = course.created_at

            try:
                await session.flush()
            except IntegrityError as exc:
                await session.rollback()
                raise CourseRevisionConflictError(
                    "Course was created concurrently; reload before saving."
                ) from exc

            if not is_new:
                await session.execute(
                    delete(CourseEnrollmentRecord).where(
                        CourseEnrollmentRecord.course_id == record.id
                    )
                )
                await session.execute(
                    delete(CourseInstructorRecord).where(
                        CourseInstructorRecord.course_id == record.id
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
                record.instructors = []
                record.pending_requests = []
                record.lesson_bindings = []

            for user_id in course.enrolled_users:
                user = await self._get_or_create_user(session, user_id)
                record.enrollments.append(CourseEnrollmentRecord(user=user))

            for user_id in course.instructor_ids:
                user = await self._get_or_create_user(session, user_id)
                record.instructors.append(CourseInstructorRecord(user=user))

            for user_id in course.pending_requests:
                user = await self._get_or_create_user(session, user_id)
                record.pending_requests.append(CoursePendingRequestRecord(user=user))

            for lesson_id, version in course.lessons.items():
                lesson_result = await session.execute(
                    select(LessonRecord).where(
                        LessonRecord.owning_course_id == record.id,
                        LessonRecord.lesson_id == lesson_id,
                        LessonRecord.version == version,
                    )
                )
                lesson = lesson_result.scalar_one_or_none()
                if lesson is None:
                    raise ValueError(
                        f"Lesson {lesson_id}@{version} does not exist for course {course.course_id}."
                    )
                record.lesson_bindings.append(CourseLessonRecord(lesson=lesson))

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise CourseRevisionConflictError(
                    "Course changed concurrently; reload before saving."
                ) from exc
            course.revision = record.revision

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
                    selectinload(CourseRecord.instructors).selectinload(CourseInstructorRecord.user),
                    selectinload(CourseRecord.pending_requests).selectinload(CoursePendingRequestRecord.user),
                    selectinload(CourseRecord.lesson_bindings).selectinload(CourseLessonRecord.lesson),
                )
            )
            records = result.scalars().all()
            return [_course_from_record(record) for record in records]

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
        for_update: bool = False,
    ) -> SessionRecord | None:
        """Load a session row with related data.

        Args:
            session: Database session used for the lookup.
            session_id: Public session identifier.

        Returns:
            SessionRecord | None: Loaded session row, or `None` if absent.
        """
        statement = (
            select(SessionRecord)
            .options(
                selectinload(SessionRecord.user),
                selectinload(SessionRecord.course),
                selectinload(SessionRecord.lesson),
                selectinload(SessionRecord.messages),
            )
            .where(SessionRecord.session_id == session_id)
        )
        if for_update:
            statement = statement.with_for_update()
        result = await session.execute(statement)
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
                    LessonRecord.owning_course_id == course.id,
                    LessonRecord.lesson_id == session_model.lesson_id,
                    LessonRecord.version == session_model.lesson_version,
                )
            )
            lesson = lesson_result.scalar_one_or_none()
            if lesson is None:
                raise ValueError(
                    f"Lesson {session_model.lesson_id}@{session_model.lesson_version} does not exist."
                )

            record = await self._get_session_record(
                session, session_model.session_id, for_update=True
            )
            is_new = record is None
            if is_new:
                binding_result = await session.execute(
                    select(CourseLessonRecord).where(
                        CourseLessonRecord.course_id == course.id,
                        CourseLessonRecord.lesson_id == lesson.id,
                    )
                )
                if binding_result.scalar_one_or_none() is None:
                    raise ValueError(
                        f"Lesson {session_model.lesson_id}@{session_model.lesson_version} "
                        f"is not bound to course {session_model.course_id}."
                    )
                record = SessionRecord(
                    session_id=session_model.session_id,
                    messages=[],
                )
                session.add(record)
                record.persistence_revision = 0
            elif record.persistence_revision != session_model.persistence_revision:
                raise SessionRevisionConflictError(
                    "Session changed concurrently; reload and retry."
                )
            else:
                record.persistence_revision += 1

            record.user = user
            record.course = course
            record.lesson = lesson
            record.title = session_model.title
            record.created_at = session_model.created_at
            record.updated_at = session_model.updated_at
            record.closed_at = session_model.closed_at
            record.turn_count = session_model.turn_count
            record.max_turns = session_model.max_turns
            record.is_active = session_model.is_active
            record.is_completion_started = session_model.is_completion_started
            record.completed_at = session_model.completed_at
            record.is_finalized = session_model.is_finalized
            record.turned_in_at = session_model.turned_in_at
            record.logging_policy = session_model.logging_policy
            record.reflection_hooks = [hook.model_dump(mode="json") for hook in session_model.reflection_hooks]
            record.lesson_snapshot = (
                None
                if session_model.lesson_snapshot is None
                else session_model.lesson_snapshot.model_dump(mode="json")
            )
            record.lesson_artifact_revision = session_model.lesson_artifact_revision
            record.lesson_content_sha256 = session_model.lesson_content_sha256
            record.transcript_available = session_model.transcript_available
            record.transcript_unavailable_reason = session_model.transcript_unavailable_reason
            if session_model.frozen_inference_config is not None:
                record.frozen_inference_config = session_model.frozen_inference_config.model_dump(mode="json")

            await session.flush()

            if not is_new:
                await session.execute(
                    delete(MessageRecord).where(
                        MessageRecord.session_id == record.id
                    )
                )
                await session.flush()
                record.messages = []
            persisted_messages = [] if session_model.logging_policy == "disabled" else [
                message for message in session_model.messages if message.role != "system"
            ]
            for index, message in enumerate(persisted_messages):
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
            session_model.persistence_revision = record.persistence_revision

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


class PostgresWorkspaceStateStorage(PostgresStorageMixin, WorkspaceStateStorage):
    """Postgres-backed storage for user course and lesson recency state."""

    async def restore_course_state(self, state: UserCourseState) -> None:
        """Restore a legacy course state while preserving its timestamp."""
        async with self._session_factory() as session:
            user = await self._get_or_create_user(session, state.user_id)
            course_result = await session.execute(
                select(CourseRecord).where(CourseRecord.course_id == state.course_id)
            )
            course = course_result.scalar_one_or_none()
            if course is None:
                raise ValueError(f"Course {state.course_id} does not exist.")
            session.add(
                UserCourseStateRecord(
                    user=user,
                    course=course,
                    last_accessed_at=state.last_accessed_at,
                )
            )
            await session.commit()

    async def restore_lesson_state(self, state: UserLessonState) -> None:
        """Restore a legacy lesson state while preserving its timestamp."""
        async with self._session_factory() as session:
            user = await self._get_or_create_user(session, state.user_id)
            course_result = await session.execute(
                select(CourseRecord).where(CourseRecord.course_id == state.course_id)
            )
            course = course_result.scalar_one_or_none()
            if course is None:
                raise ValueError(f"Course {state.course_id} does not exist.")
            lesson_result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.owning_course_id == course.id,
                    LessonRecord.lesson_id == state.lesson_id,
                    LessonRecord.version == state.lesson_version,
                )
            )
            lesson = lesson_result.scalar_one_or_none()
            if lesson is None:
                raise ValueError(
                    f"Lesson {state.lesson_id}@{state.lesson_version} does not exist "
                    f"in course {state.course_id}."
                )
            session.add(
                UserLessonStateRecord(
                    user=user,
                    course=course,
                    lesson=lesson,
                    last_accessed_at=state.last_accessed_at,
                )
            )
            await session.commit()

    async def touch_course(
        self,
        user_id: str,
        course_id: str,
    ) -> UserCourseState:
        async with self._session_factory() as session:
            user = await self._get_or_create_user(session, user_id)
            course_result = await session.execute(
                select(CourseRecord).where(CourseRecord.course_id == course_id)
            )
            course = course_result.scalar_one_or_none()
            if course is None:
                raise ValueError(f"Course {course_id} does not exist.")

            result = await session.execute(
                select(UserCourseStateRecord).where(
                    UserCourseStateRecord.user_id == user.id,
                    UserCourseStateRecord.course_id == course.id,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = UserCourseStateRecord(
                    user=user,
                    course=course,
                    last_accessed_at=datetime.now(UTC),
                )
                session.add(record)
            else:
                record.last_accessed_at = datetime.now(UTC)

            await session.commit()
            return UserCourseState(
                user_id=user_id,
                course_id=course_id,
                last_accessed_at=record.last_accessed_at,
            )

    async def touch_lesson(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> UserLessonState:
        async with self._session_factory() as session:
            user = await self._get_or_create_user(session, user_id)
            course_result = await session.execute(
                select(CourseRecord).where(CourseRecord.course_id == course_id)
            )
            course = course_result.scalar_one_or_none()
            if course is None:
                raise ValueError(f"Course {course_id} does not exist.")
            lesson_result = await session.execute(
                select(LessonRecord).where(
                    LessonRecord.lesson_id == lesson_id,
                    LessonRecord.version == lesson_version,
                )
            )
            lesson = lesson_result.scalar_one_or_none()
            if lesson is None:
                raise ValueError(f"Lesson {lesson_id}@{lesson_version} does not exist.")

            result = await session.execute(
                select(UserLessonStateRecord).where(
                    UserLessonStateRecord.user_id == user.id,
                    UserLessonStateRecord.course_id == course.id,
                    UserLessonStateRecord.lesson_id == lesson.id,
                )
            )
            record = result.scalar_one_or_none()
            if record is None:
                record = UserLessonStateRecord(
                    user=user,
                    course=course,
                    lesson=lesson,
                    last_accessed_at=datetime.now(UTC),
                )
                session.add(record)
            else:
                record.last_accessed_at = datetime.now(UTC)

            await session.commit()
            return UserLessonState(
                user_id=user_id,
                course_id=course_id,
                lesson_id=lesson_id,
                lesson_version=lesson_version,
                last_accessed_at=record.last_accessed_at,
            )

    async def list_course_states(self, user_id: str) -> list[UserCourseState]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(
                    UserCourseStateRecord.last_accessed_at,
                    UserRecord.external_user_id,
                    CourseRecord.course_id,
                )
                .join(UserRecord, UserCourseStateRecord.user_id == UserRecord.id)
                .join(CourseRecord, UserCourseStateRecord.course_id == CourseRecord.id)
                .where(UserRecord.external_user_id == user_id)
            )
            return [
                UserCourseState(
                    user_id=external_user_id,
                    course_id=course_id,
                    last_accessed_at=last_accessed_at,
                )
                for last_accessed_at, external_user_id, course_id in result.all()
            ]

    async def list_lesson_states(
        self,
        user_id: str,
        course_id: str | None = None,
    ) -> list[UserLessonState]:
        async with self._session_factory() as session:
            query = (
                select(
                    UserLessonStateRecord.last_accessed_at,
                    UserRecord.external_user_id,
                    CourseRecord.course_id,
                    LessonRecord.lesson_id,
                    LessonRecord.version,
                )
                .join(UserRecord, UserLessonStateRecord.user_id == UserRecord.id)
                .join(CourseRecord, UserLessonStateRecord.course_id == CourseRecord.id)
                .join(LessonRecord, UserLessonStateRecord.lesson_id == LessonRecord.id)
                .where(UserRecord.external_user_id == user_id)
            )
            if course_id is not None:
                query = query.where(CourseRecord.course_id == course_id)

            result = await session.execute(query)
            return [
                UserLessonState(
                    user_id=external_user_id,
                    course_id=resolved_course_id,
                    lesson_id=resolved_lesson_id,
                    lesson_version=lesson_version,
                    last_accessed_at=last_accessed_at,
                )
                for (
                    last_accessed_at,
                    external_user_id,
                    resolved_course_id,
                    resolved_lesson_id,
                    lesson_version,
                ) in result.all()
            ]

    async def health_check(self) -> bool:
        return await self._ping()
