from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp.

    Returns:
        datetime: Current UTC timestamp.
    """
    return datetime.now(UTC)


class Base(DeclarativeBase):
    """Declarative base for Plexa database models."""


class UserRecord(Base):
    """Canonical internal user record."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    external_user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class CourseRecord(Base):
    """Course metadata row."""

    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    term: Mapped[str | None] = mapped_column(String(255), nullable=True)
    owner_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    discoverable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lesson_timeline: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    owner: Mapped[UserRecord] = relationship()
    enrollments: Mapped[list[CourseEnrollmentRecord]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    instructors: Mapped[list[CourseInstructorRecord]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    pending_requests: Mapped[list[CoursePendingRequestRecord]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )
    lesson_bindings: Mapped[list[CourseLessonRecord]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
    )


class CourseEnrollmentRecord(Base):
    """Enrollment join row between a user and a course."""

    __tablename__ = "course_enrollments"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_enrollment"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    course: Mapped[CourseRecord] = relationship(back_populates="enrollments")
    user: Mapped[UserRecord] = relationship()


class CoursePendingRequestRecord(Base):
    """Pending enrollment request join row between a user and a course."""

    __tablename__ = "course_pending_requests"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_pending_request"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    course: Mapped[CourseRecord] = relationship(back_populates="pending_requests")
    user: Mapped[UserRecord] = relationship()


class CourseInstructorRecord(Base):
    """Authorized instructor join row between a user and a course."""

    __tablename__ = "course_instructors"
    __table_args__ = (UniqueConstraint("course_id", "user_id", name="uq_course_instructor"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    course: Mapped[CourseRecord] = relationship(back_populates="instructors")
    user: Mapped[UserRecord] = relationship()


class LessonRecord(Base):
    """Versioned lesson artifact row."""

    __tablename__ = "lessons"
    __table_args__ = (UniqueConstraint("lesson_id", "version", name="uq_lesson_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lesson_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    author: Mapped[str] = mapped_column(String(255), nullable=False)
    course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(255), nullable=True)
    license: Mapped[str] = mapped_column(String(255), nullable=False)
    lesson_created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    learning_objective: Mapped[str] = mapped_column(Text, nullable=False)
    behavioral_focus: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approximate_time: Mapped[str | None] = mapped_column(String(255), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    course_bindings: Mapped[list[CourseLessonRecord]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[SessionRecord]] = relationship(back_populates="lesson")


class CourseLessonRecord(Base):
    """Join row binding a concrete lesson version into a course."""

    __tablename__ = "course_lessons"
    __table_args__ = (UniqueConstraint("course_id", "lesson_id", name="uq_course_lesson"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)

    course: Mapped[CourseRecord] = relationship(back_populates="lesson_bindings")
    lesson: Mapped[LessonRecord] = relationship(back_populates="course_bindings")


class UserCourseStateRecord(Base):
    """User-scoped recency state for a course."""

    __tablename__ = "user_course_states"
    __table_args__ = (UniqueConstraint("user_id", "course_id", name="uq_user_course_state"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[UserRecord] = relationship()
    course: Mapped[CourseRecord] = relationship()


class UserLessonStateRecord(Base):
    """User-scoped recency state for a lesson within a course."""

    __tablename__ = "user_lesson_states"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id", "lesson_id", name="uq_user_lesson_state"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="CASCADE"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    user: Mapped[UserRecord] = relationship()
    course: Mapped[CourseRecord] = relationship()
    lesson: Mapped[LessonRecord] = relationship()


class SessionRecord(Base):
    """Session row for a user's lesson conversation."""

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="Untitled session")
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id", ondelete="RESTRICT"), nullable=False)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    turn_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_completion_started: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    turned_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    logging_policy: Mapped[str] = mapped_column(String(32), nullable=False, default="default")
    reflection_hooks: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list, nullable=False)
    frozen_inference_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    user: Mapped[UserRecord] = relationship()
    course: Mapped[CourseRecord] = relationship()
    lesson: Mapped[LessonRecord] = relationship(back_populates="sessions")
    messages: Mapped[list[MessageRecord]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="MessageRecord.sequence_index",
    )


class MessageRecord(Base):
    """Ordered transcript row belonging to a session."""

    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("session_id", "sequence_index", name="uq_session_message_index"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_metadata: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    sequence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    session: Mapped[SessionRecord] = relationship(back_populates="messages")


class EncryptedLogRecord(Base):
    """Encrypted session log artifact plus plaintext lookup metadata."""

    __tablename__ = "encrypted_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    instance_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    course_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lesson_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lesson_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    course_owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    authorized_instructor_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    turn_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    log_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    artifact_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_event_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    encrypted_blob: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class EncryptedLogAccessAuditRecord(Base):
    """Audit row for instructor access to encrypted session logs."""

    __tablename__ = "encrypted_log_access_audits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    audit_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    requester_user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    course_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lesson_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    lesson_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_user_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
