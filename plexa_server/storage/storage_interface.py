from abc import ABC, abstractmethod
from typing import List, Optional

from plexa_server.inference.base import InferenceConfig
from plexa_server.models.encrypted_log import EncryptedLogMetadata
from plexa_server.models.course import Course
from plexa_server.models.lesson import Lesson
from plexa_server.models.log_access_audit import EncryptedLogAccessAuditEntry, EncryptedLogAccessAuditAction
from plexa_server.models.session import Session
from plexa_server.models.workspace_state import UserCourseState, UserLessonState


class ArtifactStorage(ABC):
    """Abstract storage contract for lesson artifacts and encrypted logs."""

    @abstractmethod
    async def save_lesson(self, lesson: Lesson) -> None:
        """Persist a lesson artifact.

        Args:
            lesson: Lesson document to store.
        """

    @abstractmethod
    async def load_lesson(self, lesson_id: str, version: str) -> Optional[Lesson]:
        """Load a lesson artifact by identifier and version.

        Args:
            lesson_id: Lesson identifier to load.
            version: Lesson version to load.

        Returns:
            Optional[Lesson]: Stored lesson document, or `None` if absent.
        """

    @abstractmethod
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

    @abstractmethod
    async def load_encrypted_log(self, instance_id: str) -> Optional[bytes]:
        """Load an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.

        Returns:
            Optional[bytes]: Stored encrypted bytes, or `None` if absent.
        """

    @abstractmethod
    async def load_encrypted_log_metadata(self, instance_id: str) -> Optional[EncryptedLogMetadata]:
        """Load plaintext metadata describing an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.

        Returns:
            Optional[EncryptedLogMetadata]: Stored metadata, or `None` if absent.
        """

    @abstractmethod
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

    @abstractmethod
    async def delete_encrypted_log(self, instance_id: str) -> None:
        """Delete an encrypted lesson log blob.

        Args:
            instance_id: Identifier for the encrypted log.
        """

    @abstractmethod
    async def save_encrypted_log_access_audit(
        self,
        entry: EncryptedLogAccessAuditEntry,
    ) -> None:
        """Persist an audit record for instructor access to encrypted logs."""

    @abstractmethod
    async def list_encrypted_log_access_audits(
        self,
        course_id: str | None = None,
        session_id: str | None = None,
        requester_user_id: str | None = None,
        action: EncryptedLogAccessAuditAction | None = None,
    ) -> list[EncryptedLogAccessAuditEntry]:
        """List persisted audit records for encrypted log access."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Report whether artifact storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """


class SessionStorage(ABC):
    """Abstract storage contract for sessions and frozen inference configs."""

    @abstractmethod
    async def save_session(self, session: Session) -> None:
        """Persist the current session state.

        Args:
            session: Session object to store.
        """

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        """Load a session by id.

        Args:
            session_id: Identifier of the session to load.

        Returns:
            Optional[Session]: Persisted session, or `None` if absent.
        """

    @abstractmethod
    async def delete_session(self, session_id: str) -> None:
        """Delete any persisted state associated with a session id.

        Args:
            session_id: Identifier of the session to delete.
        """

    @abstractmethod
    async def save_inference_config(
        self,
        session_id: str,
        config: InferenceConfig,
    ) -> None:
        """Persist the frozen inference config for a session.

        Args:
            session_id: Identifier of the session that owns the config.
            config: Frozen inference config to store.
        """

    @abstractmethod
    async def get_inference_config(self, session_id: str) -> Optional[InferenceConfig]:
        """Load a session's inference config.

        Args:
            session_id: Identifier of the session whose config should be loaded.

        Returns:
            Optional[InferenceConfig]: Persisted config, or `None` if absent.
        """

    @abstractmethod
    async def list_sessions(self) -> List[Session]:
        """Load every persisted session document.

        Returns:
            List[Session]: All persisted sessions.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Report whether session storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """


class CourseStorage(ABC):
    """Abstract storage contract for course metadata and lesson bindings."""

    @abstractmethod
    async def save_course(self, course: Course) -> None:
        """Persist a course document.

        Args:
            course: Course document to store.
        """

    @abstractmethod
    async def get_course(self, course_id: str) -> Optional[Course]:
        """Load a course by id.

        Args:
            course_id: Identifier of the course to load.

        Returns:
            Optional[Course]: Persisted course, or `None` if absent.
        """

    @abstractmethod
    async def delete_course(self, course_id: str) -> None:
        """Delete a persisted course document.

        Args:
            course_id: Identifier of the course to delete.
        """

    @abstractmethod
    async def list_courses(self) -> List[Course]:
        """Load every persisted course document.

        Returns:
            List[Course]: All persisted courses.
        """

    @abstractmethod
    async def bind_lesson_to_course(
        self,
        course_id: str,
        lesson_id: str,
        version: str,
    ) -> None:
        """Bind a lesson version into a course document.

        Args:
            course_id: Identifier of the course to update.
            lesson_id: Lesson identifier to bind.
            version: Lesson version to store.
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """Report whether course storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """


class WorkspaceStateStorage(ABC):
    """Abstract storage contract for user-scoped course and lesson recency state."""

    @abstractmethod
    async def touch_course(
        self,
        user_id: str,
        course_id: str,
    ) -> UserCourseState:
        """Persist a course access timestamp for a user."""

    @abstractmethod
    async def touch_lesson(
        self,
        user_id: str,
        course_id: str,
        lesson_id: str,
        lesson_version: str,
    ) -> UserLessonState:
        """Persist a lesson access timestamp for a user."""

    @abstractmethod
    async def list_course_states(self, user_id: str) -> list[UserCourseState]:
        """Return all stored course recency state for a user."""

    @abstractmethod
    async def list_lesson_states(
        self,
        user_id: str,
        course_id: str | None = None,
    ) -> list[UserLessonState]:
        """Return all stored lesson recency state for a user."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Report whether workspace-state storage is reachable.

        Returns:
            bool: `True` when the storage backend is ready for use.
        """
